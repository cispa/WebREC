from typing import Any, List
import os
import sys
import signal
import time
import logging
import argparse
from multiprocessing import Pool, current_process
from tqdm import tqdm

from misc import start_wayback, start_mitmd_proxy, start_pagegraph, check_directory_validity
from config import BRAVE_EXEC_PATH, INITIALIZATION_BREAK

def run_task(path: str) -> None:
    """
    Runs a task to replay a WARC file for a specific origin.

    This function starts the wayback proxy and mitmdump proxy, then replays the WARC file
    and uses pagegraph to process the origin.

    Args:
        path (str): Path to the directory containing the WARC file for the origin.
    """
    scheme, hostname = os.path.basename(path).split("_")
    origin = scheme + "://" + hostname
    output_path = os.path.join(path, "warc_replay")
    os.makedirs(output_path)

    num = int(current_process().name.split("-")[1])
    
    # Set up logging
    log_file = os.path.join(output_path, f"./log-p{num}.txt")
    logging.basicConfig(filename=log_file, encoding="utf-8", level=logging.DEBUG)
    logging.info(f"Process {num}: {origin}")

    bin_dir = os.path.join(os.path.dirname(sys.executable))
    base_dir = os.path.dirname(os.path.realpath(__file__))

    log_dir = os.path.join(output_path, "logs")
    os.makedirs(log_dir)

    # Create WARC Collection
    port_warcp = 16000 + num
    warc_file = f"{path}/{hostname}.warc"
    p_warcp = start_wayback(port_warcp, warc_file, output_path, bin_dir)
    if p_warcp == -1:
        logging.error(f"Process {num}: Failed to start wayback proxy for {origin}")
        return

    # Run mitmd
    port_mitmd = 15000 + num
    mitm_script = os.path.join(base_dir, "js_injector.py")
    p_mitmd = start_mitmd_proxy(
        port_mitmd, port_warcp, output_path, "", bin_dir, mitm_script, set_hardump=False
    )

    time.sleep(INITIALIZATION_BREAK) # Allow time for proxies to initialize

    # Run page graph crawl
    start_pagegraph(
        port_mitmd, BRAVE_EXEC_PATH, output_path, origin, base_dir
    )

    # Shut everything down
    p_mitmd.send_signal(signal.SIGINT)
    p_mitmd.wait()
    p_warcp.send_signal(signal.SIGINT)
    p_warcp.wait()

def run_replay_warc(origin_directories: List[str], workers: int = 1) -> None:
    """
    Runs the WARC replay process for a list of origin directories using multiprocessing.

    Args:
        origin_directories (List[str]): List of directories containing WARC files to replay.
        workers (int): Number of worker processes to use for parallel replay.
    """
    with Pool(workers) as p:
        _ = list(
            tqdm(
                p.imap_unordered(run_task, origin_directories),
                leave=True,
                desc="Origins",
                total=len(origin_directories),
                position=0,
            )
        )

def parse_args() -> argparse.Namespace:
    """
    Parses command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description='Runs the experiment pipeline but replays responses from the collected HAR files.')
    parser.add_argument('--initial-crawl', type=str, default="",
                        help='Path of the initial crawl.')
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    origin_directories = list()
    crawl_path = os.path.abspath(args.initial_crawl)
    for f in os.listdir(crawl_path):
        path = os.path.join(crawl_path, f)
        if not os.path.isdir(path): continue
        validity = check_directory_validity(path)
        if validity["error"] != "": continue
        origin_directories.append(path)
    
    run_replay_warc(origin_directories)



if __name__ == "__main__":
    main()
