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
| 6 | Answer verification, rendering, CLI | ✅ Done | |
| 7 | Integration tests on the two required queries, README | ✅ Done | |

## What works today

- **Ingestion.** `python src/ingest.py` parses the filing, chunks it and builds `data/index/` (277 chunks from 640 blocks). No API keys needed.
- **Tools.** `search_10k` (hybrid search, section and kind filters, position order, one hop of cross-references), `web_search` (Tavily, untrusted wrapping) and `calculator` (`simpleeval`). Errors are raised as `ToolException` and reach the model as `status="error"` messages.
- **Agent.** plan → agent ⇄ tools → verify on LangGraph, Claude Sonnet 5.5 via `init_chat_model`. The plan uses native structured output; the system prompt is stable within a question and earlier turns are resent without thinking blocks (Claude binds thinking to the history).
- **Verification and rendering.** Code checks every marker, paragraph, list item, table row and figure; renders Sources from the Evidence; warns above the answer when a check fails.
- **CLI.** `python src/main.py` (REPL with `/new`, `/quit`) or one question; streams the plan, tool calls and results; startup checks exit 2 on a missing or stale index or a missing key.
- **End-to-end.** `python src/run_e2e.py` runs `eval/agent_queries.jsonl` (the two required queries plus the assignment's decision-logic examples and a not-disclosed case); `pytest -m integration` runs the same through `tests/test_queries.py`. Latest answers: `docs/example-outputs.md`.
- **Eval.** `python src/evaluate.py`: hit@5 1.0, not-found accuracy 1.0 at `min_dense_score` 0.6.

## Tests

- Default run (`pytest`): 393 tests, about 7 s, no API keys or downloads.
- Opt-in: `pytest -m embedding_models` (12 tests, real models and filing); `pytest -m integration` (6 end-to-end queries, real APIs, costs tokens).
- `ruff check`, `ruff format --check` and `mypy` (strict) pass.

## Latest end-to-end run

Both required queries pass (R&D 8.3% of net sales; gross margin 46.9%). Across runs, some answers to the other queries carry a verification warning for an uncited aside, and the agent once added a web search to the 10-K-only risk factors question. Model output varies between runs.
