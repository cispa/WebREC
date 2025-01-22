import logging
import networkx as nx
import math
import hashlib
import base64
import os
import multiprocessing
from collections import defaultdict
from tqdm import tqdm
import pickle

logging.basicConfig(level=logging.INFO)

PROCESSES = 16

# !!! This analysis only looks for usage of GoogleTagManager

class Third_Party_Analyser:

    def __init__(self, graphml_file: str, origin: str) -> None:
        """The init method requires the path to the graphml file and the crawled origin."""

        self.G = nx.read_graphml(graphml_file)
        self.origin = origin
        self.graphml_file = graphml_file
        self.resource_dictionary: dict[str, list[str]] = defaultdict(list)
        self.fill_resource_dictionary()

    def find_resource(self, search="google-analytics"):
        """Find all resources that requested aa URL containing `search`"""
        search_result = list()
        for e in self.G.edges(data=True):
            t = e[2]['edge type']
            if t in ["request start", "request redirect"]:
                n = self.G.nodes().get(e[1])
                parent_n = self.G.nodes().get(e[0])
                if search in n["url"]:
                    print("Found: ", n)
                    node_type = parent_n["node type"]
                    if node_type == "HTML element":
                        node_type += "--" + parent_n["tag name"]
                    print("Via ", node_type)
                    trace = self.trace_execution(parent_n)
                    print("Trace: ", trace)
                    search_result.append((node_type, trace, n["url"], self.graphml_file))

                    # If we find a redirect, we log it to manually analyze
                    if t == "request redirect":
                        with open(f"./third_party_redirects-{n['id']}", "a") as f:
                            f.write(f"{self.graphml_file}\n")
                            f.write(f"{parent_n}\n")
                            f.write(f"{n}\n")
                            f.write(f"\n")

        return search_result


    def fill_resource_dictionary(self) -> None:
        """This method fills a key/value store with resource hashes and their URLs."""

        for parent, child, edge in self.G.edges(data=True):
            if edge["edge type"] == "request complete":
                script_hash64 = edge["response hash"]
                parent_node = self.G.nodes().get(parent)
                resource = parent_node["url"]
                self.resource_dictionary[script_hash64].append(resource)

    def trace_execution(self, node: dict[str, str]) -> list[str]:
        """This method traces the execution and creation of nodes by following the 'execute' and 'create node' edge recursively."""

        logging.debug(f"Analyse node: {node}")
        node_id = f"n{node['id']}"
        node_type = node["node type"]

        if node_type == "script":
            # The script was executed by someone.
            # We want to find out who.

            script_type = node["script type"]
            resource = self.get_script_resource(node)

            for parent, child, edge in self.G.in_edges(node_id, data=True):
                if edge["edge type"] == "execute":
                    parent_node = self.G.nodes().get(parent)
                    if script_type == "module":
                        logging.debug("Module with exec")
                    trace = self.trace_execution(parent_node)
                    if resource:
                        trace.append(resource)
                    return trace

            raise Exception(
                f"Script node <{node_id}, {script_type}> has no execution edge."
            )

        if node_type == "HTML element":
            # Every HTML element needs to be created by another node.
            tag_name = node["tag name"]
            for parent, child, edge in self.G.in_edges(node_id, data=True):
                if edge["edge type"] == "create node":
                    parent_node = self.G.nodes().get(parent)
                    trace = self.trace_execution(parent_node)
                    return trace

            raise Exception(
                f"HTML node ({tag_name}, {node_id}) has no create node edge."
            )

        if node_type == "resource":
            logging.error("I returned a resource!!!")
            return [node["url"]]

        if node_type == "parser":
            # The root of all documents is the parser.
            return [self.origin]

        # frame owner
        raise Exception(f"Unexpected node type {node_type}.")
    

    def get_script_resource(self, node: dict[str, str]) -> str | None:
        """This method tries various methods to find out the resource URL of a script.
        1) Find resource node via connected resource node
        2) Find resource via src attribute
        3) Find resource via source hash
        """

        node_id = f"n{node['id']}"
        node_type = node["node type"]
        assert node_type == "script", f"Expected script, got {node_type}"

        # eval("") has no source
        script_source = node.get("source", "").encode()
        script_hash = hashlib.sha256(script_source)
        script_hash64 = base64.b64encode(script_hash.digest()).decode()
        script_type = node["script type"]

        resource = None

        executor_node = None
        for parent, child, edge in self.G.in_edges(node_id, data=True):
            if edge["edge type"] == "execute":
                executor_node = self.G.nodes().get(parent)

        if executor_node is None:
            # This can happen if we have an inline event handler.
            raise Exception(
                f"Script node <{node_id}, {script_type}> has no execution edge."
            )

        # 1) Find resource node via connected resource node
        # There can be multiple request edges, e.g., if the script imported something. 
        # The initial request has always the lowest id.
        smallest_resource_id = math.inf
        for parent, child, edge in self.G.in_edges(f'n{executor_node["id"]}', data=True):
            if (
                edge["edge type"] == "request complete"
                and edge["resource type"].lower() == "script"
                # and edge["response hash"] == script_hash64
            ):
                resource_node = self.G.nodes().get(parent)
                if int(resource_node["id"]) < smallest_resource_id:
                    smallest_resource_id = int(resource_node["id"])
        
        if smallest_resource_id < math.inf:            
            resource_node = self.G.nodes().get(f"n{smallest_resource_id}")
            resource = resource_node["url"]
            
        # 2) Find resource via src attribute
        if resource is None:
            for parent, child, edge in self.G.in_edges(f'n{executor_node["id"]}', data=True):
                if (
                    edge["edge type"] == "set attribute"
                    and edge["key"].lower() == "src"
                ):
                    resource = edge["value"]
                    assert script_type in [
                        "external file",
                        "module",
                    ], f"Expected module or external file, got {script_type}"

        # 3) Find resource only via source hash
        # This is the case if a script element used defer
        if resource is None:
            resource_list = self.resource_dictionary.get(script_hash64, [])
            resource = None
            if len(resource_list) != 0:
                if len(set(resource_list)) > 1:
                    raise Exception(f"Two resources for same hash: {resource_list}")
                resource = resource_list[0]

        # logging.error(resource)

        # Some additional checks
        # External file are expected to have a resource
        if script_type in ["external file"]:
            if resource is None:
                # from IPython import embed; embed()
                raise Exception(f"External files ({script_type}, {node_id}) expect resources")

            assert (
                resource is not None
            ), f"External files ({script_type}, {node_id}) expect resources"

        # No "inline inside generated element", because some sites load script dynamically and then put it inside an inline script
        if script_type in ["inline", "inline inside document write"]:
            assert (
                resource is None
            ), f"Inline scripts ({script_type}, {node_id}) expect no resources. Got {resource}"

        if script_type == "inline inside document write" and resource is not None:
            # This resource was loaded via JS. Inline scripts have no source.
            resource = None

        if script_type == "eval" and resource is not None:
            # This resource was loaded via JS. Eval scripts have no source.
            resource = None

        return resource
  
def run_analysis(path):
    search = "googletagmanager.com"

    # Get the graphml file
    graphml_file = ""
    for f in os.listdir(path):
        if f.endswith(".graphml"):
            graphml_file = os.path.join(path, f)
            break

    # Call the Third Party Analyser
    res = dict()
    try:
        print(path)
        tpa = Third_Party_Analyser(graphml_file, "ORIGIN")
        p_node_types = tpa.find_resource(search)
        res[path] = p_node_types
    except Exception as e:
        res[path] = [("ERROR", e, None)]
        pass
    print("======")

    return res


def main():
    # The path to the crawl output we want to analyze
    crawl_output_path = "../src/output/2024-05-03_161812"

    # The path to a list of origins that we want to analyze.
    # This list is manually created from another analysis 
    # and contains only origins that ever request the GTM
    list_path = "./googletagmanager.list"

    # The path to the result pickle for later analysis
    pickle_path = "./googletagmanager_0606_new.pkl"


    origin_directories = list()
    with open(list_path, "r") as f:
        for o in f.read().splitlines():
            origin_directories.append(os.path.join(crawl_output_path, o))


    with multiprocessing.Pool(PROCESSES) as p:
        results = list(
            tqdm(
                p.imap_unordered(run_analysis, origin_directories),
                leave=True,
                desc="Origins",
                total=len(origin_directories),
                position=0,
            )
        )
    
    for d in results:
        res.update(d)
 
    with open(pickle_path, 'wb') as outp:
        pickle.dump(res, outp)

if __name__ == '__main__':
    main()