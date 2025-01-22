from warcio.archiveiterator import ArchiveIterator
from haralyzer import HarParser
import datetime
import time
from tqdm import tqdm
from typing import Any
from multiprocessing import Pool
import networkx as nx
from adblockparser import AdblockRules
import tldextract
import pandas as pd
import json
import os
import re
from collections import Counter
from utils import get_valid_directories

CRAWL_PATH = "/home/ubuntu/hwpg-ae/src/output/2025-01-16_103056"

def protocol_majority_vote(path, url):
    # Dirty fix for temporary pg issue
    log = open(os.path.join(path, "logs", "pagegraph.log")).read()
    url_sp = url.split("://", 1)[1]
    prot = Counter(re.findall(r"(https?://)" + url_sp.replace("?", r"\?"), log)).most_common(1)[0][0]
    return prot + url_sp

def run(path):
    """
    Process a single crawl directory to analyze WARC, HAR, and GraphML files.

    Args:
        path (str): Path to the crawl data directory.

    Returns:
        pd.DataFrame: Dataframe containing processed URL data.
    """

    domain = os.path.basename(path).split("_")[1]
    print(f"Processing domain: {domain}")

    # Define file paths
    warc_file = f"{path}/{domain}.warc"
    har_file = f'{path}/{domain}.har'
    graphml_file = ""
    for f in os.listdir(path):
        if f.endswith(".graphml"):
            graphml_file = f"{path}/{f}"
    
    # Calculate end timestamp based on GraphML filename
    pg_end_ts = datetime.datetime.fromtimestamp(int(graphml_file.replace(".graphml", "").split("_")[-1]))
    pg_end_ts += datetime.timedelta(hours=0, seconds=10)
    pg_end_ts = pg_end_ts.replace(tzinfo=None)

    # === WARC File Analysis ===
    warc_urls = list()
    with open(warc_file, 'rb') as stream:
        for record in ArchiveIterator(stream):
            # PG only stores with response.
            if record.rec_type in ['response', 'revisit']:
                uri = record.rec_headers.get_header('WARC-Target-URI')
                ts = record.rec_headers.get_header('WARC-Date')
                ts_dt = datetime.datetime.fromisoformat(ts[:-1])
                ts_dt = ts_dt.replace(tzinfo=None)

                if ts_dt > pg_end_ts: continue
                warc_urls.append(uri)

    # === HAR File Analysis ===
    har_urls = list()
    har_redirects = set()
    har_prefetch = set()
    har_preflight = set()
    har_csp_report = set()
    har_websocket = set()

    with open(har_file, 'r') as f:
        har_parser = HarParser(json.loads(f.read()))
        for e in har_parser.pages[0].entries:
            sec_fetch_dest = [h["value"] for h in e["request"]["headers"] if h["name"] == 'Sec-Fetch-Dest']
            sec_purpose = [h["value"] for h in e["request"]["headers"] if h["name"] == 'Sec-Purpose']
            upgrade_req = [h["value"] for h in e["request"]["headers"] if h["name"] == 'Upgrade']
            access_cntrl_req_meth = [h["value"] for h in e["request"]["headers"] if h["name"] == 'Access-Control-Request-Method']

            additional_info = ""

            if e["response"]["redirectURL"]:
                if "document" in sec_fetch_dest:
                    har_redirects.add(e.url)
                    additional_info = "har_redirects"
                    print("Redirect", e.url)
                elif "iframe" in sec_fetch_dest:
                    har_redirects.add(e.url)
                    additional_info = "har_redirects_iframe"
                    print("Iframe Redirect", e.url)
                else:
                    pass

            if "serviceworker" in sec_fetch_dest:
                print("serviceworker", e.url)
                continue
            if "report" in sec_fetch_dest:
                print("report", e.url)
                print("Content Type:", [h["value"] for h in e["request"]["headers"] if h["name"] == 'Content-Type'])
                har_csp_report.add(e.url)
                additional_info = "har_csp_report"
                # continue
            if "prefetch" in sec_purpose:
                print("prefetch", e.url)
                har_prefetch.add(e.url)
                additional_info = "har_prefetch"
                # continue
            if "websocket" in upgrade_req:
                print("websocket upgrade", e.url)
                additional_info = "har_websocket"
                har_websocket.add(e.url)

            if len(access_cntrl_req_meth) > 0:
                print("!!!! Pre fligth", e.url)
                additional_info = "har_preflight"
                har_preflight.add(e.url)
                # continue

            uri = e.url
            ts_dt = e.startTime
            ts_dt += datetime.timedelta(milliseconds=e.time)
            ts_dt = ts_dt.replace(tzinfo=None)            
            
            if ts_dt > pg_end_ts: continue
            har_urls.append((uri, additional_info))

    # === Pagegraph Analysis ===
    pg_urls = list()
    pg_no_cont = set()
    try:
        G = nx.read_graphml(graphml_file) 
    except:
        return None
    
    edges = G.edges(data=True)
    for e in edges:
        t = e[2]['edge type']
        if t in ["request start", "request redirect"]:
            n = G.nodes().get(e[1])

            # Check if the request was ever finished via a redirect or completed.
            # Otherwise the request does not appear in HAR
            continue_req = [
                out_e for out_e in G.out_edges(e[1], data=True)
                if out_e[2]['edge type'] in ["request redirect", "request complete", "request error"]
            ]
            if len(continue_req) == 0:
                pg_no_cont.add(n["url"])
                # print("!!! Filtered out because no continue req:", n["url"])
                # continue

            url = protocol_majority_vote(path, n["url"])
            pg_urls.append(url)


    for n in G.nodes(data=True):
        if n[1]["node type"] == "DOM root" and "url" in n[1] and n[1]["url"].startswith("http"):

            # Check if this node was ever added to the strcuture.
            # It could be that an iframe node was created multiple times but never added to the structure -> no request
            added_to_structure = False
            for e in G.in_edges(n[0], data=True):
                # We have two options here
                # 1. The edge type is structure. This means, the node was added
                if e[2]["edge type"] == "structure":
                    added_to_structure = True
                    break

                # 2. The edge type is only create. Then, we check the parent node type.
                # Parser sometimes creates nodes without the structure edge, still adding them to DOM.
                if e[2]["edge type"] in ["create", "create node"]:
                    parent = G.nodes().get(e[0])
                    if parent["node type"] == "parser":
                        added_to_structure = True
                        break
                    else:
                        print("Parent:")
                        print(str(parent)[:200])

            if added_to_structure:
                print("Add the following because added to structure:", n[1]["url"])
                url = protocol_majority_vote(path, n[1]["url"])
                pg_urls.append(url)
            
    # Merge together
    pg_urls = [u for u in pg_urls if u.startswith("http")]
    har_urls = [u for u in har_urls if "brave" not in u[0]]
    warc_urls = [u for u in warc_urls if "brave" not in u]

    res = {
        "url": list(),
        "source": list(),
        "additional_info": list(),
        "url_site": list()
    }

    har_urls_urls = [u[0] for u in har_urls]
    print("HAR, but not PG", set(har_urls_urls) - har_redirects - set(pg_urls))
    print("PG, but not HAR", set(pg_urls) - set(har_urls_urls))
    
    for u in pg_urls:
        if not u.startswith("http"): continue
        res["url"].append(u)
        url_extract = tldextract.extract(u)
        res["url_site"].append(f"{url_extract.domain}.{url_extract.suffix}")
        res["source"].append("PG")
        if u in pg_no_cont:
            res["additional_info"].append("pg_no_cont")
        else:
            res["additional_info"].append("")

    for u in har_urls:
        if "brave" in u: continue
        res["url"].append(u[0])
        url_extract = tldextract.extract(u[0])
        res["url_site"].append(f"{url_extract.domain}.{url_extract.suffix}")
        res["source"].append("HAR")
        res["additional_info"].append(u[1])

    for u in warc_urls:
        if "brave" in u: continue
        res["url"].append(u)
        url_extract = tldextract.extract(u)
        res["url_site"].append(f"{url_extract.domain}.{url_extract.suffix}")
        res["source"].append("WARC")
        res["additional_info"].append("")

    df_final = pd.DataFrame(res)

    origin = os.path.basename(path)
    df_final["origin"] = origin

    pg_origin = "_".join(graphml_file.split("page_graph_")[1].split("_")[:-2]).replace("___", "://").replace("_", ".")
    if pg_origin[-1].isdigit():
        # fix port
        pg_origin = ".".join(pg_origin.split(".")[:-1]) + ":" + pg_origin.split(".")[-1]


    df_final["pg_origin"] = pg_origin

    pg_origin_extract = tldextract.extract(pg_origin)
    df_final["site"] = f"{pg_origin_extract.domain}.{pg_origin_extract.suffix}"
    
    print(df_final)
    return df_final


def export_redirect_chains(path):
    schema = os.path.basename(path).split("_")[0]
    domain = os.path.basename(path).split("_")[1]
    origin = schema + "://" + domain

    print(domain)
    har_file = f'{path}/{domain}.har'

    with open(har_file, "r") as f:
        har_parser = HarParser(json.loads(f.read()))

    chain = [origin]
    while True:
        redirect_url = ""
        found = False
        for idx, e in enumerate(har_parser.pages[0].entries):
            if e.url == chain[-1]:
                found = True
                print(idx, e)
                redirect_url = e.response.redirectURL
                if redirect_url != "":
                    chain.append(redirect_url)
                break
        
        if not found:
            for idx, e in enumerate(har_parser.pages[0].entries):
                if e.url == chain[-1] + "/":
                    print(idx, e)
                    redirect_url = e.response.redirectURL
                    if redirect_url != "":
                        chain.append(redirect_url)
                    break
        
        if redirect_url == "":
            break
            
    return {"domain": domain, "chain": chain}

def get_origin(path):
    domain = os.path.basename(path).split("_")[1]
    graphml_file = ""
    for f in os.listdir(path):
        if f.endswith(".graphml"):
            graphml_file = f"{path}/{f}"
    G = nx.read_graphml(graphml_file)
    
    origin = ""
    for n in G.nodes(data=True):
        if n[1]["node type"] == "DOM root":
            if "url" in n[1] and n[1]["url"].startswith("http"):
                origin = n[1]["url"]
                break

    return path, origin

def load_tracking_list_rules(path):
    # Load EasyList rules from a file or a URL
    tracker_list = open(path, "r").read()
    raw_rules = tracker_list.splitlines()
    return [rule for rule in raw_rules if not rule.startswith("!")]

easylist_rules = load_tracking_list_rules("./easylist.txt")
easyprivacy_rules = load_tracking_list_rules("./easyprivacy.txt")
adblock_list_rules = AdblockRules(easylist_rules)
adblock_privacy_rules = AdblockRules(easyprivacy_rules)

def run_blocklist(url):
    return url, adblock_list_rules.should_block(url), adblock_privacy_rules.should_block(url)

def main():
    """
    Main function to process crawl directories and export results.
    """
    crawl_output_path = CRAWL_PATH
    origin_directories = get_valid_directories(crawl_output_path, replay_warc=False, replay_har=False)

    frames = list()
    with Pool(6) as p:
        frames = list(
            tqdm(
                p.imap_unordered(run, origin_directories),
                leave=True,
                desc="Origins",
                total=len(origin_directories),
                position=0,
            )
        )

    result = pd.concat(frames)

    csv_time = str(int(time.time()))
    csv_file = f"requests_results_{csv_time}.csv"
    result.to_csv(csv_file, sep=',', index=False, encoding='utf-8')

    # Create blocklist csv
    urls = list(set(result["url"]))
    with Pool(6) as p:
        blocklist_result = list(
            tqdm(
                p.imap_unordered(run_blocklist, urls),
                leave=True,
                desc="URLs",
                total=len(urls),
                position=0,
            )
        )
    
    blocklist_dict = {x[0]:[x[1], x[2]] for x in blocklist_result}
    result["easylist"] = [blocklist_dict[url][0] for url in result["url"]]
    result["easyprivacy"] = [blocklist_dict[url][1] for url in result["url"]]
    result["third_party"] = result["site"] != result["url_site"]
    csv_file = f"requests_results_{csv_time}_blocklists.csv"
    result.to_csv(csv_file, sep=',', index=False, encoding='utf-8')

if __name__ == "__main__":
    main()