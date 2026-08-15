"""URL routes for PaperSieve.

Registered as a Flask Blueprint (a way to group related routes together)
in the create_app() factory in app/__init__.py.
"""

import uuid
from urllib.parse import urlparse

from flask import Blueprint, Response, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from . import db
from .arxiv_client import CATEGORIES, ArxivClientError, search_papers
from .models import Favorite

bp = Blueprint("main", __name__)

RESULTS_PER_PAGE = 10

# The two sort orders arXiv's API supports that this app exposes (it also
# offers sorting by "lastUpdatedDate", but that's redundant with
# "submittedDate" for our purposes). Used both to populate the dropdown in
# search.html and to reject any unexpected value coming in on the query
# string before it's forwarded to arXiv.
SORT_OPTIONS = {
    "relevance": "Relevance",
    "submittedDate": "Newest first",
}

# arXiv's API returns a 500 Internal Server Error for the literal
# "browse everything" query (search_query=all:*) — confirmed this isn't
# about sort order (tried forcing sortBy=submittedDate first; arXiv 500s
# on it regardless of sort). Rather than let every visitor who submits
# the search form with every field blank hit that error, this exact
# message is shown instead, and arXiv is never actually called.
NEEDS_KEYWORD_OR_AUTHOR_ERROR = (
    "Enter a keyword or author, or choose a specific category — arXiv "
    "doesn't support browsing every category with nothing to search for."
)


def _safe_next_url(candidate, fallback):
    """Validates the "next" value from a favorite form before redirecting
    to it.

    "next" is meant to send visitors back to whichever page they clicked
    "save"/"remove" from (search results or the favorites page), but since
    it comes from a regular form field, nothing stops someone from crafting
    a request with next="https://evil.example" pointing somewhere else
    entirely (a classic open-redirect trick). Only allow it if it's a
    same-site relative path.
    """
    if not candidate:
        return fallback
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return fallback
    if not candidate.startswith("/") or candidate.startswith("//"):
        return fallback
    return candidate


def _get_session_id():
    """Returns this visitor's anonymous session id, creating one the
    first time they show up.

    Setting `session.permanent = True` here is what makes the cookie
    actually last for PERMANENT_SESSION_LIFETIME (configured in
    app/__init__.py) instead of being deleted as soon as the browser
    closes.
    """
    if "session_id" not in session:
        session["session_id"] = uuid.uuid4().hex
        session.permanent = True
    return session["session_id"]


@bp.route("/")
def index():
    # active_page isn't used for nav highlighting here (the landing page
    # has no header/nav at all), but it puts data-page="index" on <body>
    # so style.css can scope the "fit within one viewport" layout rules
    # to this page only, the same way app.js already scopes behaviour by
    # data-page on the search/favorites pages.
    return render_template("index.html", active_page="index")


@bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    author = request.args.get("author", "").strip()
    category = request.args.get("category", "")
    page = max(request.args.get("page", 1, type=int), 1)

    sort_by = request.args.get("sort", "relevance")
    if sort_by not in SORT_OPTIONS:
        sort_by = "relevance"

    results = None
    total_pages = 0
    error = None

    if category == "all" and not query and not author:
        # See NEEDS_KEYWORD_OR_AUTHOR_ERROR above: this exact combination
        # is known to 500 on arXiv's side, so it's rejected here instead
        # of ever being sent.
        error = NEEDS_KEYWORD_OR_AUTHOR_ERROR
    # Only call arXiv if the visitor has actually searched for something;
    # otherwise just show the empty form.
    elif query or author or category:
        try:
            results = search_papers(
                query=query,
                author=author,
                category=category,
                start=(page - 1) * RESULTS_PER_PAGE,
                max_results=RESULTS_PER_PAGE,
                sort_by=sort_by,
            )
            # Ceiling division: rounds up so a partial last page still
            # counts (e.g. 21 results / 10 per page = 3 pages, not 2).
            total_pages = max(1, -(-results["total_results"] // RESULTS_PER_PAGE))
        except ArxivClientError as exc:
            error = str(exc)

    session_id = _get_session_id()
    favorite_ids = {
        favorite.arxiv_id
        for favorite in Favorite.query.filter_by(session_id=session_id).all()
    }

    return render_template(
        "search.html",
        active_page="search",
        query=query,
        author=author,
        category=category,
        categories=CATEGORIES,
        sort=sort_by,
        sort_options=SORT_OPTIONS,
        results=results,
        error=error,
        page=page,
        total_pages=total_pages,
        favorite_ids=favorite_ids,
    )


@bp.route("/favorites")
def favorites():
    session_id = _get_session_id()
    saved = (
        Favorite.query.filter_by(session_id=session_id)
        .order_by(Favorite.saved_at.desc())
        .all()
    )
    return render_template("favorites.html", active_page="favorites", favorites=saved)


@bp.route("/favorites/add", methods=["POST"])
def add_favorite():
    session_id = _get_session_id()
    arxiv_id = request.form["arxiv_id"]

    already_saved = Favorite.query.filter_by(
        session_id=session_id, arxiv_id=arxiv_id
    ).first()

    if not already_saved:
        favorite = Favorite(
            session_id=session_id,
            arxiv_id=arxiv_id,
            title=request.form.get("title", ""),
            authors=request.form.get("authors", ""),
            summary=request.form.get("summary", ""),
            link=request.form.get("link", ""),
            pdf_link=request.form.get("pdf_link", ""),
            published=request.form.get("published", ""),
        )
        db.session.add(favorite)
        try:
            db.session.commit()
        except IntegrityError:
            # Two "save" requests for the same paper landed close enough
            # together that both passed the already_saved check above
            # (e.g. a very fast double click). The database's own
            # UniqueConstraint caught it — the paper ends up saved either
            # way, so there's nothing to report back to the visitor.
            db.session.rollback()

    # "next" lets the same form work from more than one page (search
    # results or the favorites page itself) and send the visitor back to
    # wherever they clicked "save" from.
    return redirect(_safe_next_url(request.form.get("next"), url_for("main.search")))


@bp.route("/favorites/remove", methods=["POST"])
def remove_favorite():
    session_id = _get_session_id()
    arxiv_id = request.form["arxiv_id"]

    Favorite.query.filter_by(session_id=session_id, arxiv_id=arxiv_id).delete()
    db.session.commit()

    return redirect(_safe_next_url(request.form.get("next"), url_for("main.favorites")))


def _escape_bibtex(text):
    """Escapes literal '{' and '}' so they can't unbalance a BibTeX
    field's braces.

    arXiv titles and author-supplied text often contain LaTeX math (e.g.
    "Learning in O(n^{2}) time"), and every brace in a title is otherwise
    passed straight through into the exported file. A single unescaped
    brace throws off brace-balance for the rest of the entry and can
    corrupt it for every downstream parser (Zotero, BibTeX/BibLaTeX, ...).
    """
    return text.replace("{", r"\{").replace("}", r"\}")


def _to_bibtex_entry(favorite):
    """Converts one Favorite row into a single BibTeX @article entry.

    BibTeX is the citation format LaTeX and most reference managers
    (Zotero, Mendeley, ...) can import directly, which makes it a more
    useful export for an academic audience than a plain CSV.
    """
    # BibTeX keys shouldn't contain dots; arxiv_id looks like "2101.00001v1".
    key = favorite.arxiv_id.replace(".", "_")

    # We store authors as "Name One; Name Two" (see models.py); BibTeX
    # expects them joined with " and " instead.
    authors = _escape_bibtex(favorite.authors.replace("; ", " and "))
    title = _escape_bibtex(favorite.title)

    # `published` is an ISO-ish date string like "2017-06-12T00:00:00Z";
    # BibTeX just wants the year.
    year = favorite.published[:4] if favorite.published else ""

    return (
        f"@article{{{key},\n"
        f"  title = {{{title}}},\n"
        f"  author = {{{authors}}},\n"
        f"  year = {{{year}}},\n"
        f"  eprint = {{{favorite.arxiv_id}}},\n"
        f"  archivePrefix = {{arXiv}},\n"
        f"  url = {{{favorite.link}}}\n"
        f"}}"
    )


@bp.route("/favorites/export")
def export_favorites():
    session_id = _get_session_id()
    saved = (
        Favorite.query.filter_by(session_id=session_id)
        .order_by(Favorite.saved_at.desc())
        .all()
    )

    bibtex = "\n\n".join(_to_bibtex_entry(favorite) for favorite in saved)

    return Response(
        bibtex,
        mimetype="application/x-bibtex",
        headers={
            "Content-Disposition": "attachment; filename=papersieve-favorites.bib"
        },
    )
