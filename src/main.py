from typing import Any, Dict, List
import os
import sys
import subprocess
from datetime import datetime
import argparse

from crawl import run_crawl
from misc import get_origin_directories
from replay_warc import run_replay_warc
from replay_har import run_replay_har

def setup(output_path: str = "./output") -> None:
    """
    Sets up the environment and checks dependencies before running crawls.

    This function checks if necessary dependencies like 'warcprox', 'mitmdump', 
    'npm', and 'git' are installed. It also clones and sets up the 
    'pagegraph-crawl' repository if not already present and creates the output 
    directory.

    Args:
        output_path (str): Path where output will be stored.
    """
    bin_dir = os.path.join(os.path.dirname(sys.executable))

    # Check for warcprox and mitmdump installation
    if not os.path.exists(os.path.join(bin_dir, "warcprox")):
        print("warcprox does not exist in your env and needs to be installed.")
        sys.exit(-1)
    if not os.path.exists(os.path.join(bin_dir, "mitmdump")):
        print("mitmdump does not exist in your env and needs to be installed.")
        sys.exit(-1)

    # Check for npm installation
    try:
        null = open("/dev/null", "w")
        subprocess.Popen("npm", stdout=null, stderr=null)
        null.close()
    except OSError:
        print("npm does not exist and needs to be installed.")
        sys.exit(-1)

    # Check for git installation
    try:
        null = open("/dev/null", "w")
        subprocess.Popen("git", stdout=null, stderr=null)
        null.close()
    except OSError:
        print("git does not exist and needs to be installed.")
        sys.exit(-1)

    # Clone and setup the pagegraph-crawl repository
    base_dir = os.path.dirname(os.path.realpath(__file__))
    if not os.path.exists(os.path.join(base_dir, "pagegraph-crawl")):
        print("Cloning pagegraph crawl")
        subprocess.call(
            [
                "git",
                "clone",
                "https://github.com/brave/pagegraph-crawl.git",
                os.path.join(base_dir, "pagegraph-crawl"),
            ]
        )

        subprocess.call(
            ["npm", "install"], cwd=os.path.join(base_dir, "pagegraph-crawl")
        )
        subprocess.call(
            ["npm", "run", "build"], cwd=os.path.join(base_dir, "pagegraph-crawl")
        )

    # Ensure the output path is not already in use
    if os.path.exists(output_path):
        print(
            "The following path already exists and cannot be used for output:\n",
            output_path,
        )
        sys.exit(-1)
    else:
        os.makedirs(output_path)


def clean() -> None:
    """
    Terminates running processes related to mitmproxy, warcprox, Xvfb, and Brave browser.
    """
    for p in ["mitm", "warc", "Xvfb", "brave"]:
        subprocess.call(["pkill", "-f", p])

def parse_args() -> argparse.Namespace:
    """
    Parses command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description='Crawls and collects pagegraph, HAR and WARC files for a list of domains.')
    parser.add_argument('--output', type=str, default="output",
                        help='output path to store archives')
    parser.add_argument('--workers', type=int, default=1,
                        help='number of workers')
    parser.add_argument('--origins', type=str, nargs='*', default=[],
                        help='origins that the crawler should visit')
    parser.add_argument('--replay-warc-path', type=str, default=None,
                        help='path to the crawl that you want to replay')
    parser.add_argument('--replay-har-path', type=str, default=None,
                        help='path to the crawl that you want to replay')
    parser.add_argument('--clean', action='store_true', 
                        help='Clean zombie processes')
    parser.add_argument('--init', action='store_true', 
                        help='Initializes the setup')
    return parser.parse_args()


def main() -> None:
    """
    Main function
    
    Main creates the path for the output and sets everything up.
    Then it runs the crawlers.
    """

    args = parse_args()

    output = args.output
    workers = args.workers
    origins = args.origins
    replay_warc_path = args.replay_warc_path
    replay_har_path = args.replay_har_path

    # Handle cleaning of processes
    if args.clean:
        clean()
        return
    
    if args.init:        
        setup(output)
        print("Successful setup!")
        return

    # Replay WARC or HAR files if paths are provided
    if replay_warc_path:
        origin_directories = get_origin_directories(replay_warc_path, warc_replay=True)
        run_replay_warc(origin_directories, workers=workers)
    elif replay_har_path:
        origin_directories = get_origin_directories(replay_har_path, mitmd_replay=True)
        run_replay_har(origin_directories, workers=workers)
    else:
        # Run the crawling process
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        print("Timestamp:", ts)
        base_dir = os.path.dirname(os.path.realpath(__file__))
        output_path = os.path.join(base_dir, output, ts)

        setup(output_path)
        run_crawl(origins, output_path, workers)


if __name__ == "__main__":
    main()
