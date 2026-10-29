# Financial Research Agent

A command-line agent that answers questions about Apple Inc. from its fiscal 2025 Form 10-K and live web data. For each question it shows a plan, runs its tools (10-K search, web search, calculator) in parallel where it can, computes every number in code, and cites every claim: a 10-K section and page, a web URL and retrieval date, or a calculation. A check in code, not the model, flags any claim without a source.

The 10-K is already parsed and indexed (`data/index/`), so there is nothing to ingest before the first run. The design and its reasoning are in the [high-level](docs/high-level-design.md) and [low-level](docs/low-level-design.md) design documents.

## How it works

```
 Offline, once per filing:
   10-K HTML ──► parse (sections, risk factors, tables, pages) ──► chunk ──► embed ──► local index (Qdrant)
                                                                                            │
 Per question:                                                                              │
   question ──► plan ──► agent (Claude) ◄──► tools ── search_10k ── hybrid search ──────────┘
                              │                 ├── web_search ── Tavily
                              │                 └── calculator ── arithmetic in code
                              ▼
                      verify (code): every claim cited? ──► answer + Sources
```

- **How tools are registered.** Each tool is a LangChain `@tool` with a Pydantic argument schema, built by a factory that injects its dependencies (`src/research_agent/tools/`). `composition.build_agent` creates them once; the graph binds them to the model and runs them in LangGraph's `ToolNode`, in parallel when the model asks for several at once.
- **How the agent chooses a tool.** Claude decides through native function calling, guided by each tool's description (its docstring) and the system prompt: the 10-K for risks, explanations and reported figures; the web for market data, competitors and recent events; the calculator for every derived number. A plan step runs first and is shown before any tool runs.
- **How information flows.** Plan → the agent calls tools until it can answer, up to 6 rounds → verify checks the answer in code: every citation must match a tool result, every paragraph and number must cite one, and the model must not write URLs. Code, not the model, writes the Sources list.
- **Where prompts are stored.** `prompts/`: `system.txt` (rules), `planner.txt` (plan step), `examples.txt` (a formatted answer), `final.txt` (answer when the tool budget runs out). Tool descriptions live in the tool docstrings, next to the arguments they describe.

How this layout maps to the assignment's suggested one: `agent.py` → `src/research_agent/agent/` (graph, nodes, verify, render); `tools/document_qa.py` → `tools/search_10k.py`, backed by `retrieval/` and `ingestion/`; `tools/tavily_search.py` → `tools/web_search.py`; `utils/` → `config.py`, `models.py`, `log.py`, `prompts.py`; `prompts/system_prompt.txt` → `prompts/system.txt`; `tool_descriptions.txt` → the tool docstrings; `tests/test_queries.py` → `tests/e2e/test_queries.py`.

## Setup

Requires Python 3.12. Everything else runs locally on the CPU.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # runtime dependencies plus pytest, ruff and mypy
```

### API keys

The agent needs two keys: Anthropic for the model and Tavily for web search. The unit and integration tests need neither.

1. **Anthropic:** at [console.anthropic.com](https://console.anthropic.com), add credits under Settings → Billing, then create a key under API Keys (it starts with `sk-ant-`).
2. **Tavily:** sign up at [tavily.com](https://tavily.com) (the free tier gives 1,000 searches a month) and copy the key from the dashboard (it starts with `tvly-`).
3. Copy the template and fill in your keys:

   ```bash
   cp .env.example .env
   ```

   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   TAVILY_API_KEY=tvly-your-key-here
   ```

`.env` is gitignored, so keys never reach git. Exported environment variables work too and take precedence. The agent checks both keys at startup and names any missing one; keys are never logged.

## Asking questions

```bash
python src/main.py                                               # interactive session
python src/main.py "What are Apple's top three risk factors?"    # one question, then exit
python src/main.py --verbose "..."                               # also prints full tool outputs and the log lines
```

In a session, follow-up questions share the conversation. `/new` starts a new conversation, `/quit` exits.

For each question the agent prints its plan, each tool call and result as it happens, then the answer with a Sources list. Markers in the answer point to the sources: `[D…]` a 10-K passage, `[W…]` a web result, `[C…]` a calculation.

### The two required queries

```bash
python src/main.py "What are Apple's top 3 risk factors mentioned in their latest 10-K, and what percentage of total revenue did they spend on R&D?"
python src/main.py "How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in their 10-K for any margin pressure?"
```

Answers from the latest test run: [docs/example-outputs.md](docs/example-outputs.md).

### Choosing the model

The default is Claude Haiku 5.5 (about 2¢ for the full end-to-end run). To use Claude Sonnet 5.5 (about 40¢), set `LLM_MODEL`:

```bash
LLM_MODEL=anthropic:claude-sonnet-5-5 python src/main.py        # for one command
echo 'LLM_MODEL=anthropic:claude-sonnet-5-5' >> .env            # for every run
```

Every other setting in `src/research_agent/config.py` can be changed the same way, for example `MAX_TOOL_ROUNDS=4`. Logs go to `logs/agent.jsonl`, one JSON line per step and tool call.

## Running the tests

```bash
pytest                                          # unit + integration tests: no API keys, a few seconds
pytest tests/unit                               # unit tests only
pytest tests/integration -m "not e2e"           # all integration tests, including the real embedding models
pytest -m embedding_models                      # only the real-embedding-model tests (~80 MB download, ~5 min)
pytest -m e2e                                   # end-to-end: real Claude and Tavily APIs, needs keys, costs tokens
ruff check . && ruff format --check . && mypy   # lint, format and type checks
```

Plain `pytest` skips the end-to-end and embedding-model tests, because they cost tokens or download models.

**End-to-end tests** (`tests/e2e/test_queries.py`) ask the six questions in `eval/agent_queries.jsonl`: the two required queries, the assignment's tool-choice examples (risk factors → 10-K only, stock price → web only, P/E vs. Microsoft → both) and a figure the 10-K doesn't disclose. Each checks the tools used, the key figures (R&D 8.3% of net sales, gross margin 46.9%), that every citation matches a tool result, and that a missing figure is reported. The answers are printed at the end of the run and, when all pass, written to `docs/example-outputs.md`. Run one query with `pytest -m e2e -k query_1`.

**Retrieval eval:** `python src/evaluate.py` measures hit@5 and not-found accuracy of the 10-K search.

## Ingesting another filing

Download the 10-K HTML from [Apple's EDGAR filings](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=10-K) into `data/`, point the settings at it and rebuild the index (about a minute, no API keys):

```bash
SOURCE_HTML=data/aapl-20260926.htm FILING_LABEL="Form 10-K FY2026" python src/ingest.py
```

Put the same two settings in `.env` so the agent uses the new index; it refuses to start on an index that doesn't match its settings. The prompts and the end-to-end checks name fiscal 2025, so update them for another year.

## Demo vs. production

The demo is built to run on a reviewer's laptop with two API keys and nothing else installed. The design is the same in production; what changes is what each part runs on.

| Area | Demo, and why | Production, and why |
|---|---|---|
| Model | Claude **Haiku 5.5**: about 20× cheaper than Sonnet (2¢ vs. 40¢ per test run) and passes the tests. | Claude **Sonnet 5.5**: more precise reasoning and citations (Haiku occasionally mis-copies a citation marker, which the verifier flags). Accuracy matters more than cost here. |
| Model access | Public Anthropic API with a personal key: simplest setup. | Private endpoint (such as Bedrock) behind a model gateway: data stays in the bank's cloud, with quotas, fallback models and cost tracking. |
| Interface | CLI, as the assignment asks. | An API service (FastAPI or LangGraph Server) on Kubernetes with SSO and role-based access, so other apps and users can call it. |
| Tools | Plain functions in the same process: easy to test. | MCP servers behind a tool gateway: shared by other agents, deployed, secured and audited separately. |
| Conversation state | In memory: one user, lost on exit. | PostgreSQL checkpointer: survives restarts and is shared across replicas. |
| Retrieval | Qdrant in local mode with CPU embeddings: no server or GPU to install. | A Qdrant cluster or the bank's standard vector store, a reranker for precision, and exact figures from the filing's XBRL data instead of parsed HTML tables. |
| Ingestion | A manual command, one filing. | A scheduled pipeline (EDGAR poller → queue → workers) that picks up new filings for many companies. |
| Quality | Unit, integration and end-to-end tests and a retrieval eval. | A golden question set scored by an LLM judge (validated against human labels) as a release gate in CI, plus monitoring of live answers. |
| Security and audit | Keys in `.env`, logs in a local file. | A secrets manager, guardrails for personal data and prompt injection, an immutable audit trail and OpenTelemetry tracing. |

## Dependencies

| Package | Why |
|---|---|
| `langgraph` | An explicit graph (plan → agent ⇄ tools → verify) whose steps are testable, with parallel tool calls and conversation threads built in. |
| `langchain`, `langchain-anthropic` | The model is a setting (`init_chat_model`); one interface for tools and messages. |
| `beautifulsoup4`, `lxml` | The 10-K's structure lives in inline styles, which generic loaders lose; a targeted parser keeps it. |
| `qdrant-client`, `fastembed` | Local hybrid search (meaning + keywords) with no server, GPU or embedding API. |
| `tavily-python` | Web search built for LLMs, wrapped in our own tool to control format, citations and errors. |
| `simpleeval` | Safe arithmetic: models are unreliable at math and `eval` is unsafe. |
| `pydantic`, `pydantic-settings` | Validated data and configuration; API keys handled as secrets. |
| `structlog`, `rich` | JSON logs per step and tool call; Markdown answers in the terminal. |
| `pytest`, `ruff`, `mypy` | Tests without API keys, linting and strict typing. |
