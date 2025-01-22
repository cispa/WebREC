from typing import Any, Dict, List
import os
import sys
import subprocess
import signal
import time
import logging
import shutil
from multiprocessing import Pool, current_process
from tqdm import tqdm
import json

from reporting import send_message
from misc import start_mitmd_proxy, start_warc_prox, start_pagegraph, check_run_completeness

from config import BRAVE_EXEC_PATH

def get_crux_list(output_path: str, yyyymm: str = "202311") -> List[Any]:
    """
    Reads and returns the curx list.
    
    Args:
        output_path (str): Path where output is stored.
        yyyymm (str): Timestamp in the format YYYYMM of the crux list.

    Returns:
        list: List of origins from the crux list or an empty list if not found.
    """
    output_path = os.path.dirname(output_path)
    crux_file = os.path.join(output_path, f"{yyyymm}.json")

    if os.path.exists(crux_file):
        with open(crux_file, "r") as f:
            rows = json.load(f)
            return rows
    return []

def setup_process(output_path: str) -> None:
    """
    Sets up the logging configuration for the current process.

    Args:
        output_path (str): Path where log files will be stored.
    """

    num = int(current_process().name.split("-")[1])
    log_file = os.path.join(output_path, f"./log-p{num}.txt")
    logging.basicConfig(filename=log_file, encoding="utf-8", level=logging.DEBUG)

def run_task_helper(input: Dict[str, str]) -> None:
    """
    Helper function to run a task for processing a specific origin.
    
    The helper starts all proxies (warcprox and mitmdump) first.
    In the next step, pagegraph-crawl (called WebREC in the paper) is used to
    crawl the origin and generate a pagegraph.
    For every HTML response, mitmdump injects a script element (via js_injector.py) to hook into JS calls.

    Args:
        input (dict): Dict containing the 'origin' and 'output_path' for the task.
    """

    origin = input["origin"]
    output_path = input["output_path"]

    num = int(current_process().name.split("-")[1])

    logging.info(f"Process {num}: {origin}")

    scheme, hostname = origin.split("://")

    output_path = os.path.join(output_path, f"{scheme}_{hostname}")
    bin_dir = os.path.join(os.path.dirname(sys.executable))
    base_dir = os.path.dirname(os.path.realpath(__file__))
    os.makedirs(os.path.join(output_path, "logs"))

    # Setup warcprox for creating WARC files
    port_warcp = 16000 + num
    p_warcp = start_warc_prox(port_warcp, output_path, hostname, bin_dir)

    # Setup mitmproxy for creating HAR files. 
    # It also injects our hooking JS.
    port_mitmd = 15000 + num
    mitm_script = os.path.join(base_dir, "js_injector.py")
    p_mitmd = start_mitmd_proxy(
        port_mitmd, port_warcp, output_path,
        hostname, bin_dir, mitm_script
    )

    time.sleep(5) # Allow some time for proxies to be fully started

     # Run page graph crawl
    start_pagegraph(
        port_mitmd, BRAVE_EXEC_PATH,
        output_path, origin, base_dir
    )

    # Shut everything down
    p_mitmd.send_signal(signal.SIGINT)
    p_mitmd.wait()
    p_warcp.send_signal(signal.SIGINT)
    p_warcp.wait()

def run_task(input: Dict[str, str]) -> None:
    """ 
    Runs a task to crawl an origin, with retries in case of failure.

    Args:
        input (dict): Dictionary containing the 'origin' and 'output_path'.
    """
    scheme, hostname = input["origin"].split("://")
    output_path = os.path.join(input["output_path"], f"{scheme}_{hostname}")

    attempt = 0
    max_retries = 3

    # Run the task and check if it was completed successfully
    while 1:
        run_task_helper(input)
        complete = check_run_completeness(input)
        if complete:
            break

        if attempt < max_retries:
            shutil.move(output_path, output_path + "_failed_attempt_" + str(attempt))
            attempt += 1
            time.sleep(30)
            logging.info(f"Retry {hostname}")
        else:
            logging.info(f"Failed {hostname} due to missing files")
            break


def check_disk_space() -> None:
    """Check disk space and report it after the crawl finished running."""
    p = subprocess.run("df", capture_output=True, shell=True)
    send_message(str(p.stdout))


def run_crawl(origin_list: List[str] = [], output_path: str = "./output", workers: int = 1) -> None:
    """
    Schedules the crawls for a list of origins using multiprocessing.

    Args:
        origin_list (list): List of origins to process.
        output_path (str): Path where output will be stored.
        workers (int): Number of workers invloved in multiprocessing.
    """

    # If there is no origin provided, load the crux list
    if len(origin_list) == 0:
        origin_list = get_crux_list(output_path)
        origin_list = [r["origin"] for r in origin_list if int(r["rank"]) <= 10_000]

    # Prepare init args and start the pool
    inputs = [{"origin": o, "output_path": output_path} for o in origin_list]
    with Pool(workers, initializer=setup_process, initargs=[output_path]) as p:
        _ = list(
            tqdm(
                p.imap_unordered(run_task, inputs),
                leave=True,
                desc="Origins",
                total=len(origin_list),
                position=0,
            )
        )

    # check_disk_space()
