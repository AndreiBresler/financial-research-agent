"""The assignment's test queries against the real agent (marker e2e: needs API keys, costs tokens).

Run with: pytest -m e2e (one query: add -k query_1). Skipped when the index isn't built or a key is missing. Every
query in eval/agent_queries.jsonl runs, the two required ones first. The questions and answers are printed at the end of
the run; after a full run where every query passed, they are also written to docs/example-outputs.md, the assignment's
example outputs.
"""

from collections.abc import Iterator

import pytest

from e2e_support import RESULTS_KEY, AgentQuery, QueryResult, format_report, load_agent_queries, run_query
from filing_support import PROJECT_ROOT
from research_agent.agent.graph import AgentGraph
from research_agent.cli import startup_problems
from research_agent.composition import build_agent
from research_agent.config import TEXT_ENCODING, Settings
from research_agent.ingestion.indexer import open_qdrant

QUERIES = load_agent_queries(PROJECT_ROOT / "eval" / "agent_queries.jsonl")
REPORT_PATH = PROJECT_ROOT / "docs" / "example-outputs.md"

# One event loop for the module: the model and Tavily clients keep connections bound to the loop that opened them.
pytestmark = [pytest.mark.e2e, pytest.mark.asyncio(loop_scope="module")]


@pytest.fixture(scope="module")
def graph() -> Iterator[AgentGraph]:
    """Build the real agent once for all queries, or skip when the setup isn't ready."""
    settings = Settings()
    problems = startup_problems(settings)
    if problems:
        pytest.skip("; ".join(problems))
    qdrant_client = open_qdrant(settings.index_dir)
    try:
        yield build_agent(settings, qdrant_client)
    finally:
        qdrant_client.close()


@pytest.fixture(scope="module")
def results(request: pytest.FixtureRequest) -> Iterator[list[QueryResult]]:
    """Collect every query's result for the end-of-run summary; after a full passing run, write them to the report."""
    collected: list[QueryResult] = []
    request.config.stash[RESULTS_KEY] = collected
    yield collected
    # Only a full, passing run replaces the report: a partial run (-k) or a failure would overwrite a good one.
    if len(collected) == len(QUERIES) and all(result.passed for result in collected):
        REPORT_PATH.write_text(format_report(collected), encoding=TEXT_ENCODING)


@pytest.mark.parametrize("query", QUERIES, ids=[query.name for query in QUERIES])
async def test_query(graph: AgentGraph, results: list[QueryResult], query: AgentQuery) -> None:
    """The agent uses the expected tools, states the key figures, and cites only what its tools returned."""
    result = await run_query(graph, query)
    results.append(result)
    assert result.passed, f"{'; '.join(result.failures)}\n\n{result.answer}"
