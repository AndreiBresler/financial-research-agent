"""End-to-end checks of the real agent (assignment test queries): tool choice, figures, grounding and citations.

Each query in eval/agent_queries.jsonl names the tools the agent must use and must not use, figures the answer
must contain, and whether the answer must report a data gap. A query fails on a missed expectation, on a citation
that matches no tool result, on a URL the model wrote, or when a required tool's results go uncited. Sentences
the verifier finds uncited are reported as warnings: model output varies between runs, and the answer already
carries the warning for the user. Used by tests/e2e/test_queries.py; its checks are unit-tested in test_e2e_checks.py.
"""

import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from research_agent.agent.graph import AgentGraph
from research_agent.agent.state import question_input
from research_agent.agent.verify import DATA_GAPS_HEADING, check_answer, evidence_registry
from research_agent.cli import RECURSION_LIMIT
from research_agent.config import TEXT_ENCODING
from research_agent.models import ToolName, Verification
from research_agent.tools.calculator import CALC_ID_PREFIX
from research_agent.tools.calculator import TOOL_NAME as CALCULATOR_NAME
from research_agent.tools.output import cited_ids
from research_agent.tools.search_10k import DOC_ID_PREFIX
from research_agent.tools.search_10k import TOOL_NAME as SEARCH_10K_NAME
from research_agent.tools.web_search import TOOL_NAME as WEB_SEARCH_NAME
from research_agent.tools.web_search import WEB_ID_PREFIX

REPORT_TITLE = "# Example outputs"
REPORT_INTRO = (
    "Answers from the latest full `pytest -m e2e` run, the assignment's two queries first. Each answer is shown as the "
    "CLI renders it: any verification warning, the answer, then the Sources list written by code."
)
REPORT_SEPARATOR = "\n\n"
PASSED_LABEL = "passed"
FAILED_LABEL = "FAILED"
NO_TOOLS = "none"
LIST_SEPARATOR = ", "
ISSUE_SEPARATOR = "; "
MARKER_PREFIX_BY_TOOL = {
    SEARCH_10K_NAME: DOC_ID_PREFIX,
    WEB_SEARCH_NAME: WEB_ID_PREFIX,
    CALCULATOR_NAME: CALC_ID_PREFIX,
}


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
    warnings: list[str] = []

    @property
    def passed(self) -> bool:
        """Return True when every expectation was met."""
        return not self.failures


# Where the e2e test leaves its results, so the end-of-run summary can print them.
RESULTS_KEY = pytest.StashKey[list[QueryResult]]()


def load_agent_queries(path: Path) -> list[AgentQuery]:
    """Read the end-to-end queries, one JSON object per line."""
    lines = path.read_text(encoding=TEXT_ENCODING).splitlines()
    return [AgentQuery.model_validate_json(line) for line in lines if line.strip()]


def uncited_tools(query: AgentQuery, answer: str) -> list[str]:
    """Return the required tools whose results the answer never cites."""
    cited_prefixes = {citation_id[0] for citation_id in cited_ids(answer)}
    return [tool for tool in query.required_tools if MARKER_PREFIX_BY_TOOL[tool] not in cited_prefixes]


def check_result(query: AgentQuery, tools_used: list[str], answer: str, verification: Verification) -> list[str]:
    """Compare a run with the query's expectations and the hard grounding rules; describe every miss."""
    failures = [f"did not use {tool}" for tool in query.required_tools if tool not in tools_used]
    unneeded_tools = [tool for tool in query.forbidden_tools if tool in tools_used]
    failures.extend(f"used {tool}, which this question shouldn't need" for tool in unneeded_tools)
    failures.extend(f"answer lacks {figure}" for figure in query.expected_figures if figure not in answer)
    if query.expect_data_gap and DATA_GAPS_HEADING not in answer:
        failures.append(f"answer has no {DATA_GAPS_HEADING} section")
    failures.extend(f"cites [{citation_id}], which no tool returned" for citation_id in verification.unknown_ids)
    if verification.has_urls:
        failures.append("the model wrote a URL instead of citing a source")
    failures.extend(f"never cites {tool} results" for tool in uncited_tools(query, answer))
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
    messages = state["messages"]
    tools_used = tools_in_order(messages)
    model_answer = messages[-1].text
    verification = check_answer(model_answer, evidence_registry(messages))
    return QueryResult(
        name=query.name,
        question=query.question,
        tools_used=tools_used,
        answer=state["final"] or "",
        failures=check_result(query, tools_used, model_answer, verification),
        warnings=[f"uncited: {text}" for text in verification.uncited],
    )


def summary_lines(result: QueryResult) -> list[str]:
    """Return one query's question, tools, outcome and answer, for the end-of-run summary."""
    outcome = PASSED_LABEL if result.passed else f"{FAILED_LABEL}: {ISSUE_SEPARATOR.join(result.failures)}"
    tools = LIST_SEPARATOR.join(result.tools_used) or NO_TOOLS
    return [f"Q: {result.question}", f"Tools: {tools} · Result: {outcome}", "", result.answer, ""]


def format_report(results: list[QueryResult]) -> str:
    """Render the results as Markdown: each question, the tools it used, its outcome and its answer."""
    sections = [REPORT_TITLE, REPORT_INTRO]
    for result in results:
        outcome = PASSED_LABEL if result.passed else f"{FAILED_LABEL}: {ISSUE_SEPARATOR.join(result.failures)}"
        tools = LIST_SEPARATOR.join(result.tools_used) or NO_TOOLS
        heading = f"## {result.name}\n\n**Question:** {result.question}"
        warnings = f" · **Citation warnings:** {len(result.warnings)}" if result.warnings else ""
        sections.append(f"{heading}\n\n**Tools:** {tools} · **Result:** {outcome}{warnings}")
        sections.append(result.answer)
    return REPORT_SEPARATOR.join(sections)
