"""End-to-end checks of the real agent (assignment test queries): tool choice, key figures and verification.

Each query in eval/agent_queries.jsonl names the tools the agent must use and must not use, figures the answer
must contain, and whether the answer must report a data gap. Shared by src/run_e2e.py and tests/test_queries.py.
"""

import uuid
from collections.abc import Sequence
from pathlib import Path

from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from research_agent.agent.graph import AgentGraph
from research_agent.agent.render import WARNING_PREFIX
from research_agent.agent.state import question_input
from research_agent.agent.verify import DATA_GAPS_HEADING
from research_agent.cli import RECURSION_LIMIT
from research_agent.models import ToolName

FILE_ENCODING = "utf-8"
REPORT_TITLE = "# Example outputs"
REPORT_SEPARATOR = "\n\n"
PASSED_LABEL = "passed"
FAILED_LABEL = "FAILED"
NO_TOOLS = "none"
LIST_SEPARATOR = ", "


class AgentQuery(BaseModel):
    """One end-to-end question and what a correct run looks like."""

    name: str
    question: str
    required_tools: list[ToolName]
    forbidden_tools: list[ToolName] = []
    expected_figures: list[str] = []
    expect_data_gap: bool = False


class QueryResult(BaseModel):
    """What the agent did for one query, and which expectations it missed."""

    name: str
    question: str
    tools_used: list[str]
    answer: str
    failures: list[str]

    @property
    def passed(self) -> bool:
        """Return True when every expectation was met."""
        return not self.failures


def load_agent_queries(path: Path) -> list[AgentQuery]:
    """Read the end-to-end queries, one JSON object per line."""
    lines = path.read_text(encoding=FILE_ENCODING).splitlines()
    return [AgentQuery.model_validate_json(line) for line in lines if line.strip()]


def check_result(query: AgentQuery, tools_used: list[str], answer: str) -> list[str]:
    """Compare a run with the query's expectations and describe every miss."""
    failures = [f"did not use {tool}" for tool in query.required_tools if tool not in tools_used]
    unneeded_tools = [tool for tool in query.forbidden_tools if tool in tools_used]
    failures.extend(f"used {tool}, which this question shouldn't need" for tool in unneeded_tools)
    failures.extend(f"answer lacks {figure}" for figure in query.expected_figures if figure not in answer)
    if query.expect_data_gap and DATA_GAPS_HEADING not in answer:
        failures.append(f"answer has no {DATA_GAPS_HEADING} section")
    if answer.startswith(WARNING_PREFIX):
        failures.append("verification flagged the answer")
    return failures


def tools_in_order(messages: Sequence[BaseMessage]) -> list[str]:
    """Return the names of the tools the run called, each once, in order of first use."""
    names = [message.name for message in messages if isinstance(message, ToolMessage) and message.name]
    return list(dict.fromkeys(names))


async def run_query(graph: AgentGraph, query: AgentQuery) -> QueryResult:
    """Ask one query on a fresh thread and check the result."""
    config: RunnableConfig = {"configurable": {"thread_id": uuid.uuid4().hex}, "recursion_limit": RECURSION_LIMIT}
    try:
        state = await graph.ainvoke(question_input(query.question), config)
    # A failed model or tool call is a failed query, not a crashed run.
    except Exception as exception:
        failure = f"run failed: {type(exception).__name__}: {exception}"
        return QueryResult(name=query.name, question=query.question, tools_used=[], answer="", failures=[failure])
    tools_used = tools_in_order(state["messages"])
    answer = state["final"] or ""
    failures = check_result(query, tools_used, answer)
    return QueryResult(
        name=query.name, question=query.question, tools_used=tools_used, answer=answer, failures=failures
    )


def format_report(results: list[QueryResult]) -> str:
    """Render the results as Markdown: each question, the tools it used, its outcome and its answer."""
    sections = [REPORT_TITLE]
    for result in results:
        outcome = PASSED_LABEL if result.passed else f"{FAILED_LABEL}: {'; '.join(result.failures)}"
        tools = LIST_SEPARATOR.join(result.tools_used) or NO_TOOLS
        heading = f"## {result.name}\n\n**Question:** {result.question}"
        sections.append(f"{heading}\n\n**Tools:** {tools} · **Result:** {outcome}")
        sections.append(result.answer)
    return REPORT_SEPARATOR.join(sections)
