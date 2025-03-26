# WebREC
This project provides a framework for crawling websites using Brave's [pagegraph crawl](https://github.com/brave/pagegraph-crawl). A combination of warcprox and mitmproxy collects web archives (WARC), HTTP Archives (HAR), and JavaScript execution traces. The collected data can then be replayed to analyze the recorded interactions.

This code is used in the paper "Web Execution Bundles: Reproducible, Accurate, and Archivable Web Measurements".

All relevant detailed steps to run the pipeline are also described in the [AE PDF](PageGraph_Analyses_AE.pdf).

## Requirements
* Python 3.x
* Brave Nightly executable path defined in `config.py`.
* `warcprox` and `mitmdump` installed in your environment.
* `npm` and `git` installed to manage the [pagegraph crawl](https://github.com/brave/pagegraph-crawl) repository.
* `pip install -r requirements.txt`

Make sure you have all the required dependencies installed before running the project.

## Pagegraph-crawl Patches
For our research, we added two additions to the [pagegraph-crawl](https://github.com/brave/pagegraph-crawl/tree/0758ba99697afd7d3e30f92688430fe5c4faa69d) version we were working with (commit `0758ba99697afd7d3e30f92688430fe5c4faa69d`). 
1. **Bypass CSP.**
In order to hook into the JS calls, we had to bypass CSP. Puppeteer provides a method to do so ([see here](https://github.com/puppeteer/puppeteer/blob/main/docs/api/puppeteer.page.setbypasscsp.md)). We added this in our crawler via `await page.setBypassCSP(true)` before the first `goto` call.
2. **Xvfb retries.**
Since we run the crawler in parallel, we had issues with xvfb sessions that took longer to close. Therefore, we added a wait and retry function to pagegraph crawler when starting or stopping xvfb.

Both additions, plus test code that was not relevant for the final analysis, can be found in the [pagegraph patches](./src/pagegraph_patches/).

Even without the patchs, we expect the newest version of pagegraph-crawl to work with our framework for test runs.
The newer version only uses `--logging verbose` instead of `--debug debug` which is set in the [pageggraph-crawl call](./src/misc.py).

## Installation
1. **Clone the repository**
```
git clone git@github.com:FHantke/hwpg.git
cd hwpg/src
```

2. **Install Python dependencies**
```
pip install -r requirements.txt
```

## Example config.py
```
TELEGRAM_API_KEY = 'secret'
TELEGRAM_CHAT_ID = 1
JS_HOOKING = True
SCRIPT_PATH = "./js_injections/js_hooks.js"
INITIALIZATION_BREAK = 60
BRAVE_EXEC_PATH = "/opt/brave.com/brave-nightly/brave-browser-nightly"
```

## Usage
```
usage: main.py [-h] [--output OUTPUT] [--workers WORKERS] [--origins [ORIGINS ...]] [--replay-warc-path REPLAY_WARC_PATH] [--replay-har-path REPLAY_HAR_PATH] [--clean]

Process some integers.

options:
  -h, --help            show this help message and exit
  --output OUTPUT       output path to store archives
  --workers WORKERS     number of workers
  --origins [ORIGINS ...]
                        origins that the crawler should visit
  --replay-warc-path REPLAY_WARC_PATH
                        path to the crawl that you want to replay
  --replay-har-path REPLAY_HAR_PATH
                        path to the crawl that you want to replay
  --clean               Clean zombie processes
```

### Running a Crawl
To start a crawl, run the following command:
```
python main.py --output ./output --workers 4 --origins https://example.com
```

## Replaying a WARC or HAR Archive
To replay a previously collected WARC or HAR archive, specify the path
to the earlier collected output. `replay-warc-path` replays WARC files, 
`replay-har-path` replays har files.

```
python main.py --replay-warc-path ./output/2024-09-25_113507
```

##  Output Example
```
output
└── 2024-09-25_113507
    └── https_example.com
        ├── example.com.har
        ├── example.com.warc
        ├── logs
        │   ├── mitmd_15001.log
        │   ├── warcp_16001.log
        │   └── pagegraph.log
        ├── mitmd_replay
        │   ├── log-p1.txt
        │   ├── logs
        │   │   ├── mitmd_15001.log
        │   │   └── pagegraph.log
        │   └── page_graph_https___fhantke_de_1727271635.graphml
        ├── warc_replay
        │   ├── log-p1.txt
        │   ├── logs
        │   │   ├── mitmd_15001.log
        │   │   ├── warcp_16001.log
        │   │   └── pagegraph.log
        │   ├── collections/...
        │   └── page_graph_https___fhantke_de_1727269058.graphml
        └── page_graph_https___fhantke_de_1727264133.graphml
```
