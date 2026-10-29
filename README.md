# Financial Research Agent

A command-line research agent that answers questions about Apple Inc. from its fiscal 2025 Form 10-K and live web data. For each question it shows a plan, runs tools in parallel, computes every number in code, and cites every claim: a 10-K section and page, a web URL and retrieval date, or a calculation.

## Start here: run the end-to-end tests

Apple's latest 10-K, for fiscal year 2025 (ended September 27, 2025), is already ingested: the filing is in `data/` and its index in `data/index/`, so there is no ingestion step.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # fill in ANTHROPIC_API_KEY and TAVILY_API_KEY (see API keys below)
pytest -m e2e               # the 2 required queries + 4 more, against the real Claude and Tavily APIs
```

- **What runs:** `tests/e2e/test_queries.py` asks the six questions in `eval/agent_queries.jsonl`: the assignment's two required queries, its decision-logic examples (risk factors → 10-K only, current stock price → web only, P/E versus Microsoft → both) and a figure the 10-K doesn't disclose.
- **What each test checks:** the right tools were used (and a "just use X" question used only X), the key figures are in the answer (R&D 8.3% of net sales, gross margin 46.9%), a missing figure is reported under Data gaps, every citation matches a tool result, the model wrote no URLs, and every tool's results are cited.
- **Output:** pass or fail per query, then, at the end of the run, each question with the agent's full answer and its Sources, the two required queries first. After a full run the answers are also written to [docs/example-outputs.md](docs/example-outputs.md). Run one query with `pytest -m e2e -k query_1`.
- **The latest answers to the assignment's two queries:** [Query 1, document only](docs/example-outputs.md#query_1_document_only) and [Query 2, document and web](docs/example-outputs.md#query_2_hybrid).
- **Good to know:** the run costs API tokens and takes a few minutes; the first run downloads the embedding models (about 80 MB). Without API keys the tests are skipped, and the reason is shown with `-rs`.
- **Model:** Claude Haiku 5.5 by default (about 2¢ per full run). To run with Claude Sonnet 5.5 instead, see [Choosing the model](#choosing-the-model).
- **Without API keys:** `pytest` runs the 399 unit and integration tests in about 7 seconds.

## Design

- [High-level design](docs/high-level-design.md): scope, architecture, agent loop, 10-K handling, reliability and security, path to production.
- [Low-level design](docs/low-level-design.md): modules, data models, ingestion stages, tool contracts, graph, tests and build order.

## Setup

Requires Python 3.12. The embedding models run locally on the CPU; no GPU is needed.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt     # runtime dependencies plus pytest, ruff and mypy
cp .env.example .env                    # then fill in ANTHROPIC_API_KEY and TAVILY_API_KEY
```

The fiscal 2025 10-K is already ingested (`data/index/`); to ingest another filing, see [Ingesting a filing](#ingesting-a-filing).

### API keys

The agent needs two keys: one for Claude (the model) and one for Tavily (web search). Ingestion, the retrieval eval and `pytest` without `-m e2e` need neither.

1. **Anthropic:** sign in at [console.anthropic.com](https://console.anthropic.com), add credits under Settings → Billing, then create a key under API Keys. It starts with `sk-ant-`.
2. **Tavily:** sign up at [tavily.com](https://tavily.com); the free tier gives 1,000 searches a month. Copy the API key from the dashboard. It starts with `tvly-`.
3. Put both in `.env`, which is gitignored, so the keys never reach git:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` so it reads, with your own keys:

   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   TAVILY_API_KEY=tvly-your-key-here
   ```

   Or export them for the current shell instead; environment variables take precedence over `.env`:

   ```bash
   export ANTHROPIC_API_KEY=sk-ant-your-key-here
   export TAVILY_API_KEY=tvly-your-key-here
   ```

The agent checks both keys at startup and stops with a message naming any missing one (exit code 2); the e2e tests are skipped with the same reason. Keys are read as secrets and never logged. A full e2e run costs about 2¢ with the default model, and Anthropic's console shows usage and the remaining balance (Usage, and Settings → Billing).

## Usage

Ask one question, or start a session:

```bash
python src/main.py "What are Apple's top three risk factors?"   # answers once and exits
python src/main.py                                               # interactive session
python src/main.py --verbose "..."                               # also prints full tool outputs and debug logs
```

In a session, follow-up questions share the conversation, so they can refer to earlier answers. Type `/new` to start a new conversation and `/quit` (or Ctrl+D) to exit.

For each question the agent prints its plan, then each tool call and result as it happens, then the answer. Every fact and number in the answer carries a citation marker: `[D…]` for a 10-K passage, `[W…]` for a web result, `[C…]` for a calculation. The Sources list under the answer is written by code from the tool results, not by the model. If a claim can't be tied to a source, a warning above the answer lists it.

### Running the test queries

```bash
# The assignment's two queries, one at a time, with the live plan and tool calls:
python src/main.py "What are Apple's top 3 risk factors mentioned in their latest 10-K, and what percentage of total revenue did they spend on R&D?"
python src/main.py "How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in their 10-K for any margin pressure?"

# All end-to-end queries as tests (tests/e2e/test_queries.py), writing the answers to docs/example-outputs.md;
# needs API keys and costs tokens:
pytest -m e2e
pytest -m e2e -k query_1                                # one query by name
```

The queries live in `eval/agent_queries.jsonl`: the two required ones, the assignment's decision-logic examples (risk factors → 10-K only, current stock price → web only, P/E versus Microsoft → both) and a figure the 10-K doesn't disclose. Each names the tools it must and must not use, the figures the answer must contain, and whether it must report a data gap. A query fails on a missed expectation, on a citation that matches no tool result, on a URL the model wrote, or when a required tool's results go uncited. Sentences the citation check finds uncited are listed as warnings: the answer shows them to the user, but they don't fail the run, because model wording varies between runs.

### Example

[docs/example-outputs.md](docs/example-outputs.md) holds the answers from the latest end-to-end run. Query 1 below: the plan and tool lines show the format `main.py` prints, and the answer is from an end-to-end run (abridged).

```text
Plan:
  1. List the first three risk factors in Item 1A (search_10k)
  2. Find R&D expense and total net sales for fiscal 2025 (search_10k)
  3. Divide R&D by net sales (calculator)
→ search_10k(query="risk factors", section="item:1A", order_by="position", k=3)
→ search_10k(query="research and development expense total net sales", kind="table")
← search_10k: D25, D26, D38
← search_10k: D135, ...
→ calculator(expression="34550 / 416161 * 100")
← calculator: C3bd255

Top 3 risk factors
 1 Economic conditions. Global and regional economic conditions can materially hurt Apple's business, results,
   financial condition and stock price. Sales outside the U.S. are a majority of net sales [D25].
 2 Political and other disruptions. Political events, trade and other international disputes, geopolitical
   tensions, conflict, natural disasters and public health issues can have a material adverse effect on Apple [D26].
 3 Competition and rapid technological change. Apple's markets are highly competitive, and it must make significant
   R&D investments that may not achieve expected returns [D38].

R&D as a share of total net sales, fiscal 2025
 • Research and development expense was $34,550 million [D135].
 • Total net sales were $416,161 million [D135].
 • The share is 34,550 / 416,161 × 100 = 8.30% [C3bd255].

Assumptions
 • "Top 3" means the first three risk factors in the order the filing lists them. The filing doesn't rank risks by importance.

Sources
 • [C3bd255] 34550 / 416161 * 100 = 8.302075
 • [D25] Form 10-K FY2025 › Part I › Item 1A › Macroeconomic and Industry Risks, p. 5
 • [D135] Form 10-K FY2025 › Part II › Item 8 › CONSOLIDATED STATEMENTS OF OPERATIONS, p. 29
 ...
```

### Choosing the model

The agent uses **Claude Haiku 5.5** by default: about 2¢ per full end-to-end run. **Claude Sonnet 5.5** costs about 40¢ per run and reasons and cites more carefully; with Haiku, a run can occasionally mis-copy a citation marker, which the verifier flags. The model is the `LLM_MODEL` setting.

For one command, put the setting in front of it:

```bash
LLM_MODEL=anthropic:claude-sonnet-5-5 pytest -m e2e
LLM_MODEL=anthropic:claude-sonnet-5-5 python src/main.py "How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in their 10-K for any margin pressure?"
LLM_MODEL=anthropic:claude-sonnet-5-5 python src/main.py
```

To change it for every run, add one line to `.env`:

```bash
echo 'LLM_MODEL=anthropic:claude-sonnet-5-5' >> .env
```

To go back to the default, delete that line from `.env`, or set it explicitly:

```bash
LLM_MODEL=anthropic:claude-haiku-5-5 pytest -m e2e
```

### Configuration and logs

Every setting in `src/research_agent/config.py` can be overridden by an environment variable or a line in `.env` with the same name in capitals, for example `MAX_TOOL_ROUNDS=4` or `LLM_MODEL=anthropic:claude-sonnet-5-5` for a stronger, more expensive model. Each run appends JSON log lines to `logs/agent.jsonl`: one per node and tool call, with latency, token usage and outcome. API keys are never logged.

Exit codes: 0 success, 1 the question failed (for example, the model API was unreachable after retries), 2 the index is missing or stale or an API key is missing, 130 interrupted with Ctrl+C.

## Ingesting a filing

The repository ships with Apple's fiscal 2025 10-K already ingested. To index another version, such as next year's filing:

1. Download the 10-K's HTML document from [Apple's EDGAR filings](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=10-K) into `data/`.
2. Point the configuration at it, in `.env` or the environment:

   ```bash
   SOURCE_HTML=data/aapl-20260926.htm     # the file you downloaded
   FILING_LABEL="Form 10-K FY2026"        # how Sources name the filing
   ```

   The page-footer pattern (`PAGE_FOOTER_PATTERN`) matches Apple's footer for any year; change it only if the footer's format changes.
3. Build the index, then check retrieval:

   ```bash
   python src/ingest.py      # parses, chunks and indexes into data/index/: about a minute, no API keys needed
   python src/evaluate.py    # retrieval eval: hit@5 and not-found accuracy
   ```

`ingest.py` replaces the previous index. It writes a manifest last, with the filing's hash, the parser version and the embedding models; the agent refuses to start on an index that doesn't match its configuration and prints the ingest command. Re-run ingestion also after changing the parser, the chunker or the embedding models.

The prompts and tool descriptions name fiscal 2025 (`prompts/`, the tool docstrings), and the end-to-end checks and retrieval eval expect fiscal 2025 figures and sections; update them for another year.

## Tests

```bash
pytest                                          # unit + integration tests: 399 tests, ~7 s, no API keys
pytest tests/unit                               # unit tests only: one module at a time, with fakes
pytest tests/integration                        # integration tests only: components together, no paid APIs
pytest -m embedding_models                      # opt-in integration tests: real embedding models and a full ingest (~80 MB download)
pytest -m e2e                                   # end-to-end tests: real Claude and Tavily APIs (see Start here)
ruff check . && ruff format --check . && mypy   # lint, format and strict type checks
python src/evaluate.py                          # retrieval eval: hit@5 and not-found accuracy
```

The tests are split by folder: `tests/unit` tests one module at a time with fakes, the mini fixture or an in-memory index; `tests/integration` tests components together without paid APIs, such as the graph and CLI driving the real agent graph with a scripted model, the ingestion pipeline, and the parser on the real filing; `tests/e2e` calls the real APIs. Plain `pytest` runs the first two and needs no API keys. The parser tests run against a synthetic filing in `tests/fixtures/` and against the real filing in `data/aapl-20250927.htm`, a public EDGAR document included in the repo.

## Architecture

```
question → plan → agent ⇄ tools → verify → answer with Sources
                    │
                    ├── search_10k   10-K passages (hybrid search over the local index)
                    ├── web_search   Tavily results, wrapped as untrusted content
                    └── calculator   arithmetic in code
```

- **How tools are registered.** Each tool is a LangChain `@tool` built by a factory that injects its dependencies (`make_search_10k`, `make_web_search`, `make_calculator` in `src/research_agent/tools/`), with a Pydantic argument schema. `composition.build_agent` creates the three tools once and passes them to `build_graph`, which binds them to the model (`bind_tools`) and runs them in LangGraph's `ToolNode`, concurrently when the model requests several in one step.
- **How the agent chooses a tool.** Claude decides, through native function calling. Its guidance is the tool descriptions (each tool's docstring, written for the model) and the system prompt's rule: the 10-K for risks, explanations and reported figures; the web for market data, competitors and post-filing events; the calculator for every derived number. A plan step runs first and names a tool per step, and the plan is shown to the user before any tool runs.
- **How information flows.** The plan node asks for a structured `Plan`. The agent node calls the model with the tools; each tool returns text for the model plus `Evidence` for the code, under stable citation markers (`D` + chunk, `W`/`C` + a hash of the URL or expression). The loop ends when the model answers or the tool budget (`MAX_TOOL_ROUNDS`, default 6) is used up, in which case the model answers from what it gathered. The verify node then checks the answer in code: every marker must exist, every paragraph, list item and number must cite one, and the model must not write URLs. Code renders the Sources list from the Evidence, and a failed check puts a warning above the answer.
- **Where prompts are stored.** In `prompts/`: `system.txt` (rules, tool choice, citations, untrusted web content), `examples.txt` (a formatted answer), `planner.txt` (the plan step) and `final.txt` (the forced answer at the tool budget). Tool descriptions live in each tool's docstring next to its argument schema, so the description and the contract change together; the assignment's suggested `tool_descriptions.txt` would duplicate them.
- **How the 10-K is handled.** A targeted parser (`src/research_agent/ingestion/`) keeps the filing's structure: Parts, Items, notes, each risk factor as a unit, printed page numbers, and tables as Markdown with their headers. Chunks of at most 400 tokens carry their section path, pages and cross-references (such as "see Note 7"); search follows one hop of cross-references. The index is local Qdrant with dense (`bge-small`) and keyword (BM25) vectors fused by RRF; a minimum dense score decides "not found".

The [high-level](docs/high-level-design.md) and [low-level](docs/low-level-design.md) design documents cover the reasoning behind each choice.

## Dependencies

| Package | Why |
|---|---|
| `langgraph` | An explicit graph (plan → agent ⇄ tools → verify) whose nodes are testable, with parallel tool execution and conversation threads built in. |
| `langchain`, `langchain-anthropic` | `init_chat_model` makes the model a setting; `@tool` and messages give one interface for tools and history. |
| Claude Haiku 5.5 (Anthropic API) | Default model: passes all end-to-end tests at about a twentieth of Sonnet 5.5's cost (about 2¢ per full run instead of 40¢). `LLM_MODEL=anthropic:claude-sonnet-5-5` switches to Sonnet for stronger reasoning. |
| `beautifulsoup4`, `lxml` | The 10-K's structure lives in inline styles, which generic document loaders lose; a targeted parser keeps it. |
| `qdrant-client`, `fastembed` | Local hybrid search (dense + BM25, fused in Qdrant) with no server, GPU or embedding API. |
| `tavily-python` | Web search built for LLM use; wrapped in our own thin tool to control format, IDs and errors. |
| `simpleeval` | Safe arithmetic: no names, no attribute access, only `round` and `abs`. Models are unreliable at arithmetic and `eval` is unsafe. |
| `pydantic`, `pydantic-settings` | Validated data models and configuration from the environment; API keys as secrets. |
| `structlog`, `rich` | JSON logs per node and tool call; Markdown rendering in the terminal. |
| `pytest`, `ruff`, `mypy` | Tests (no API keys needed), linting and strict typing. |

## Results and limitations

- **The two required queries** pass end to end: the right tools, the key figures (R&D ≈ 8.3% of net sales, gross margin 46.9%), and cited sources from each tool. See `docs/example-outputs.md`.
- **The citation check is strict on purpose.** It flags any paragraph, list item or figure without a marker, including asides such as a caveat or an interpretation. Model wording varies between runs, so some answers carry such a warning; it is shown above the answer and counted in the end-to-end report.
- **"Top 3 risk factors"** means the first three in the filing's order, since the 10-K doesn't rank them; the answer says so under Assumptions.
- **Web data** is only as current and consistent as the pages found; answers state the period of each figure and list conflicts under Data gaps.
