# TODO

Open action items. Build-step progress is tracked in `STATUS.md`. Last updated 2026-10-29.

## Next: build step 5

- [ ] `log.py`, including the node and tool-call decorator. The tool-call logging deferred from steps 3 and 4 lands here.
- [ ] In prompt files, write literal dollar signs as `$$`, because `string.Template` treats `$` as a placeholder (see CLAUDE.md).

## Later build steps

- [ ] Step 6: `main.py` builds `AsyncTavilyClient` from `settings.tavily_api_key.get_secret_value()` and passes it to `make_web_search` with `today=date.today`. `tavily-python` ships no type hints, so mypy can't check it against the `WebSearchClient` protocol; the integration tests are the first real check.
- [ ] Step 6: the CLI startup check should use `stale_reasons` and `missing_credentials()` and exit with code 2.
- [ ] Step 7: the README must answer the README questions: tool registration, tool choice, information flow and prompt location (HLD §9).

## Open issues

- [ ] **Text after Note 13 is attributed to Note 13.** In the real filing, the auditor's reports and other Item 8 material come after the last note. The parser has no heading that closes a note, so citations would label the auditor's report "Note 13". A possible fix: treat known Item 8 headings that follow the notes as closing the open note. This needs a parser change, a `PARSER_VERSION` bump and a re-ingest. Not yet approved.
- [ ] **The eval has only 3 off-topic questions.** Adding more would make the 0.6 threshold more reliable. Re-run `python src/evaluate.py` after any parsing, chunking or embedding change.

## Optional

- [ ] Set `HF_TOKEN` to remove the Hugging Face warning during ingestion and speed up model downloads.
- [ ] The first commit (`a374a09`) has a co-author line. Removing it means rewriting and force-pushing `main`; only if wanted.
