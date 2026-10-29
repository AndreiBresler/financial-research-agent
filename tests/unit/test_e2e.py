"""Unit tests for the end-to-end checks (assignment test queries): expectations, the query file and the report."""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from filing_support import PROJECT_ROOT
from research_agent.e2e import AgentQuery, QueryResult, check_result, format_report, load_agent_queries, tools_in_order
from research_agent.models import Verification

QUERIES_PATH = PROJECT_ROOT / "eval" / "agent_queries.jsonl"
ASSIGNMENT_QUERY_1 = (
    "What are Apple's top 3 risk factors mentioned in their latest 10-K, and what percentage of total revenue did "
    "they spend on R&D?"
)
ASSIGNMENT_QUERY_2 = (
    "How does Apple's gross margin compare to Microsoft's current gross margin, and what reasons does Apple cite in "
    "their 10-K for any margin pressure?"
)
DOCUMENT_QUERY = AgentQuery(
    name="query_1",
    question="q",
    required_tools=["search_10k", "calculator"],
    forbidden_tools=["web_search"],
    expected_figures=["8.3"],
)
GOOD_ANSWER = "R&D was $34,550 million [D135], which is 8.3% of net sales [C3bd255]."
PASSED = Verification()


class TestQueryFile:
    """eval/agent_queries.jsonl holds the assignment's two queries verbatim."""

    def test_assignment_queries_are_included_verbatim(self) -> None:
        """Both required questions are asked exactly as the assignment words them."""
        questions = [query.question for query in load_agent_queries(QUERIES_PATH)]
        assert ASSIGNMENT_QUERY_1 in questions
        assert ASSIGNMENT_QUERY_2 in questions

    def test_names_are_unique(self) -> None:
        """--only selects queries by name."""
        names = [query.name for query in load_agent_queries(QUERIES_PATH)]
        assert len(names) == len(set(names))


class TestCheckResult:
    """Each expectation and grounding rule produces one readable failure when it is missed."""

    def test_all_expectations_met(self) -> None:
        """Required tools used and cited, no forbidden tool, figure present, no fabricated citation."""
        assert check_result(DOCUMENT_QUERY, ["search_10k", "calculator"], GOOD_ANSWER, PASSED) == []

    def test_missing_and_forbidden_tools(self) -> None:
        """Skipping the calculator and reaching for the web are both reported."""
        failures = check_result(DOCUMENT_QUERY, ["search_10k", "web_search"], GOOD_ANSWER, PASSED)
        assert failures[:2] == ["did not use calculator", "used web_search, which this question shouldn't need"]

    def test_missing_figure(self) -> None:
        """The answer must contain the key figure."""
        answer = "R&D was a large share of net sales [C3bd255], per the statement of operations [D135]."
        failures = check_result(DOCUMENT_QUERY, ["search_10k", "calculator"], answer, PASSED)
        assert failures == ["answer lacks 8.3"]

    def test_fabricated_citation_fails(self) -> None:
        """A marker that matches no tool result is a grounding failure."""
        verification = Verification(unknown_ids=["D999"])
        failures = check_result(DOCUMENT_QUERY, ["search_10k", "calculator"], GOOD_ANSWER, verification)
        assert failures == ["cites [D999], which no tool returned"]

    def test_model_written_url_fails(self) -> None:
        """Sources come from code; a URL in the answer is a grounding failure."""
        verification = Verification(has_urls=True)
        failures = check_result(DOCUMENT_QUERY, ["search_10k", "calculator"], GOOD_ANSWER, verification)
        assert failures == ["the model wrote a URL instead of citing a source"]

    def test_required_tool_left_uncited_fails(self) -> None:
        """Using the 10-K but citing only the calculation doesn't show where the inputs came from."""
        answer = "R&D was 8.3% of net sales [C3bd255]."
        failures = check_result(DOCUMENT_QUERY, ["search_10k", "calculator"], answer, PASSED)
        assert failures == ["never cites search_10k results"]

    def test_uncited_sentences_do_not_fail(self) -> None:
        """An uncited aside is a warning on the answer, not a failed query."""
        verification = Verification(uncited=["The gap is roughly structural."])
        assert check_result(DOCUMENT_QUERY, ["search_10k", "calculator"], GOOD_ANSWER, verification) == []

    def test_data_gap_expected(self) -> None:
        """A question the filing can't answer must say so under Data gaps."""
        query = AgentQuery(name="gap", question="q", required_tools=["search_10k"], expect_data_gap=True)
        answer = "Brazil isn't broken out [D234]."
        assert check_result(query, ["search_10k"], answer, PASSED) == ["answer has no ### Data gaps section"]
        answer_with_gap = f"{answer}\n\n### Data gaps\n- Brazil net sales aren't disclosed."
        assert check_result(query, ["search_10k"], answer_with_gap, PASSED) == []


class TestToolsInOrder:
    """The tools used are read from the run's tool results."""

    def test_each_tool_once_in_order_of_first_use(self) -> None:
        """Repeated calls count once."""
        messages = [
            HumanMessage("q"),
            ToolMessage("a", tool_call_id="1", name="search_10k"),
            ToolMessage("b", tool_call_id="2", name="web_search"),
            ToolMessage("c", tool_call_id="3", name="search_10k"),
            AIMessage("answer"),
        ]
        assert tools_in_order(messages) == ["search_10k", "web_search"]


class TestReport:
    """--output writes each question, its tools, its outcome and its answer."""

    def test_report_lists_outcome_and_answer(self, tmp_path: Path) -> None:
        """A failed query shows why; a passed one says so."""
        results = [
            QueryResult(name="ok", question="Q1?", tools_used=["search_10k"], answer="A1 [D4].", failures=[]),
            QueryResult(name="bad", question="Q2?", tools_used=[], answer="", failures=["did not use web_search"]),
        ]
        report = format_report(results)
        assert "## ok" in report
        assert "**Result:** passed" in report
        assert "A1 [D4]." in report
        assert "FAILED: did not use web_search" in report

    def test_report_counts_citation_warnings(self) -> None:
        """Uncited sentences show up in the report without failing the query."""
        result = QueryResult(
            name="ok", question="Q?", tools_used=["search_10k"], answer="A [D4].", failures=[], warnings=["uncited: x"]
        )
        assert "**Result:** passed · **Citation warnings:** 1" in format_report([result])
