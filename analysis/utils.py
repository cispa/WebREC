import os
import shutil
from typing import Any, List, Dict

def check_directory_validity(directory: str, replay_warc: bool=True, replay_har: bool=True) -> Dict[str, Any]:
    """
    Check the calidity of a directory.
    """

    result: dict[str, Any] = {
        "origin": os.path.basename(directory),
        "error": ""
    }

    # Check if we have WARC, HAR and PageGraph
    file_types = {".graphml": [], ".warc": [], ".har": []}

    for entry in os.listdir(directory):
        for file_type in file_types:
            if entry.endswith(file_type):
                file_types[file_type].append(entry)

    missing_file_types = [
        file_type for file_type, exists in file_types.items() if len(exists) != 1
    ]

    if missing_file_types:
        result["error"] = "Missing " + ", ".join(missing_file_types)
        return result

    if len(file_types[".graphml"]) > 1:
        result["error"] = "Multiple pagegraphs"
        return result
    
    if replay_warc:
        # Check for warc replay
        warc_replay_path = os.path.join(directory, "warc_replay")
        if not os.path.exists(warc_replay_path):
            result["error"] = "No warc replay directory"
            return result

        warc_graph = False
        for entry in os.listdir(warc_replay_path):
            if entry.endswith(".graphml"):
                warc_graph = True
                break

        if not warc_graph:
            result["error"] = "No warc replay graphml"
            return result
        
    if replay_har:
        # Check for mitm replay
        mitmd_replay_path = os.path.join(directory, "mitmd_replay")
        if not os.path.exists(mitmd_replay_path):
            result["error"] = "No mitmd replay directory"
            return result

        mitmd_graph = False
        for entry in os.listdir(mitmd_replay_path):
            if entry.endswith(".graphml"):
                mitmd_graph = True
                break

        if not mitmd_graph:
            result["error"] = "No mitmd replay graphml"
            return result
    
    return result

def get_valid_directories(crawl_output_path: str, replay_warc: bool = True, replay_har: bool = True) -> List[str]:
    """
    Get a list of valid directories from the given crawl output path.
    """

    origin_directories = []
    for entry in os.listdir(crawl_output_path):
        path = os.path.join(crawl_output_path, entry)
        if not os.path.isdir(path):
            continue

        validity = check_directory_validity(path, replay_warc=replay_warc, replay_har=replay_har)
        if validity["error"] == "":
            origin_directories.append(path)

    return origin_directories

def remove_broken_mitmd_directories(crawl_output_path, validities):
    for repo in validities:
        if repo["error"] == "No mitmd replay graphml":
            mitmd_path = os.path.join(crawl_output_path, repo["origin"], "mitmd_replay")
            print(mitmd_path)
            shutil.rmtree(mitmd_path)

def remove_broken_warc_directories(crawl_output_path, validities):
    for repo in validities:
        if repo["error"] == "No warc replay graphml":
            warc_path = os.path.join(crawl_output_path, repo["origin"], "warc_replay")
            print(warc_path)
            shutil.rmtree(warc_path)
