"""Minimal client for the public arXiv API.

Official documentation: https://info.arxiv.org/help/api/index.html

arXiv doesn't return JSON: it returns an Atom feed (XML), which is why we
use `feedparser` (a library built for parsing RSS/Atom feeds) instead of
just calling `response.json()` like you would with most modern APIs.
"""

from dataclasses import dataclass
from typing import List, Optional

import feedparser
import requests

ARXIV_API_URL = "https://export.arxiv.org/api/query"

# arXiv's API documentation asks clients to identify themselves with a
# descriptive User-Agent instead of relying on a library's generic default
# (requests sends "python-requests/X.Y.Z" if we don't set this, which some
# servers treat as generic bot traffic and throttle more aggressively).
HEADERS = {
    "User-Agent": "PaperSieve/0.1 (open-source student project; https://github.com/tommipisca/PaperSieve)"
}

# Top-level arXiv categories, used to populate the filter dropdown in the
# UI. Keep these labels in sync with the <option> values in search.html.
# "all" is a sentinel meaning "no filter" (search across every category) —
# it isn't a real arXiv category, so _build_search_query() below has to
# treat it specially rather than passing it straight through as `cat:all*`.
CATEGORIES = {
    "all": "All categories",
    "cs": "Computer Science",
    "math": "Mathematics",
    "physics": "Physics",
    "q-bio": "Quantitative Biology",
    "q-fin": "Quantitative Finance",
    "stat": "Statistics",
    "eess": "Electrical Engineering & Systems Science",
    "econ": "Economics",
}


@dataclass
class ArxivPaper:
    """A single search result, already converted from the raw Atom entry
    into plain Python types the rest of the app can work with."""

    arxiv_id: str
    title: str
    authors: List[str]
    summary: str
    published: str
    updated: str
    link: str
    pdf_link: Optional[str]
    categories: List[str]
    primary_category: Optional[str]


class ArxivClientError(RuntimeError):
    """Raised when a search against arXiv fails (network error or a
    response we can't make sense of)."""


def _build_search_query(query: str = "", category: str = "", author: str = "") -> str:
    """Builds the `search_query` string in the format arXiv's API expects.

    arXiv uses field prefixes joined with boolean operators, e.g.:
        all:transformer AND au:vaswani AND cat:cs*
    """
    parts = []
    if query:
        parts.append(f"all:{query}")
    if author:
        parts.append(f"au:{author}")
    if category and category != "all":
        # "all" (and, for backwards compatibility, the empty string this
        # project used before) both mean "no category filter" — see the
        # comment on CATEGORIES in this module. Anything else is a real
        # arXiv category; the trailing "*" matches its sub-categories too,
        # e.g. "cs*" matches both "cs.CL" and "cs.LG", not just "cs".
        parts.append(f"cat:{category}*")
    if not parts:
        # arXiv requires *some* search_query; this matches everything.
        parts.append("all:*")
    return " AND ".join(parts)


def search_papers(
    query: str = "",
    category: str = "",
    author: str = "",
    start: int = 0,
    max_results: int = 10,
    sort_by: str = "relevance",
    sort_order: str = "descending",
) -> dict:
    """Queries the arXiv API and returns already-parsed results.

    Returns a dict with:
      - papers: list of ArxivPaper
      - total_results: total number of matches arXiv reports (used for
        pagination, even though we only fetch one page at a time)
      - start / max_results: the pagination parameters that were used

    Raises ArxivClientError if the request fails or the response can't be
    parsed, so callers (the routes) can catch a single, specific exception
    instead of having to know about `requests` or `feedparser` internals.
    """
    search_query = _build_search_query(query, category, author)

    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    try:
        response = requests.get(
            ARXIV_API_URL, params=params, headers=HEADERS, timeout=60
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        # arXiv answered, but with an error status. 429 ("Too Many
        # Requests") is common: arXiv asks API clients to send at most
        # one request every few seconds, and it's easy to hit that limit
        # while testing (repeated searches, app restarts, ...).
        if exc.response is not None and exc.response.status_code == 429:
            raise ArxivClientError(
                "arXiv is rate-limiting requests right now. Wait a few "
                "seconds and try again."
            ) from exc
        raise ArxivClientError(f"arXiv returned an error: {exc}") from exc
    except requests.RequestException as exc:
        # A broader failure: no response at all (connection refused,
        # DNS failure, timeout, ...).
        raise ArxivClientError(f"Could not reach arXiv: {exc}") from exc

    feed = feedparser.parse(response.text)
    if feed.bozo and not feed.entries:
        raise ArxivClientError("Received an invalid response from arXiv.")

    total_results = int(feed.feed.get("opensearch_totalresults", 0))

    papers = []
    for entry in feed.entries:
        # entry.id looks like "http://arxiv.org/abs/2101.00001v1"; we only
        # want the id itself.
        arxiv_id = entry.id.rsplit("/abs/", 1)[-1]

        authors = [author.name for author in getattr(entry, "authors", [])]

        pdf_link = None
        for link in getattr(entry, "links", []):
            if getattr(link, "title", "") == "pdf":
                pdf_link = link.href
                break

        categories = [tag["term"] for tag in getattr(entry, "tags", [])]
        primary = getattr(entry, "arxiv_primary_category", None)
        primary_category = primary.get("term") if primary else None

        papers.append(
            ArxivPaper(
                arxiv_id=arxiv_id,
                # arXiv abstracts/titles often contain line breaks purely
                # for formatting; collapsing whitespace keeps them clean.
                title=" ".join(entry.title.split()),
                authors=authors,
                summary=" ".join(entry.summary.split()),
                published=entry.get("published", ""),
                updated=entry.get("updated", ""),
                link=entry.link,
                pdf_link=pdf_link,
                categories=categories,
                primary_category=primary_category,
            )
        )

    return {
        "papers": papers,
        "total_results": total_results,
        "start": start,
        "max_results": max_results,
    }
