import json
import re
import os
import shutil
import networkx as nx
from collections import defaultdict
import multiprocessing
import pandas as pd
from tqdm import tqdm
import time
from typing import Any
from utils import get_valid_directories

pd.set_option('display.max_rows', None)

MAX_WORKERS = 128
CRAWL_PATH = "/home/ubuntu/hwpg-ae/src/output/2025-01-13_080956"

def log_analyzer(path: str) -> dict[str, int]:
    """
    Analyze logs to count JS appearances.
    
    Args:
        path (str): Path to the log file.

    Returns:
        dict[str, int]: A dictionary of properties/events and their occurrence counts.
    """
    log_content = open(path, "r").read()
    d = defaultdict(int)

    for l in log_content.split("\n"):
        if l == "calling generatePageGraph":
            break

        if "[HWPG] {" in l:
            line = re.search(r'INFO:CONSOLE.*\[HWPG\] (.*}).*", source', l)
            if not line:
                # Not a logging line
                # print(f"ERROR: No log for {path} in line: {l[:500]}")
                continue

            try:
                json_data = json.loads(line[1])
            except:
                print(f"ERROR: Parsing json: {l}")
                continue

            # {'type': 'log', 'function': '[object CSSStyleDeclaration].item', 'args': [0]}
            if json_data["type"] != "log": continue

            if json_data["event"] in ["get", "set", "constructor"]:
                d[f"{json_data['property']}.{json_data['event']}"] += 1
            else:
                d[f"{json_data['property']}"] += 1
    return d

def pg_cleaner(G, edges_ids, edge_id):
    """
    Identify redundant logs based on edge relationships in the graph.

    Args:
        G: NetworkX graph object.
        edges_ids: Dictionary mapping edge IDs to edge details.
        edge_id: Current edge ID being processed.

    Returns:
        list: Redundant logs identified.
    """
    redundant_logs = list()
    idx = 1

    # check if parent 
    edge = edges_ids[edge_id]
    child = G.nodes().get(edge[1])
    parent = G.nodes().get(edge[0])
    
    # Go through the edges to find the result of the call
    while True:
        while edge_id-idx not in edges_ids:
            idx += 1
            if idx > edge_id:
                return []
            
        if edges_ids[edge_id-idx][2]["edge type"] == "js result":
            break
        idx += 1
        if idx > edge_id:
            return []
        
    # Traverse edges to identify redundant logs
    while True:                
        while edge_id-idx not in edges_ids:
                idx += 1
        
        try:
            edge_data = edges_ids[edge_id-idx]
        except:            
            print(f"ERROR: Edge {edge_id - idx} not found")
            for k in edges_ids:
                if k >= edge_id-idx-20 and k <= edge_id-idx+20:
                    print(str(edges_ids[k])[:200])
            break

        edge_value = edge_data[2].get("value")
        if not edge_value:
            break

        try:
            json_value = json.loads(edge_value)
        except json.JSONDecodeError:
            print("Error: break due to json")
            break

        if type(json_value) != type({}):
            break

        # Check for the Json Value as it indicates the logging of a call
        if "property" not in json_value:
            break

        breaker = True
        
        try:
            property = json_value["property"].replace("[object CSS]", "CSS")
            if property == child["method"]:
                breaker = False

            x = property + "." + json_value["event"]
            if x == child["method"]:
                breaker = False

            x = x.replace("Window.", "")
            if x == child["method"]:
                breaker = False
        except Exception as e:
            print(f"ERROR FOR {type(json_value)} {json_value}: {e}")
            print(child)
            break

        if breaker:
            # print("break due to false method")
            break

        parent_method = G.nodes().get(edge_data[0], {}).get("method")
        if parent_method != "JsonStringify":
            break

        redundant_logs.append(edge_value)
        idx += 2

    return redundant_logs[1:]

def pg_analyzer(path: str, standard_filter: list[str]) -> dict[str, int]:
    """
    Analyze the page graph file and count JS appearances.

    Args:
        path (str): Path to the graphml file.
        standard_filter (list[str]): List of standard methods to filter.

    Returns:
        dict[str, int]: Method counts from the page graph.
    """
    d = defaultdict(int)

    try:
        G = nx.read_graphml(path)
    except:
        print(f"Error parsing xml in {path}")
        return d


    edges = [x for x in G.edges(data=True)]
    edges = sorted(edges, key=lambda x:int(x[2]['id']))
    edges_ids = {int(x[2]['id']):x for x in edges}

    def standard_filter_helper(method):
        standard = method.split(".")[0]
        if standard not in standard_filter:
            return False
        # setTimeout was only added for artifacts evaluation
        if (standard == "Window" 
            and "getComputedStyle" not in method
            and "setTimeout" not in method):
            print(f"{method} is false")
            return False
        if method == "CSSStyleDeclaration.":
            return False    
        return True

    # For webAPI calls, look for the js call and add it to the called methods (d)
    for n in G.nodes(data=True):
        if n[1]["node type"] == "web API":
            for e in G.in_edges(n[0], data=True):
                if e[2]["edge type"] == "js call":
                    method = n[1]["method"]
                    if standard_filter_helper(method):
                        d[method] += 1
                        redundant_logs_res = pg_cleaner(G, edges_ids, int(e[2]['id']))
                        d[method] += len(redundant_logs_res)
    return d


def cleanup_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize method names in the dataframe.

    Args:
        df (pd.DataFrame): Input dataframe.

    Returns:
        pd.DataFrame: Cleaned dataframe.
    """
    df['Call'] = df['Call'].replace({'Window.CSSStyleSheet.constructor': 'CSSStyleSheet.constructor'})
    df['Call'] = df['Call'].replace({'Window.MessageChannel.constructor': 'MessageChannel.constructor'})
    df['Call'] = df['Call'].replace({'[object Window].MessageChannel.constructor': 'MessageChannel.constructor'})
    df['Call'] = df['Call'].replace({'[object Window].getComputedStyle': 'Window.getComputedStyle'})
    df['Call'] = df['Call'].replace({'.getComputedStyle': 'Window.getComputedStyle'})
    df['Call'] = df['Call'].replace({'[object CSS].escape': 'CSS.escape'})
    return df

def compare_one_origin(path: str) -> pd.DataFrame:
    """
    This method goes through all relevant logs of one origin directory and alayze.

    Args:
        path (str): Path to the origin directory.

    Returns:
        pd.DataFrame: Combined dataframe of results.
    """

    # == Analyze ground truth JS ==
    pg_log = os.path.join(path, "logs", "pagegraph.log")
    res = log_analyzer(pg_log)

    df_js = pd.DataFrame(list(res.items()), columns=['Call', 'Appearances JS'])
    df_js = cleanup_df(df_js)

    # == Analyze har replay JS ==
    har_pg_log = os.path.join(path, "mitmd_replay", "logs", "pagegraph.log")
    res = log_analyzer(har_pg_log)

    df_har = pd.DataFrame(list(res.items()), columns=['Call', 'Appearances HAR JS'])
    df_har = cleanup_df(df_har)

    # == Analyze warc replay JS ==
    warc_pg_log = os.path.join(path, "warc_replay", "logs", "pagegraph.log")
    res = log_analyzer(warc_pg_log)

    df_warc = pd.DataFrame(list(res.items()), columns=['Call', 'Appearances WARC JS'])
    df_warc = cleanup_df(df_warc)

    # == Analyze pagegraph ==
    graphml_files = list()
    for f in os.listdir(path):
        if f.endswith(".graphml"):
            graphml_files.append(os.path.join(path, f))
    
    if len(graphml_files) == 0:
        return

    standard_filter = [
       "MessageChannel",
        "MessagePort",
        "MediaList",
        "StyleSheet",
        "CSSStyleSheet",
        "StyleSheetList",
        "ProcessingInstruction",
        "CSSRuleList",
        "CSSRule",
        "CSSStyleRule",
        "CSSImportRule",
        "CSSGroupingRule",
        "CSSPageRule",
        "CSSNamespaceRule",
        "CSSStyleDeclaration",
        "HTMLElement",
        "SVGElement",
        "MathMLElement",
        "CSS",
        "Window"
    ]

    res = pg_analyzer(graphml_files[0], standard_filter)

    df_pg = pd.DataFrame(list(res.items()), columns=['Call', 'Appearances PG'])

    df_final = pd.merge(df_js, df_pg, on='Call', how='outer')
    df_final = pd.merge(df_final, df_har, on='Call', how='outer')
    df_final = pd.merge(df_final, df_warc, on='Call', how='outer')
    df_final = df_final.sort_values(by=['Call'])

    df_final.loc[len(df_final)] = ["Empty", 0, 0, 0, 0]

    origin = os.path.basename(path)
    df_final["origin"] = origin
    df_final['Appearances PG'] = df_final['Appearances PG'].infer_objects(copy=False).fillna(0)
    df_final['Appearances JS'] = df_final['Appearances JS'].infer_objects(copy=False).fillna(0)
    df_final['Appearances HAR JS'] = df_final['Appearances HAR JS'].infer_objects(copy=False).fillna(0)
    df_final['Appearances WARC JS'] = df_final['Appearances WARC JS'].infer_objects(copy=False).fillna(0)

    return df_final

def main():    
    """
    Main function to process all origins and generate a results CSV.
    """  
    crawl_output_path = CRAWL_PATH

    origin_directories = get_valid_directories(crawl_output_path, replay_warc=True, replay_har=True)

    with multiprocessing.Pool(MAX_WORKERS) as p:
        frames = list(
            tqdm(
                p.imap_unordered(compare_one_origin, origin_directories),
                leave=True,
                desc="Origins",
                total=len(origin_directories),
                position=0,
            )
        )
    
    result = pd.concat(frames)

    csv_file = f"js_results_{str(int(time.time()))}.csv"
    result.to_csv(csv_file, sep=',', index=False, encoding='utf-8')
    # from IPython import embed; embed()

if __name__ == "__main__":
    main()