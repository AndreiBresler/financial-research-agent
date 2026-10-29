"""The assignment's test queries against the real agent (marker integration: needs API keys, costs tokens).

Run with: pytest -m integration. Skipped when the index isn't built or a key is missing. Every query in
eval/agent_queries.jsonl runs, the two required ones first; src/run_e2e.py runs the same queries with full output.
"""

from collections.abc import Iterator

import pytest

from filing_support import PROJECT_ROOT
from research_agent.agent.graph import AgentGraph
from research_agent.cli import startup_problems
from research_agent.composition import build_agent, open_qdrant
from research_agent.config import Settings
from research_agent.e2e import AgentQuery, load_agent_queries, run_query

QUERIES = load_agent_queries(PROJECT_ROOT / "eval" / "agent_queries.jsonl")

# One event loop for the module: the model and Tavily clients keep connections bound to the loop that opened them.
pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]


@pytest.fixture(scope="module")
def graph() -> Iterator[AgentGraph]:
    """Build the real agent once for all queries, or skip when the setup isn't ready."""
    settings = Settings()
    problems = startup_problems(settings)
    if problems:
        pytest.skip("; ".join(problems))
    qdrant_client = open_qdrant(settings)
    try:
        yield build_agent(settings, qdrant_client)
    finally:
        qdrant_client.close()


@pytest.mark.parametrize("query", QUERIES, ids=[query.name for query in QUERIES])
async def test_query(graph: AgentGraph, query: AgentQuery) -> None:
    """The agent uses the expected tools, states the key figures, and its answer passes verification."""
    result = await run_query(graph, query)
    assert result.passed, f"{'; '.join(result.failures)}\n\n{result.answer}"
