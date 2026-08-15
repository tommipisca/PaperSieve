"""Standalone diagnostic script — NOT part of the app.

Runs the exact same request our arxiv_client.py makes, but with no Flask
involved, so we can isolate whether the slowdown is specific to the
`requests` library itself vs something about the Flask app.

Usage (with the venv activated):
    python test_arxiv.py
"""

import time

import requests

HEADERS = {
    "User-Agent": "PaperSieve/0.1 (open-source student project; https://github.com/tommipisca/PaperSieve)"
}

print("Sending request...")
start = time.time()

response = requests.get(
    "https://export.arxiv.org/api/query",
    params={"search_query": "all:test", "max_results": 1},
    headers=HEADERS,
    timeout=60,
)

elapsed = time.time() - start
print(f"Status: {response.status_code}")
print(f"Elapsed: {elapsed:.3f} seconds")
