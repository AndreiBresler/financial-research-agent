"""Unit tests for the search_10k tool (LLD section 7): arguments, output format, Evidence, position mode and errors."""

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from research_agent.models import Evidence
from research_agent.retrieval.store import ChunkStore
from research_agent.tools.output import NO_RELEVANT_CONTENT
from research_agent.tools.search_10k import (
    MISSING_SECTION,
    TOOL_NAME,
    UNKNOWN_SECTION,
    SearchTenKArguments,
    evidence,
    passage,
)
from retrieval_fakes import TEST_FILING_LABEL, build_corpus, build_search_10k
from tool_support import call_tool, evidence_of, markers

LARGE_OUTPUT_LIMIT = 12_000
SMALL_OUTPUT_LIMIT = 120


@pytest.fixture
def tool() -> BaseTool:
    """Return the tool with the default output limit."""
    return build_search_10k()


def assert_tool_error(message: ToolMessage, error_code: str) -> None:
    """Check the call failed as a tool error: status error, the error text for the model, and no Evidence."""
    assert message.status == "error"
    assert str(message.content).startswith(error_code)
    assert message.artifact is None


class TestDefinition:
    """What the model is told about the tool."""

    def test_name_schema_and_async(self, tool: BaseTool) -> None:
        """The tool is called search_10k, takes query, section, order_by, k and kind, and runs asynchronously."""
        schema_fields = set(SearchTenKArguments.model_fields)
        assert tool.name == TOOL_NAME
        assert schema_fields == {"query", "section", "order_by", "k", "kind"}
        assert tool.description
        assert tool.coroutine is not None

    @pytest.mark.parametrize(
        "arguments",
        [
            {"query": "x" * 301},
            {"query": ""},
            {"query": "tax", "k": 0},
            {"query": "tax", "k": 11},
            {"query": "tax", "order_by": "random"},
            {"query": "tax", "kind": "chart"},
        ],
    )
    def test_schema_rejects_bad_arguments(self, arguments: dict[str, object]) -> None:
        """Queries are 1-300 characters, k is 1-10, order_by is relevance or position, kind a chunk kind."""
        with pytest.raises(ValidationError):
            SearchTenKArguments.model_validate(arguments)


class TestRelevance:
    """Hybrid search results, formatted for the model, with Evidence for the renderer."""

    async def test_passages_carry_marker_path_and_page(self, tool: BaseTool) -> None:
        """Each passage opens with its marker, the short path and page, then the chunk text."""
        message = await call_tool(tool, query="tax rates", section="item:1A", k=1)
        content = str(message.content)
        assert content.startswith(
            "[D4] Part I › Item 1A › Financial Risks (p. 12)\nChanges in tax rates can raise the Company’s tax expense."
        )

    async def test_cross_referenced_passages_follow_the_ranked_ones(self, tool: BaseTool) -> None:
        """The tax risk's references to Notes 7 and 3 come after it, with Item 8 shortened in the path."""
        message = await call_tool(tool, query="tax rates", section="item:1A", k=1)
        content = str(message.content)
        assert markers(message) == ["D4", "D12", "D10"]
        assert "[D12] Part II › Item 8 › Note 7 – Provision (p. 42)" in content

    async def test_evidence_matches_the_passages_shown(self, tool: BaseTool) -> None:
        """One Evidence per passage, with the stable D ID and the source line the renderer will print."""
        message = await call_tool(tool, query="tax rates", section="item:1A", k=1)
        evidence = evidence_of(message)
        assert [item.id for item in evidence] == markers(message)
        assert evidence[0] == Evidence(
            id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12"
        )

    async def test_k_defaults_to_top_k(self) -> None:
        """Without k, the tool returns top_k ranked passages (plus any cross-references)."""
        capped_tool = build_search_10k()
        message = await call_tool(capped_tool, query="services margin", section="item:7")
        assert markers(message) == ["D6", "D7"]


class TestPosition:
    """order_by=position returns the first k units of a section, in document order."""

    async def test_item_1a_returns_the_opening_part_of_each_risk_factor(self, tool: BaseTool) -> None:
        """'Top N risk factors' skips the intro and returns one part per risk factor, so a long one can't crowd
        the next out of the output cap."""
        message = await call_tool(tool, query="risk factors", section="item:1A", order_by="position", k=2)
        assert markers(message) == ["D3", "D4"]

    async def test_other_sections_return_units_of_every_kind(self, tool: BaseTool) -> None:
        """Outside Item 1A, position order includes every unit; Item 8 continues into its notes."""
        message = await call_tool(tool, query="statements", section="item:8", order_by="position", k=2)
        assert markers(message) == ["D8", "D9"]

    async def test_position_needs_a_section(self, tool: BaseTool) -> None:
        """Without a section there is no document order to follow, so the model is told to add one."""
        message = await call_tool(tool, query="risk factors", order_by="position")
        assert_tool_error(message, MISSING_SECTION)


class TestPageRanges:
    """A chunk spanning pages cites them as a range, for the model and in Sources."""

    def test_page_range_in_passage_and_evidence(self) -> None:
        """The second part of the tax risk factor spans pages 13 and 14."""
        chunk = ChunkStore(build_corpus()).get(5)
        assert passage(chunk).startswith("[D5] Part I › Item 1A › Financial Risks (pp. 13–14)")
        expected_source = "Form 10-K FY2025 › Part I › Item 1A › Financial Risks, pp. 13–14"
        assert evidence(chunk, TEST_FILING_LABEL).source == expected_source


class TestKind:
    """The kind argument narrows results to tables, risk factors or narrative text."""

    async def test_table_search_returns_tables_only(self, tool: BaseTool) -> None:
        """'Find the figures' as a table search returns the revenue table first and no narrative."""
        message = await call_tool(tool, query="revenue", kind="table")
        message_markers = markers(message)
        assert message_markers[0] == "D8"
        assert set(message_markers) <= {"D7", "D8"}

    async def test_position_with_a_kind_overrides_the_risk_factor_default(self, tool: BaseTool) -> None:
        """Asking Item 1A for text by position returns its intro instead of the risk factors."""
        message = await call_tool(tool, query="intro", section="item:1A", order_by="position", kind="text")
        assert markers(message) == ["D2"]

    async def test_position_with_a_kind_outside_item_1a(self, tool: BaseTool) -> None:
        """Item 8's tables in document order: the statement table, not the notes' text."""
        message = await call_tool(tool, query="statements", section="item:8", order_by="position", kind="table")
        assert markers(message) == ["D8"]

    async def test_miss_with_a_kind_suggests_dropping_it(self, tool: BaseTool) -> None:
        """No tax table exists, so the model is told to retry without the kind filter."""
        message = await call_tool(tool, query="tax", kind="table")
        assert str(message.content) == f"{NO_RELEVANT_CONTENT} for kind table: retry without the kind filter"
        assert evidence_of(message) == []

    async def test_miss_with_section_and_kind_names_both(self, tool: BaseTool) -> None:
        """With both filters set, the retry advice names both."""
        message = await call_tool(tool, query="tax rates", section="item:1A", kind="table")
        expected = f"{NO_RELEVANT_CONTENT} in item:1A for kind table: retry without the section or kind filter"
        assert str(message.content) == expected


class TestErrors:
    """Problems come back to the model as error tool messages it can act on, never as exceptions."""

    async def test_unknown_section_lists_the_valid_ones(self, tool: BaseTool) -> None:
        """An invalid section ID returns the IDs the model can use."""
        message = await call_tool(tool, query="tax", section="item:99")
        content = str(message.content)
        assert_tool_error(message, UNKNOWN_SECTION)
        assert "item:1A" in content
        assert "note:7" in content

    async def test_not_found_in_a_section_suggests_dropping_the_filter(self, tool: BaseTool) -> None:
        """A miss inside a section tells the model to retry without the section filter."""
        message = await call_tool(tool, query="tax rates", section="item:1")
        assert str(message.content) == f"{NO_RELEVANT_CONTENT} in item:1: retry without the section filter"
        assert evidence_of(message) == []

    async def test_not_found_anywhere(self, tool: BaseTool) -> None:
        """A miss across the whole filing says the filing doesn't cover it; that is a finding, not a failure."""
        message = await call_tool(tool, query="weather forecast")
        assert str(message.content).startswith(NO_RELEVANT_CONTENT)
        assert message.status == "success"
        assert evidence_of(message) == []


class TestOutputLimit:
    """Output is capped at tool_output_max_chars without breaking citations."""

    async def test_drops_whole_passages_and_their_evidence(self) -> None:
        """Under a small cap, the output stays within it and Evidence covers exactly the passages shown."""
        small_tool = build_search_10k(tool_output_max_chars=SMALL_OUTPUT_LIMIT)
        message = await call_tool(small_tool, query="tax rates", section="item:1A", k=1)
        evidence = evidence_of(message)
        assert len(str(message.content)) <= SMALL_OUTPUT_LIMIT
        assert markers(message)
        assert [item.id for item in evidence] == markers(message)
