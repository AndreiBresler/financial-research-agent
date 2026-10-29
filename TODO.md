# TODO

Open items after build step 7. Build-step progress is in `STATUS.md`. Last updated 2026-10-29.

## Open issues

- [ ] **Text after Note 13 is attributed to Note 13.** In the real filing, the auditor's reports and other Item 8 material follow the last note, and the parser has no heading that closes a note, so those citations would say "Note 13". Fix: treat known Item 8 headings after the notes as closing the open note; needs a parser change, a `PARSER_VERSION` bump and a re-ingest.
- [ ] **Uncited asides in some answers.** The verifier flags interpretive or restated sentences without a marker; they appear as warnings in the answer and the end-to-end report. Prompt rules 2 and 6 reduced them; results vary between runs.
- [ ] **The planner's token usage isn't logged.** `with_structured_output` returns only the parsed `Plan`; `include_raw=True` would expose `usage_metadata` to `log_call`.
- [ ] **The retrieval eval has only 3 off-topic questions.** More would make the 0.6 threshold more reliable.

## Optional

- [ ] Set `HF_TOKEN` to remove the Hugging Face warning during ingestion and speed up model downloads.
- [ ] The first commit (`a374a09`) has a co-author line. Removing it means rewriting and force-pushing `main`; only if wanted.
