# Status

What's built versus designed but not yet implemented, keyed to the build order in `docs/low-level-design.md` §13. Last updated 2026-10-29.

## Build steps

| Step | Scope | Status | Commit |
|---|---|---|---|
| 1 | 10-K parser and table cleanup | ✅ Done | `92fab98` |
| 2 | Chunker, index, manifest, `src/ingest.py` | ✅ Done | `425a1c1` |
| 3 | `ChunkStore`, hybrid search, `search_10k`, retrieval eval, threshold calibration | ✅ Done | `d463a50`, `f8bb58e` |
| 4 | `web_search` and `calculator` tools | ✅ Done | `c8cafd7` |
| 5 | Agent graph, prompts, logging (`log.py`), scripted-model tests | ✅ Done | `536de87` |
| 6 | Answer verification, rendering, CLI | ✅ Done | `e3a24a8` |
| 7 | End-to-end tests on the two required queries, README | ✅ Done | `e3a24a8`, `0c87081` |

## What works today

- **Ingestion.** `python src/ingest.py` parses the filing, chunks it and builds `data/index/` (277 chunks from 640 blocks, parser version 2). No API keys needed.
- **Tools.** `search_10k` (hybrid search, section and kind filters, position order, one hop of cross-references), `web_search` (Tavily, untrusted wrapping) and `calculator` (`simpleeval`). Errors are raised as `ToolException` and reach the model as `status="error"` messages.
- **Agent.** plan → agent ⇄ tools → verify on LangGraph, Claude Haiku 5.5 by default via `init_chat_model` (Sonnet 5.5 also passes the e2e tests; `LLM_MODEL` switches). The plan uses native structured output; the system prompt is stable within a question and earlier turns are resent without thinking blocks (Claude binds thinking to the history).
- **Verification and rendering.** Code checks every marker, paragraph, list item, table row and figure; renders Sources from the Evidence; warns above the answer when a check fails.
- **CLI.** `python src/main.py` (REPL with `/new`, `/quit`) or one question; streams the plan, tool calls and results; startup checks exit 2 on a missing or stale index or a missing key.
- **End-to-end.** `pytest -m e2e` runs `eval/agent_queries.jsonl` (the two required queries plus the assignment's decision-logic examples and a not-disclosed case) through `tests/e2e/test_queries.py` and writes the answers after a full run where every query passed. Latest answers: `docs/example-outputs.md`.
- **Eval.** `python src/evaluate.py`: hit@5 1.0, not-found accuracy 1.0 at `min_dense_score` 0.6.

## Tests

- Layout: `tests/unit` (one module, fakes), `tests/integration` (components together, real filing or models, no paid APIs), `tests/e2e` (real APIs).
- Default run (`pytest`): 399 tests, about 7 s, no API keys or downloads.
- Opt-in: `pytest -m embedding_models` (12 tests, real models and filing); `pytest -m e2e` (6 end-to-end queries, real APIs, costs tokens).
- `ruff check`, `ruff format --check` and `mypy` (strict) pass.

## Review fixes (2026-10-29)

- `search_10k` position mode returns the opening part of each unit: Item 1A's second risk factor has twelve parts, and returning them all pushed the third risk factor past the 12,000-character output cap, so Query 1 named a different third risk factor from run to run.
- The auditor's reports after Note 13 belong to Item 8 (parser version 2); 9 chunks changed section, none changed text or `seq`. The retrieval eval's segment question had passed on those mislabelled chunks, so it now also lists `item:7`, which answers it.
- Simplification: one citation-marker pattern and ID hash (`tools/output.py`), `Searcher` takes `Settings`, one Qdrant opener and startup check, one text encoding, shared test helpers, dead code removed.

## Latest end-to-end run

The end-to-end checks fail on missed tools or figures, fabricated citations, model-written URLs and uncited tool results; uncited asides are warnings. All 6 queries passed in two consecutive runs on 2026-10-29, including both required queries (R&D 8.3% of net sales; gross margin 46.9%). Model output varies between runs: the agent once added a web search to the 10-K-only risk factors question, which prompt rule 3 now addresses.
