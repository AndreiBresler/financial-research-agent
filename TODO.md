# TODO

Open action items. Build-step progress is tracked in `STATUS.md`. Last updated 2026-10-29.

## Next: build step 6

- [ ] Verification checks and rendering (LLD §9), replacing the placeholder `verify` node; the registry skips error `ToolMessage`s, whose artifact is `None`.
- [ ] The verification-failure graph test, moved here from step 5.
- [ ] The CLI: REPL, one-shot mode, streaming output; bind `run_id` and `thread_id` with structlog contextvars per question.
- [ ] `main.py`: `Prompts(settings.prompts_dir)`, `configure_logging(settings.log_path, verbose)`, the model via `init_chat_model`, and `AsyncTavilyClient` from `settings.tavily_api_key.get_secret_value()` passed to `make_web_search` with `today=date.today`. `tavily-python` ships no type hints, so mypy can't check it against the `WebSearchClient` protocol; the integration tests are the first real check.
- [ ] The CLI startup check should use `stale_reasons` and `missing_credentials()` and exit with code 2.

## Later build steps

- [ ] Step 7: the README must answer the README questions: tool registration, tool choice, information flow and prompt location (HLD §9).

## Open issues

- [ ] **Text after Note 13 is attributed to Note 13.** In the real filing, the auditor's reports and other Item 8 material come after the last note. The parser has no heading that closes a note, so citations would label the auditor's report "Note 13". A possible fix: treat known Item 8 headings that follow the notes as closing the open note. This needs a parser change, a `PARSER_VERSION` bump and a re-ingest. Not yet approved.
- [ ] **The planner's token usage isn't logged.** `with_structured_output` returns only the parsed `Plan`; `include_raw=True` would expose the reply's `usage_metadata` to `log_call`.
- [ ] **The eval has only 3 off-topic questions.** Adding more would make the 0.6 threshold more reliable. Re-run `python src/evaluate.py` after any parsing, chunking or embedding change.

## Optional

- [ ] Set `HF_TOKEN` to remove the Hugging Face warning during ingestion and speed up model downloads.
- [ ] The first commit (`a374a09`) has a co-author line. Removing it means rewriting and force-pushing `main`; only if wanted.
