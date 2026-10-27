# Financial Research Agent

A command-line research agent that answers questions about Apple Inc. from its fiscal 2025 Form 10-K and live web data. For each question it shows a plan, runs tools in parallel, computes every number in code, and cites every claim: a 10-K section and page, a web URL and retrieval date, or a calculation.

## Design

- [High-level design](docs/high-level-design.md): scope, architecture, agent loop, 10-K handling, reliability and security, path to production.
- [Low-level design](docs/low-level-design.md): modules, data models, ingestion stages, tool contracts, graph, tests and build order.

## Setup

Requires Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Tests

```bash
pytest                                       # unit tests
ruff check . && ruff format --check . && mypy
```

The parser tests run against a synthetic filing in `tests/fixtures/` and against the real filing in `data/aapl-20250927.htm`, a public EDGAR document included in the repo.
