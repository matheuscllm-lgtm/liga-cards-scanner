# price-compare-tool

A small personal Python utility that compares item prices between two public
reference sources, converts everything to a single currency, and reports
notable differences to a local spreadsheet. It is a single-user hobby project;
there is no hosted service, no website and no support.

## Requirements

- Python 3.11+
- Dependencies in `requirements.txt`

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Configuration defaults (such as the conversion rate) are read from environment
variables or a local config file. Copy the template and edit it:

```bash
cp scanner.config.example scanner.config   # (copy ... on Windows)
```

Local config and any data files are git-ignored and must never be committed.

## Usage

```bash
python src/main.py
```

By default it runs against bundled sample data (no internet or credentials
needed) — this is the path used by the tests. Exact options, the environment
variables that switch data sources, and the day-to-day workflow are documented
in `CLAUDE.md`.

Output files are written locally under `reports/` and are git-ignored (they are
data, not code).

## Tests

```bash
python -m pytest
```

## Notes

- Operational/run notes are kept local and are not part of this repository.
- Contributions are not being accepted; this is a personal project.
