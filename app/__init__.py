"""Application factory for PaperSieve.

This module defines create_app(), which builds and configures a new Flask
application instance. Using a factory function (rather than a module-level
`app = Flask(__name__)`) makes it possible to create differently-configured
instances of the app, e.g. one for local development and one for tests.
"""

import os
from datetime import timedelta

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Created here, without an app attached yet, and bound to a specific app
# later inside create_app() via db.init_app(app). This "deferred
# initialization" pattern avoids circular imports between this module and
# models.py (which needs to import `db` to define its models).
db = SQLAlchemy()


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        # Signs the session cookie so it can't be tampered with by the
        # browser. In production this should come from an environment
        # variable, never be hardcoded.
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),

        # The favorites database lives in the (gitignored) instance folder,
        # so each local checkout gets its own file.
        SQLALCHEMY_DATABASE_URI="sqlite:///"
        + os.path.join(app.instance_path, "papersieve.sqlite"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,

        # Favorites are tied to an anonymous session cookie (no login).
        # This controls how long a session lasts once it's marked
        # "permanent" — which we do explicitly in routes.py the first
        # time a visitor gets a session id (session.permanent = True).
        # Without that, Flask's default is to drop the cookie as soon as
        # the browser closes, regardless of this setting.
        PERMANENT_SESSION_LIFETIME=timedelta(days=365),
    )

    # The instance folder doesn't exist on a fresh checkout (it's
    # gitignored), so we have to create it ourselves before SQLite can
    # write a database file into it.
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    # Imported here, not at the top of the file: models.py and routes.py
    # both import `db` from this module, so importing them before `db`
    # exists (or before the app is configured) would cause a circular
    # import error.
    from . import models  # noqa: F401  (registers the models with SQLAlchemy)
    from . import routes

    app.register_blueprint(routes.bp)

    with app.app_context():
        db.create_all()

    return app
