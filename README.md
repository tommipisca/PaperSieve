# PaperSieve

PaperSieve is a small open-source web app for searching academic papers on [arXiv](https://arxiv.org) and saving the interesting ones to a favorites list. It started as a personal project to learn Flask and public APIs, built to be useful to students and researchers who want to keep track of the scientific literature without too much fuss.

## Features (v1)

- Search across all arXiv categories by keyword, author, and/or category
- Sort by relevance or date
- Paginated results
- Save favorite papers (no account required: favorites are tied to the browser session)
- Dedicated page to review and remove saved favorites
- Saving/removing a favorite updates the page instantly, without a full reload (progressive enhancement: it still works with JavaScript disabled, just with a normal page reload instead)
- Export favorites as a BibTeX (`.bib`) file, ready to import into Zotero, Mendeley, or a LaTeX bibliography

## Tech stack

- Python 3 + [Flask](https://flask.palletsprojects.com/)
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) + SQLite for persisting favorites
- [feedparser](https://pypi.org/project/feedparser/) to parse the Atom responses from the [arXiv API](https://info.arxiv.org/help/api/index.html)
- Plain HTML/CSS on the frontend (Jinja2 templates)

## Local setup

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/PaperSieve.git
cd PaperSieve

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app locally
python run.py
```

The app will be available at `http://127.0.0.1:5000`.

On first run, a SQLite database is automatically created at `instance/papersieve.sqlite` (this folder is excluded from git).

## Project structure

```
PaperSieve/
├── app/
│   ├── __init__.py       # application factory
│   ├── arxiv_client.py   # arXiv API client
│   ├── models.py         # SQLAlchemy model for favorites
│   ├── routes.py         # Flask routes (search, favorites)
│   ├── templates/        # Jinja2 templates
│   └── static/           # CSS + app.js (progressive enhancement for favorites)
├── requirements.txt
├── run.py                # app entry point
└── README.md
```

## Roadmap

- [ ] Advanced filters (date range, multi-field sorting)
- [ ] Additional export formats (e.g. CSV)
- [ ] Support for sources beyond arXiv (e.g. Semantic Scholar)
- [ ] Optional user accounts to sync favorites across devices

## Contributing

This project is just getting started: issues, suggestions, and pull requests are welcome.

## License

Distributed under the [MIT license](LICENSE).
