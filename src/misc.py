from typing import Any, Dict, List
import os
import subprocess
import logging

from config import JS_HOOKING

def start_warc_prox(port_warcp: int, output_path: str, hostname: str, bin_dir: str) -> subprocess.Popen:
    """
    Starts the WARC proxy to create WARC files.

    Args:
        port_warcp (int): The port on which the WARC proxy should listen.
        output_path (str): Path to store the output WARC files.
        hostname (str): The hostname for the WARC files.
        bin_dir (str): Directory of the executable binaries.

    Returns:
        subprocess.Popen: The process running the WARC proxy.
    """   
    logfile_warcp = open(os.path.join(output_path, "logs", f"warcp_{port_warcp}.log"), "a")
    db_name_warcp = os.path.join(output_path, "warcprox.sqlite")
    warc_dir = output_path
    warc_name = hostname

    cmd = [
        os.path.join(bin_dir, "warcprox"),
        "--port", f"{port_warcp}",
        "--dir", warc_dir,
        "--warc-filename", warc_name,
        "--stats-db-file", db_name_warcp,
        "--dedup-db-file", db_name_warcp,
    ]

    return subprocess.Popen(cmd, stdout=logfile_warcp, stderr=logfile_warcp)

def start_mitmd_proxy(
        port_mitmd: int,
        port_warcp: int,
        output_path: str,
        hostname: str,
        bin_dir: str,
        mitm_script: str,
        set_hardump: bool = True
    ) -> subprocess.Popen:
    """
    Starts the mitmdump proxy to create HAR files and inject JS.

    Args:
        port_mitmd (int): The port on which the mitmdump should listen.
        port_warcp (int): Port for upstream traffic.
        output_path (str): Path to store HAR and related data.
        hostname (str): The target hostname.
        bin_dir (str): Directory of the executable binaries.
        mitm_script (str): Path to the mitmproxy script.
        set_hardump (bool): Whether dump trafic in HAR.

    Returns:
        subprocess.Popen: The process running the mitmdump proxy.
    """
    db_name_mitmd = os.path.join(output_path, "mitmdump.db")
    har_name = os.path.join(output_path, f"{hostname}.har")

    cmd = [
        "--mode", f"upstream:http://localhost:{port_warcp}",
        "--set", "ssl_insecure=true",
    ]

    if JS_HOOKING:
        cmd += ["-s", mitm_script]

    if set_hardump:
        cmd += [
            "--set", f"hardump={har_name}",
            "--set", f"db_name={db_name_mitmd}",
        ]
        
    return start_mitmd(port_mitmd, output_path, bin_dir, add_cmd=cmd)

def start_mitmd_replay(port_mitmd: int, output_path: str, bin_dir: str, har_file: str) -> subprocess.Popen:
    """
    Starts the mitmdump proxy for replaying a HAR file.

    Args:
        port_mitmd (int): The port on which the mitmdump should listen.
        output_path (str): Path to store logs.
        bin_dir (str): Directory of the executable binaries.
        har_file (str): HAR file to replay.

    Returns:
        subprocess.Popen: The process running the mitmdump replay.
    """
    cmd = [
        "--set", "connection_strategy=lazy",
        "--server-replay", har_file,
        "--server-replay-extra", "kill",
    ]

    return start_mitmd(port_mitmd, output_path, bin_dir, add_cmd=cmd)

def start_mitmd(port_mitmd: int, output_path: str, bin_dir: str, add_cmd: List[str]) -> subprocess.Popen:
    """
    Starts the mitmdump proxy process.

    Args:
        port_mitmd (int): The port on which the mitmdump should listen.
        output_path (str): Path to store logs.
        bin_dir (str): Directory of the executable binaries.
        add_cmd (list): Additional command arguments.

    Returns:
        subprocess.Popen: The process running the mitmdump proxy.
    """
    logfile_mitmd = open(os.path.join(output_path, "logs", f"mitmd_{port_mitmd}.log"), "a")

    cmd = [
        os.path.join(bin_dir, "mitmdump"),
        "--listen-port", f"{port_mitmd}"
    ] + add_cmd

    return subprocess.Popen(cmd, stdout=logfile_mitmd, stderr=logfile_mitmd)

def start_wayback(port_warcp: int, warc_file: str, output_path: str, bin_dir: str) -> subprocess.Popen:
    """
    Starts the wayback proxy for replaying a WARC file.

    Args:
        port_warcp (int): Port for wayback.
        warc_file (str): Path to the WARC file that is served.
        output_path (str): Path to store logs and other files.
        bin_dir (str): Directory of the executable binaries.

    Returns:
        subprocess.Popen: The process running the wayback proxy.
    """    
    logfile_warcp = open(os.path.join(output_path, "logs", f"warcp_{port_warcp}.log"), "a")
    # db_name_warcp = os.path.join(output_path, "warcprox.sqlite")

    # Create WARC Collection
    from pywb.manager.manager import CollectionsManager
    try:
        colls_dir = os.path.join(output_path, "collections")
        coll_manager = CollectionsManager("coll", colls_dir=colls_dir, must_exist=False)
        coll_manager.add_collection()
        coll_manager.add_warcs([warc_file])
    except Exception as e:
        logging.error(f"{warc_file} CollectionsManager ERROR: \n{e}")
        return -1

    cmd = [
        os.path.join(bin_dir, "wayback"),
        "--debug",
        "--threads", "1",
        "--directory", output_path,
        "--port", str(port_warcp),
        "--proxy", "coll",
    ]
    return subprocess.Popen(cmd, stdout=logfile_warcp, stderr=logfile_warcp)

def start_pagegraph(port_mitmd: int, brave_exec_path: str, output_path: str, origin: str, base_dir: str) -> None:
    """
    Starts the pagegraph crawl process (called WebREC in the paper).

    pageggraph crawl can also create screenshots.
    We don't need it for our experiments and due to disk space we don't store it.

    Args:
        port_mitmd (int): Port to mitmdump to connect to.
        brave_exec_path (str): Path to Brave browser executable.
        output_path (str): Path to store pagegraph output.
        origin (str): URL to crawl.
        base_dir (str): Base directory of the project.
    """
    pagegraph_dir = output_path
    log_dir = os.path.join(output_path, "logs")
    logfile_pagegraph = open(os.path.join(log_dir, "pagegraph.log"), "a")

    print("Run Brave now: " + brave_exec_path)
    pg_crawl_cmds = [
        "npm", "run", "crawl", "--", "-b", brave_exec_path, "-u", origin,
        "-t","10", "-o", pagegraph_dir,
        "--extra-args", f'["--ignore-certificate-errors", "--proxy-server=http://127.0.0.1:{port_mitmd}"]',
        # "--auto-open-devtools-for-tabs"
    ]

    # Dirty version fix
    if ("--debug" in open(os.path.join(base_dir, "pagegraph-crawl", "src", "run.ts"), "r").read()):
        pg_crawl_debug = ["--debug", "debug"]
    else:
        pg_crawl_debug = ["--logging", "verbose"]

    try:
        subprocess.run(
            pg_crawl_cmds + pg_crawl_debug,
            stdout=logfile_pagegraph,
            stderr=logfile_pagegraph,
            cwd=os.path.join(base_dir, "pagegraph-crawl"),
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        logging.error(f"{origin} pagegraph-crawl timed out")

def check_run_completeness(input: Dict[str, str]) -> bool:
    """
    Check the crawl for completeness
    
    We check if a crawl created a pagegraph activity graph (.graphml),
    a warc file and a har file. Only if all three exist, the crawl
    was successful.
    
    Args:
        input (dict): Dictionary containing 'origin' and 'output_path'.

    Returns:
        bool: True if all required files are present, False otherwise.
    """

    origin = input["origin"]
    output_path = input["output_path"]
    scheme, hostname = origin.split("://")
    output_path = os.path.join(output_path, f"{scheme}_{hostname}")

    # Check if we have WARC, HAR and PageGraph
    file_types = {".graphml": "", ".warc": "", ".har": ""}
    for entry in os.listdir(output_path):
        for file_type in file_types:
            if entry.endswith(file_type):
                file_types[file_type] = entry

    missing_file_types = [
        file_type for file_type, exists in file_types.items() if not exists
    ]

    return missing_file_types == []

def check_directory_validity(directory: str, mitmd_replay: bool = False, warc_replay: bool = False) -> Dict[str, Any]:
    """
    Checks the validity of a directory for crawling.

    Args:
        directory (str): The directory to check.
        mitmd_replay (bool): Check for mitmd replay existence.
        warc_replay (bool): Check for warc replay existence.

    Returns:
        dict: A dictionary with validity status and error messages.
    """

    result: dict[str, Any] = {
        "origin": os.path.basename(directory),
        "error": ""
    }

    # Check if we have WARC, HAR and PageGraph
    file_types = {".graphml": [], ".warc": [], ".har": []}

    for entry in os.listdir(directory):
        # print(entry)
        if entry == "warc_replay" and warc_replay:
            result["error"] = "Skipping, because Warc replay already exists"
            return result

        if entry == "mitmd_replay" and mitmd_replay:
            result["error"] = "Skipping, because Mitm replay already exists"
            return result

        for file_type in file_types:
            if entry.endswith(file_type):
                file_types[file_type].append(entry)

    missing_file_types = [
        file_type for file_type, exists in file_types.items() if len(exists) != 1
    ]

    if missing_file_types:
        result["error"] = "Missing " + ", ".join(missing_file_types)
        return result

    return result

def get_origin_directories(initial_crawl_output_path: str, mitmd_replay: bool = False, warc_replay: bool = False) -> List[str]:
    """
    Retrieves a list of valid origin directories.

    Args:
        initial_crawl_output_path (str): Base path containing crawl directories.
        mitmd_replay (bool): Check for mitmd replay existence.
        warc_replay (bool): Check for warc replay existence.

    Returns:
        list: List of valid origin directories.
    """
    origin_directories = list()
    for f in os.listdir(initial_crawl_output_path):
        path = os.path.join(initial_crawl_output_path, f)
        if not os.path.isdir(path): continue
        validity = check_directory_validity(path, mitmd_replay=mitmd_replay, warc_replay=warc_replay)
        if validity["error"] != "": continue
        origin_directories.append(path)
    
    return origin_directories