# CLAUDE.md

This file gives Claude Code the context needed to work on this project without re-deriving decisions that have already been made. Read it before making changes.

## Project overview

A command-line research agent that answers questions about Apple Inc. from its fiscal 2025 Form 10-K (year ended 2025-09-27) and live web data. For each question it streams a plan, runs tools in parallel, computes every derived number in code, and cites every claim: 10-K section and page, web URL and retrieval date, or calculation. It is a take-home assignment: the docs refer to its required queries, bonuses and README questions, and HLD §9 maps each requirement to the design section that covers it.

**The design documents are the spec.** Implement what they say. If the code needs to differ, flag the deviation; once it's approved, update the doc in the same change and bump its version, so docs and code never diverge. HLD §8 (demo → production) is material for the README, not work to do: web UI, multiple companies, authentication and deployment are non-goals (HLD §2).

**Grounding is the product.** Every fact and number in an answer comes from a tool result in this conversation, every derived number comes from `calculator`, and the model never writes a URL or page number: code renders the Sources list from the evidence registry, and a code verifier (not an LLM) flags uncited claims. A change that weakens any of this needs explicit sign-off.

Reference docs:
- `docs/high-level-design.md` — scope and assumptions, architecture, agent loop, information flow for the required queries, 10-K handling, reliability and security, demo → production, requirements traceability.
- `docs/low-level-design.md` — implements the HLD: conventions, layout, dependency decisions, `Settings`, data models, ingestion stages, retrieval and tool contracts, graph, verification, CLI, errors, tests, build order.
- `STATUS.md`: what's built vs. designed-but-not-implemented, by build step. Check it before assuming a component doesn't exist yet.
- `TODO.md`: open action items, known issues and optional cleanups.

## Tech stack

Python 3.12, local CLI only. Per-package decisions: LLD §3.

- **LangGraph**, a custom `StateGraph` (plan → agent ⇄ tools → verify), not a prebuilt agent, so plan and verify are explicit, testable nodes.
- **Claude** via `init_chat_model` (`langchain-anthropic`), `temperature=0`. The model (default `anthropic:claude-sonnet-5-5`) is a `Settings` value.
- **BeautifulSoup + lxml**, a targeted parser: 10-K structure lives in inline styles, which generic loaders lose.
- **Qdrant local mode + FastEmbed** (`BAAI/bge-small-en-v1.5` dense, `Qdrant/bm25` sparse): hybrid search fused with Qdrant's built-in RRF (`RrfQuery`, with an explicit `rrf_k`), no server, GPU or embedding API. `qdrant-client` is used directly, not `langchain-qdrant`, because search needs the raw dense score for the not-found threshold.
- **Tavily** via `AsyncTavilyClient` in a thin wrapper of our own, not `langchain-tavily`, to control output format, IDs and errors.
- **`simpleeval`** for the calculator: LLMs are unreliable at arithmetic and `eval` is unsafe.
- Pydantic v2 + pydantic-settings, structlog, rich, `tokenizers`, `langchain-text-splitters`.
- pytest + pytest-asyncio, ruff, mypy (strict).

## Code style and architecture

### Language conventions (LLD §1)

- Fully typed: `mypy` strict on our package (untyped third-party imports ignored); `ruff` lints and formats.
- Pydantic v2 models for all data that crosses a module boundary; `TypedDict` only for the LangGraph state.
- **Async I/O.** Graph nodes and network-bound tools are `async def`, and the model is called with `ainvoke`. CPU-bound work on the query path (query embedding, local Qdrant search) runs in `asyncio.to_thread`. Nothing blocks the event loop. Ingestion is a batch job and stays synchronous; `calculator` stays sync because it does no I/O.
- **No module-level side effects.** Models, clients, the index and `Settings` are created once in `main.py` (the composition root) and passed in.
- **LLD code snippets are illustrative.** They use short names (`g`, `flt`) and free variables (`index`, `settings`) for brevity. Real code follows the rules below: spelled-out names, injected dependencies.

### Classes where there is state, functions where there isn't

- **Classes** for components that hold state or dependencies: `ChunkStore`, `Index`, `PlanNode`, `AgentNode` (callable classes with `async def __call__`).
- **Pure functions** for stateless transforms: each ingestion stage (a pure function over the previous stage's output), the verification checks, rendering.
- **Tool factories** that close over injected dependencies, such as `make_search_10k(store, index, settings)`, because LangChain's `@tool` decorates functions.

SOLID applies to all three:

**S — Single Responsibility.** One job per class or function. Never mix I/O with business logic: the parser doesn't read files, the verifier doesn't call the model.

**O — Open/Closed.** Add behaviour with new nodes, tools or parser stages, not by growing `if/elif` chains inside existing ones.

**L — Liskov Substitution.** A subtype must be usable wherever the base type is expected. That includes test fakes: `ScriptedChatModel` stands in for `BaseChatModel` and must honour its contract, or the graph tests prove nothing.

**I — Interface Segregation.** Keep dependencies narrow: pass the values a component needs rather than all of `Settings` when it reads only one or two.

**D — Dependency Inversion.** Inject dependencies (model, Qdrant client, Tavily client, store) through `__init__` or factory arguments. Never construct them inside a method body. This is what lets graph tests run with a scripted model and no API keys.

### Use existing libraries — do not reinvent the wheel

Before writing a utility, check whether a dependency already provides it: `ToolNode` (parallel execution, errors as `ToolMessage`s), `InMemorySaver`, `with_structured_output`, `bind_tools`, `RecursiveCharacterTextSplitter`, Pydantic validators, structlog processors. Shared code lives in `research_agent/` (`config.py`, `models.py`, `log.py`, `prompts.py`) and is imported, not duplicated. The deliberate exceptions (our own Tavily wrapper, `qdrant-client` directly, a custom graph) are decided in LLD §3; don't "simplify" them back into wrapper libraries.

## Hard constraints — flag before violating any of these

Project-specific:

- **Answers are grounded and verified in code.** Facts and numbers come only from tool results, derived numbers only from `calculator`; the model never writes URLs or page numbers; `verify` stays code, never an LLM call (HLD §4, LLD §8–9).
- **Tools are read-only.** No file, shell or write tools. The calculator allows no names and only `round` and `abs`. Web content is always wrapped in `<untrusted_web_content>` and never followed as instructions.
- **Secrets come only from the environment**, as `SecretStr`: never logged, printed or committed. `.env` stays out of version control; `.env.example` lists the keys without values.
- **Tunables live in `Settings`, not in code**, so tuning never touches code. `min_dense_score` is calibrated with the retrieval eval, not guessed.
- **Model and embedding names are configuration.** No model string appears outside the `Settings` defaults.
- **Prompt text lives in `prompts/`**, not in Python. The exception is tool descriptions, which live in the tool docstrings next to the contract they describe (LLD §7).
- **Tests run without API keys**, except those under the opt-in `integration` marker.
- **`data/index/` is generated.** Never hand-edit it; re-run `python src/ingest.py`. `manifest.json` is written last, so a crashed build leaves no manifest and the CLI refuses to start.
- **Nothing from HLD §8's production column gets built.**

General:

- **No hardcoded strings or magic numbers in logic.** Fixed values are constants at the top of the module that owns them; tunables go in `Settings` (above). This includes protocol strings shared across modules (citation prefixes, error codes such as `NO_RELEVANT_CONTENT`, section ID formats, answer headings), third-party keys (Qdrant vector names `dense`/`sparse`, payload keys) and text encodings. If a constant already exists, import it; grep before adding a literal.
- **No short or abbreviated variable/parameter names.** Spell it out (`message`, not `msg`; `exception`, not `exc`; `query_filter`, not `flt`). Exceptions: names fixed as a contract in the LLD stay as written, namely `Settings` fields (they map to env vars), Pydantic model fields (they are the `chunks.jsonl` format) and tool argument names (the model sees them), such as `seq`, `k` and `llm_timeout_s`. TypeVars stay single-letter.
- **No nested or chained method calls.** Assign each intermediate step to a named variable, including in LangChain's fluent API: `structured_model = llm.with_structured_output(Plan)`, then `plan = await structured_model.ainvoke(messages)`.
- **Every function and method gets a one-line docstring** stating what it does. Tool docstrings are the exception: they are the model-facing tool description, so they are prompt content. Write them for the model, and treat a change to one as a behaviour change.
- **structlog, never `print()`.** The one exception is user-facing CLI output in `cli.py`, which goes through a `rich` console.
- **Minimal inline comments.** Code should be self-explanatory line by line. Comment the *why*, not the *what*, and only where a reader would otherwise be surprised.
- **General clean-code discipline**: small functions doing one thing at one level of abstraction, early returns over deep nesting, narrow parameter lists, no dead or commented-out code.
- **Full files, not diffs or snippets**, when proposing a file that doesn't exist yet in the conversation; targeted edits once it does.
- **Propose before implementing.** The HLD and LLD are the approved architecture, so implementing what they specify doesn't need re-litigating, but anything beyond a trivial fix still gets a short plan and a "go".

## Cross-file invariants — change both sides together

- **Citation markers.** Tools emit `[D<seq>]`, `[W<6 hex>]` and `[C<6 hex>]` (LLD §7); `verify` matches `\[([DWC][0-9a-f]{1,8})\]` (LLD §9); `system.txt` tells the model to copy markers exactly. IDs are stable, never counters: `D` plus the chunk's `seq`, `W`/`C` plus the first 6 hex characters of a SHA-1 of the URL or of the expression with all whitespace removed. That's why parallel tool calls need no shared counter.
- **The evidence registry is derived** from the `Evidence` artifacts on the `ToolMessage`s in `messages`. Don't add a state field for it. The model never sees artifacts.
- **Answer headings.** `### Assumptions` and `### Data gaps` (`system.txt` rule 6) mark where the verified body ends, and `render` appends `### Sources`. Renaming one means changing the prompt, `verify` and `render` together.
- **Tool error strings** (`NO_RELEVANT_CONTENT …` from `search_10k`, and from `web_search` when it gets no results; `ERROR web_unavailable: …`, `ERROR invalid_expression: …`) are read by the model and printed by the CLI. They are instructions to the model as much as error codes. `ERROR …` strings are raised as `ToolException` and reach the model as `ToolMessage`s with `status="error"`; `NO_RELEVANT_CONTENT` is a normal result with no Evidence.
- **Section IDs** (`item:1A`, `item:7`, `note:5`) are produced by the parser, accepted by `search_10k`'s `section` argument and listed to the model through `$sections`.
- **Per-question state reset.** Each question's input, built by `question_input` in `agent/state.py`, resets `plan`, `tool_rounds` and `final`, while `messages` keeps accumulating in the thread (LLD §8). A new per-question field in `AgentState` must be added to that reset.
- **Recursion limit vs. tool budget.** `recursion_limit=25` is a backstop; a run with `max_tool_rounds` rounds takes `2 × rounds + 3` steps (6 rounds → 15 steps). Going above 11 rounds means raising the limit too.
- **Prompt templating.** `prompts.py` fills `$sections`, `$plan`, `$rounds_left`, `$question` and `$tool_results` with `string.Template`. Braces need no escaping, but **dollar signs do**: with `substitute`, `$1,234` raises `ValueError` and `$AAPL` raises `KeyError`. Write literal dollars as `$$` in prompt files, and use `substitute`, not `safe_substitute`, which silently leaves a misspelled placeholder unfilled.
- **Embedding model ↔ index.** The dense vector size (384) belongs to `bge-small-en-v1.5`; changing `dense_model` changes it and requires a re-ingest. The chunk token limit (`chunk_max_tokens`, 400; model limit 512) counts the section-path prefix plus the text, measured with the embedding model's tokenizer.
- **Parser, chunker or embedding change → re-ingest and re-evaluate.** Bump `parser_version`, re-run `python src/ingest.py` and `python src/evaluate.py` (hit@5, not-found accuracy), and re-check `min_dense_score`. Every new parser rule gets a case in `tests/fixtures/mini_10k.htm`.

## Development workflow — save tokens without hurting quality or speed

- **Reuse scripts, don't rewrite them.** Before writing a verification or debug script, check `.dev-scratch/` and the test suite for something that already does the job. Extend or rerun it instead of re-authoring it.
- **Persist utility scripts in `.dev-scratch/`.** One-off scripts used to verify a change (not part of the app or its tests), such as dumping parsed blocks or probing a search, go in `.dev-scratch/` at the project root, gitignored. Give them descriptive names (`dump_item_1a_risk_factors.py`, not `tmp.py`) so they're found and reused next session.
- **Batch related checks into one command**, not one tool call per file: `ruff check . && ruff format --check . && mypy`.
- **Test strategically, not reflexively.** Plan the checkpoints before a multi-step change; LLD §13's build steps are natural ones. After a small edit, `ruff` + `mypy` and the relevant unit test file are enough; run the full `pytest` at checkpoints. Run integration tests (they cost API tokens) and the retrieval eval only when their inputs change: prompts, tools, the graph, parsing, chunking or embedding.
- **Always propose before implementing — wait for "go".** Show the plan (approach, files touched, and for any real behaviour change, the tradeoffs) and wait for an explicit "go" before writing code. This applies even when a message mixes a review ask with an implementation ask ("review X and add Y"): review first, changes after confirmation.
- **Prefer targeted edits over full-file rewrites** when only part of a file changes, to keep diffs (and token cost) proportional to the change.

## Repository structure

Planned layout, from LLD §2, which lists every module; `STATUS.md` says which parts exist so far. The LLD names the root `financial-research-agent/`; here it is this directory.

```
README.md                 setup, usage, design summary; answers the assignment's README questions
CLAUDE.md                 this file
pyproject.toml            ruff, mypy and pytest config (pythonpath = ["src"], mypy_path = "src")
requirements.txt          pinned runtime dependencies; requirements-dev.txt adds pytest, pytest-asyncio, ruff, mypy
.env.example              ANTHROPIC_API_KEY, TAVILY_API_KEY, without values
docs/                     high-level-design.md, low-level-design.md
prompts/                  system.txt, planner.txt, examples.txt, final.txt
data/aapl-20250927.htm    the source filing (public)
data/index/               generated by ingest: qdrant/, chunks.jsonl, manifest.json
eval/retrieval_set.jsonl  retrieval eval questions with their expected section_id
src/main.py               agent CLI entry point
src/ingest.py             ingestion entry point
src/evaluate.py           retrieval eval entry point
src/research_agent/       the package: config, models, log, prompts, cli; ingestion/, retrieval/, tools/, agent/
tests/                    fixtures/mini_10k.htm, unit/, graph/ (scripted fake model), test_queries.py (integration)
logs/                     generated: agent.jsonl
.dev-scratch/             gitignored one-off verification scripts
```

Entry scripts in `src/` only wire things up; logic lives in `research_agent/`. Running `python src/<script>.py` puts `src/` on the import path, so `research_agent` imports directly; pytest and mypy get the same path from `pyproject.toml`.

## Running things

There is no deployment: this is a local CLI, and HLD §8 only describes the production path.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env              # then fill in ANTHROPIC_API_KEY and TAVILY_API_KEY

python src/ingest.py              # builds data/index/: once per filing, or after a parser, chunker or embedding change
python src/main.py                # REPL: /new starts a new thread, /quit exits
python src/main.py "question"     # one-shot; --verbose adds full tool outputs and debug logs
python src/evaluate.py            # retrieval eval: hit@5 and not-found accuracy

pytest                            # unit and graph tests; integration tests excluded by default
pytest -m embedding_models        # real FastEmbed models and a full real-filing ingest (~80 MB download, ~5 min)
pytest -m integration             # both required queries; needs real API keys and costs tokens
ruff check . && ruff format --check . && mypy
```

Exit codes: 0 success, 1 runtime error, 2 index missing or stale (the CLI prints the ingest command), 130 Ctrl+C.

## Project status

Implementation follows the build order in LLD §13, each step a checkpoint. See `STATUS.md` for what's built and `TODO.md` for open items. Status stays out of this file: it changes often, and this file shouldn't.

Done means: both required queries pass the integration tests (R&D ≈ 8.3% of net sales, gross margin ≈ 46.9%, citations verified); `ruff check`, `ruff format --check`, `mypy` and `pytest` are clean; and the README answers the assignment's README questions (tool registration, tool choice, information flow, prompt location; HLD §9).

Keep `STATUS.md` and `TODO.md` current: after a task that changes what's built or what's left, propose the specific edits and apply them once approved. That's the same propose-then-"go" workflow as code changes, so they never drift silently.
