from utils import get_valid_directories
import os
from typing import Tuple, List, Dict, Any
import multiprocessing
from tqdm import tqdm
import pandas as pd
import time
import sys

# Add pagegraph-query
sys.path.insert(0, 'pagegraph-query')
import pagegraph.commands
import pagegraph.serialize
import pagegraph

MAX_WORKERS = 16

CRAWL_PATH = "/home/ubuntu/hwpg-ae/src/output/2025-01-12_203257"

def handle_pg_log(path: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Parse the pagegraph log file to extract API traces, false traces, and false 'on' traces.
    """

    with open(path, "r", errors='ignore') as f:
        api_traces, false_traces, false_on_traces = [], [], []

        for line in f.readlines():
            line = line.strip()
            if "INFO:CONSOLE" in line:
                if '"tag":"inline_handler' in line:
                    api_traces.append(line)
                if '"tag":"prog_handler' in line:
                    false_traces.append(line)
                if '"tag":"on_attr_handler' in line:
                    false_on_traces.append(line)

    return api_traces, false_traces, false_on_traces

def is_dom_excluded_element(node) -> bool:
    if node.type_name() != 'HTML element':
        return False
    
    if node.tag_name() in ["VIDEO", "AUDIO", "IMG", "INPUT"]:
        # The selected elements (input with type=image) can start a request even if not part of the page DOM
        if "request start" in [e.edge_type().value for e in node.outgoing_edges()]:
            return True
    
    return False
        

def check_pg(graphml_file) -> List[List[str]]:
    pg = pagegraph.graph.from_path(graphml_file, True)
    event_listeners = pg.event_listeners()
    
    result = list()
    for event_listener in event_listeners:
        # print(event_listener.describe())
        if event_listener.is_inline_event_handler():            
            creator = event_listener.creator
            if creator.type_name() == 'parser':
                continue
            
            # print(event_listener)
            if not event_listener.is_or_was_in_dom():
                if is_dom_excluded_element(event_listener.element):                
                    resource_events = [
                        "load",
                        "loadstart",
                        "progress",
                        "suspend",
                        "durationchange",
                        "loadedmetadata",
                        "loadeddata",
                        "error",
                        "canplay",
                        "canplaythrough"
                    ]
                    if event_listener.event in resource_events:
                        result.append([True])
                    continue

                continue

            result.append([True])
    
    return result


def run(path: str, replay_warc: bool=True, replay_har: bool=True) -> Dict[str, Any]:
    """
    Process a given directory to analyze HAR, WARC and pagegraph files.
    """

    directory = os.path.basename(path)
    scheme, domain = directory.split("_")[:2]
    origin = f"{scheme}://{domain}"

    res = {"origin": directory, "PG": 0, "GT": 0, "False GT":0, "False on GT":0, "WARC": 0, "HAR": 0, "error": ""}

    print(origin)

    # Create all paths for the log files
    pg_log_file = os.path.join(path, 'logs', 'pagegraph.log')
    pg_har_log_file = os.path.join(path, 'mitmd_replay', 'logs', 'pagegraph.log')
    pg_warc_log_file = os.path.join(path, 'warc_replay', 'logs', 'pagegraph.log')
    graphml_file = next((os.path.join(path, f) for f in os.listdir(path) if f.endswith(".graphml")), "")

    # Try to generate the pagegraph results
    try:
        pg_res = check_pg(graphml_file)
    except Exception as e:
        res["error"] = e
        print(f"ERROR: {e}")
        return res
    
    # pg_res = []
    api_traces, false_traces, false_on_traces = handle_pg_log(pg_log_file)
    res["PG"] = len(pg_res)
    res["GT"] = len(api_traces)
    res["False GT"] = len(false_traces)
    res["False on GT"] = len(false_on_traces)        

    for trace in api_traces:
        print(trace)
        print("---")

    print("PG", len(pg_res))
    print("GT", len(api_traces))

    if replay_har:
        api_traces_har, false_traces_har, false_on_traces_har = handle_pg_log(pg_har_log_file)
        res["HAR"] = len(api_traces_har)
        print("HAR", len(api_traces_har))
    else:
        res["HAR"] = 0

    if replay_warc:
        api_traces_warc, false_traces_warc, false_on_traces_warc = handle_pg_log(pg_warc_log_file)
        res["WARC"] = len(api_traces_warc)
        print("WARC", len(api_traces_warc))
    else:
        res["WARC"] = 0

    return res
    
def process_results(results: List[Dict[str, str]]) -> pd.DataFrame:
    """
    Process the results from the multiprocessing into a DataFrame.
    """

    # Tranform all results from the results list into a dict for the pandas df.
    keys = ["origin", "GT", "False GT", "False on GT", "PG", "WARC", "HAR", "error"]
    df_dict = {key: [result[key] for result in results] for key in keys}
    
    return pd.DataFrame(df_dict)


def main_for_tester() -> None:
    """
    Main function to coordinate the processing, and analysis for the tests.
    """
    test_output = "./event-handler-tester/output/"
    df_list = list()
    for d in tqdm(os.listdir(test_output)):
        crawl_output_path = os.path.join(test_output, d)
        origin_directory = get_valid_directories(crawl_output_path, replay_warc=False, replay_har=False)[0]
        print(origin_directory)
        result = run(origin_directory, replay_har=False, replay_warc=False)

        # Process results into DataFrame
        # df = process_results(results)
        result["origin"] = crawl_output_path.split("/")[-1]
        print(result)   
        df = pd.DataFrame(result, index=[0])
        df_list.append(df)
    
    csv_file = f"./event-handler-tester/results_{str(int(time.time()))}.csv"

    df_summary = pd.concat(df_list)
    # df_summary.to_csv(csv_file, sep=',', index=False, encoding='utf-8')
    print(df_summary)

def main() -> None:
    """
    Main function to coordinate the processing, and analysis.
    """
    crawl_output_path = CRAWL_PATH
    origin_directories = get_valid_directories(crawl_output_path, replay_warc=True, replay_har=True)
    print(origin_directories)
    
    with multiprocessing.Pool(MAX_WORKERS) as p:
        results = list(
            tqdm(
                p.imap_unordered(run, origin_directories),
                leave=True,
                desc="Origins",
                total=len(origin_directories),
                position=0,
            )
        )

    # Process results into DataFrame
    df = process_results(results)

    csv_file = f"./csp_results_{str(int(time.time()))}.csv"
    df.to_csv(csv_file, sep=',', index=False, encoding='utf-8')

    print(df)

    print("False")
    print(df[df["False GT"] > 0])
    print("False on*", len(df[df["False on GT"] > 0]))
    print("GT:", len(df[df["GT"] > 0]))
    print("PG:", len(df[df["PG"] > 0]))
    print("GT false with consequences:", len(df[(df["GT"] == 0) & (df["False GT"] > 0)]))
    print("GT false without consequences:", len(df[(df["GT"] > 0) & (df["False GT"] > 0)]))

main()
# main_for_tester()

