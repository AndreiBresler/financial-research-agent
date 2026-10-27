# Status

What's built versus designed but not yet implemented, keyed to the build order in `docs/low-level-design.md` §13. Last updated 2026-10-27.

## Build steps

| Step | Scope | Status | Commit |
|---|---|---|---|
| 1 | 10-K parser and table cleanup | ✅ Done | `92fab98` |
| 2 | Chunker, index, manifest, `src/ingest.py` | ✅ Done | `425a1c1` |
| 3 | `ChunkStore`, hybrid search, `search_10k`, retrieval eval, threshold calibration | ✅ Done | `d463a50`, `f8bb58e` |
| 4 | `web_search` and `calculator` tools | ⬜ Not started | |
| 5 | Agent graph, prompts, logging (`log.py`), scripted-model tests | ⬜ Not started | |
| 6 | Answer verification, rendering, CLI | ⬜ Not started | |
| 7 | Integration tests on the two required queries, README | ⬜ Not started | |

## What works today

- **Ingestion.** `python src/ingest.py` parses the filing, chunks it and builds `data/index/` (277 chunks from 640 blocks). It needs no API keys.
- **Search.** `search_10k` returns cited passages with Evidence. It supports a section filter (`item:8` includes its notes), a `kind` filter (text, risk factor or table), relevance or position order, and one hop of cross-references.
- **Eval.** `python src/evaluate.py` scores retrieval on `eval/retrieval_set.jsonl` (17 on-topic and 3 off-topic questions). At `min_dense_score` 0.6: hit@5 1.0, not-found accuracy 1.0.
- **Configuration.** `Settings` loads `.env`. API keys are optional until the agent starts.

## Not built yet

- `web_search` (Tavily) and `calculator` (simpleeval).
- The LangGraph agent: plan, agent, tools and verify nodes, the prompts in `prompts/`, and the `InMemorySaver` thread.
- Logging: `log.py`, the redaction processor, and the node and tool-call decorator from §11.
- Verification, rendering of the Sources list, and the CLI (REPL, one-shot mode, startup checks, exit codes).
- Integration tests and the final README, which must answer the assignment's README questions.

## Tests

- Default run (`pytest`): 196 tests, about 5 s, no API keys or downloads.
- Opt-in (`pytest -m embedding_models`): 12 tests with the real models on the real filing, about 1.5 min once the models are cached.
- `ruff check`, `ruff format --check` and `mypy` (strict) pass.
