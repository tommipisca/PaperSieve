"""Database models for PaperSieve.

There is a single model here: Favorite. Since v1 has no user accounts,
a favorite isn't linked to a "user" row — it's linked to an anonymous
browser session id (see app/__init__.py for how long that session cookie
is kept alive, and app/routes.py for where the id is generated).
"""

from datetime import datetime

from . import db


class Favorite(db.Model):
    """A single arXiv paper saved as a favorite by an anonymous session."""

    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)

    # Identifies *which browser session* saved this favorite. Not a real
    # user id (there's no login) — just the random token stored in the
    # session cookie, so we can list "this browser's" favorites later.
    session_id = db.Column(db.String(64), nullable=False, index=True)

    # The arXiv identifier of the paper, e.g. "2101.00001v1".
    arxiv_id = db.Column(db.String(64), nullable=False)

    # We copy the paper's details into our own table instead of only
    # storing the arxiv_id and re-fetching from arXiv every time. This
    # keeps the favorites page fast and working even if arXiv is
    # temporarily unreachable.
    title = db.Column(db.Text, nullable=False)
    authors = db.Column(db.Text, nullable=False)  # names joined with "; "
    summary = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=False)
    pdf_link = db.Column(db.String(255))
    published = db.Column(db.String(64))

    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        # The same browser can't save the same paper twice: this becomes
        # a database-level guarantee, not just something we remember to
        # check in the route.
        db.UniqueConstraint("session_id", "arxiv_id", name="uq_session_paper"),
    )

    def __repr__(self):
        return f"<Favorite {self.arxiv_id!r} for session {self.session_id[:8]}...>"
