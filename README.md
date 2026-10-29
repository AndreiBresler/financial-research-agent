# Financial Research Agent

A command-line research agent that answers questions about Apple Inc. from its fiscal 2025 Form 10-K and live web data. For each question it shows a plan, runs tools in parallel, computes every number in code, and cites every claim: a 10-K section and page, a web URL and retrieval date, or a calculation.

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
python src/ingest.py                    # builds data/index/ from the filing; no API keys needed
```

`ingest.py` parses `data/aapl-20250927.htm`, chunks it and indexes it in a local Qdrant folder. The first run downloads the embedding models (about 80 MB) and takes a few minutes. Run it again only after changing the parser, the chunker or the embedding models; the agent refuses to start on a missing or stale index and prints this command.

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

# All end-to-end queries with pass/fail checks (tools used, key figures, citation check), saving the answers:
python src/run_e2e.py --output docs/example-outputs.md
python src/run_e2e.py --only query_1_document_only      # one query by name

# The same queries as pytest tests (tests/test_queries.py); needs API keys and costs tokens:
pytest -m integration
```

The queries live in `eval/agent_queries.jsonl`: the two required ones, the assignment's decision-logic examples (risk factors → 10-K only, current stock price → web only, P/E versus Microsoft → both) and a figure the 10-K doesn't disclose. Each names the tools it must and must not use, the figures the answer must contain, and whether it must report a data gap.

### Example

[docs/example-outputs.md](docs/example-outputs.md) holds the answers from the latest end-to-end run. Query 1 below: the plan and tool lines show the format `main.py` prints, and the answer is from that run (abridged).

```text
Plan:
  1. List the first three risk factors in Item 1A (search_10k)
  2. Find R&D expense and total net sales for fiscal 2025 (search_10k)
  3. Divide R&D by net sales (calculator)
→ search_10k(query="risk factors", section="item:1A", order_by="position", k=3)
→ search_10k(query="research and development expense total net sales", kind="table")
← search_10k: D25, D26, D27, ...
← search_10k: D135, ...
→ calculator(expression="34550 / 416161 * 100")
← calculator: C3bd255

Apple spent about 8.3% of total net sales on R&D in fiscal 2025 (fiscal year ended September 27, 2025) [C3bd255].
The filing's first three risk factors cover macroeconomic conditions, geopolitical and business disruptions, and
international trade and tariffs [D25][D26][D27].
...
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

### Configuration and logs

Every setting in `src/research_agent/config.py` can be overridden by an environment variable or a line in `.env` with the same name in capitals, for example `MAX_TOOL_ROUNDS=4` or `LLM_MODEL=anthropic:claude-opus-5-5`. Each run appends JSON log lines to `logs/agent.jsonl`: one per node and tool call, with latency, token usage and outcome. API keys are never logged.

Exit codes: 0 success, 1 the question failed (for example, the model API was unreachable after retries), 2 the index is missing or stale or an API key is missing, 130 interrupted with Ctrl+C.

## Tests

```bash
ruff check . && ruff format --check . && mypy   # lint, format and strict type checks
pytest                                          # unit and graph tests: no API keys, no downloads
pytest -m embedding_models                      # real embedding models and a full ingest of the filing (~80 MB download)
python src/evaluate.py                          # retrieval eval: hit@5 and not-found accuracy
```

The default run needs no API keys: graph and CLI tests drive the real agent graph with a scripted model. The parser tests run against a synthetic filing in `tests/fixtures/` and against the real filing in `data/aapl-20250927.htm`, a public EDGAR document included in the repo.

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
| Claude Sonnet 5.5 (Anthropic API) | Strong tool use and long context at moderate cost; set by `LLM_MODEL`. |
| `beautifulsoup4`, `lxml` | The 10-K's structure lives in inline styles, which generic document loaders lose; a targeted parser keeps it. |
| `qdrant-client`, `fastembed` | Local hybrid search (dense + BM25, fused in Qdrant) with no server, GPU or embedding API. |
| `tavily-python` | Web search built for LLM use; wrapped in our own thin tool to control format, IDs and errors. |
| `simpleeval` | Safe arithmetic: no names, no attribute access, only `round` and `abs`. Models are unreliable at arithmetic and `eval` is unsafe. |
| `pydantic`, `pydantic-settings` | Validated data models and configuration from the environment; API keys as secrets. |
| `structlog`, `rich` | JSON logs per node and tool call; Markdown rendering in the terminal. |
| `pytest`, `ruff`, `mypy` | Tests (no API keys needed), linting and strict typing. |

## Results and limitations

- **The two required queries** pass end to end: the right tools, the key figures (R&D ≈ 8.3% of net sales, gross margin 46.9%), and citations on every claim. Model output varies between runs, so a run can still include an uncited aside; when it does, the answer is shown with a warning listing it.
- **The citation check is strict on purpose.** It catches real lapses, such as a restated figure or an interpretation without a marker. In the latest run of the six end-to-end queries, the warnings were all for such sentences; see `docs/example-outputs.md`.
- **"Top 3 risk factors"** means the first three in the filing's order, since the 10-K doesn't rank them; the answer says so under Assumptions.
- **Web data** is only as current and consistent as the pages found; answers state the period of each figure and list conflicts under Data gaps.
