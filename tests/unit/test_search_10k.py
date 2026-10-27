"""Unit tests for the search_10k tool (LLD section 7): arguments, output format, Evidence, position mode and errors."""

import re

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from research_agent.models import Evidence
from research_agent.retrieval.index import Index
from research_agent.retrieval.search import SearchConfig, Searcher
from research_agent.retrieval.store import ChunkStore
from research_agent.tools.search_10k import (
    MISSING_SECTION,
    NO_RELEVANT_CONTENT,
    TOOL_NAME,
    UNKNOWN_SECTION,
    SearchTenKArguments,
    make_search_10k,
)
from retrieval_fakes import build_corpus, index_corpus

FILING_LABEL = "Form 10-K FY2025"
TOP_K = 2
LARGE_OUTPUT_LIMIT = 12_000
SMALL_OUTPUT_LIMIT = 120
MARKER_PATTERN = re.compile(r"^\[(D\d+)\] ", re.MULTILINE)


def build_tool(tool_output_max_chars: int = LARGE_OUTPUT_LIMIT) -> BaseTool:
    """Build search_10k over the indexed corpus."""
    corpus = build_corpus()
    client, dense_embedder, sparse_embedder = index_corpus(corpus)
    store = ChunkStore(corpus)
    config = SearchConfig(min_dense_score=0.5, prefetch_limit=20, rrf_k=60, xref_max_extra=3)
    searcher = Searcher(store, Index(client, dense_embedder, sparse_embedder), config)
    return make_search_10k(
        store=store,
        searcher=searcher,
        top_k=TOP_K,
        tool_output_max_chars=tool_output_max_chars,
        filing_label=FILING_LABEL,
    )


@pytest.fixture
def tool() -> BaseTool:
    """Return the tool with the default output limit."""
    return build_tool()


async def call(tool: BaseTool, **arguments: object) -> ToolMessage:
    """Invoke the tool the way the graph's ToolNode does, with a tool call, and return its message."""
    tool_call = {"type": "tool_call", "id": "call-1", "name": TOOL_NAME, "args": arguments}
    message = await tool.ainvoke(tool_call)
    assert isinstance(message, ToolMessage)
    return message


def evidence_of(message: ToolMessage) -> list[Evidence]:
    """Return the Evidence artifact attached to a tool message."""
    artifact = message.artifact
    assert isinstance(artifact, list)
    return artifact


def markers(message: ToolMessage) -> list[str]:
    """Return the citation IDs the model sees, in order."""
    content = str(message.content)
    return MARKER_PATTERN.findall(content)


class TestDefinition:
    """What the model is told about the tool."""

    def test_name_schema_and_async(self, tool: BaseTool) -> None:
        """The tool is called search_10k, takes query, section, order_by and k, and runs asynchronously."""
        schema_fields = set(SearchTenKArguments.model_fields)
        assert tool.name == TOOL_NAME
        assert schema_fields == {"query", "section", "order_by", "k"}
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
        ],
    )
    def test_schema_rejects_bad_arguments(self, arguments: dict[str, object]) -> None:
        """Queries are 1-300 characters, k is 1-10, and order_by is relevance or position."""
        with pytest.raises(ValidationError):
            SearchTenKArguments.model_validate(arguments)


class TestRelevance:
    """Hybrid search results, formatted for the model, with Evidence for the renderer."""

    async def test_passages_carry_marker_path_and_page(self, tool: BaseTool) -> None:
        """Each passage opens with its marker, the short path and page, then the chunk text."""
        message = await call(tool, query="tax rates", section="item:1A", k=1)
        content = str(message.content)
        assert content.startswith(
            "[D4] Part I › Item 1A › Financial Risks (p. 12)\nChanges in tax rates can raise the Company’s tax expense."
        )

    async def test_cross_referenced_passages_follow_the_ranked_ones(self, tool: BaseTool) -> None:
        """The tax risk's references to Notes 7 and 3 come after it, with Item 8 shortened in the path."""
        message = await call(tool, query="tax rates", section="item:1A", k=1)
        content = str(message.content)
        assert markers(message) == ["D4", "D12", "D10"]
        assert "[D12] Part II › Item 8 › Note 7 – Provision (p. 42)" in content

    async def test_evidence_matches_the_passages_shown(self, tool: BaseTool) -> None:
        """One Evidence per passage, with the stable D ID and the source line the renderer will print."""
        message = await call(tool, query="tax rates", section="item:1A", k=1)
        evidence = evidence_of(message)
        assert [item.id for item in evidence] == markers(message)
        assert evidence[0] == Evidence(
            id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12"
        )

    async def test_k_defaults_to_top_k(self) -> None:
        """Without k, the tool returns top_k ranked passages (plus any cross-references)."""
        capped_tool = build_tool()
        message = await call(capped_tool, query="services margin", section="item:7")
        assert markers(message) == ["D6", "D7"]


class TestPosition:
    """order_by=position returns the first k units of a section, in document order."""

    async def test_item_1a_returns_only_risk_factors_with_all_parts(self, tool: BaseTool) -> None:
        """'Top N risk factors' skips the intro and keeps both parts of a split risk factor."""
        message = await call(tool, query="risk factors", section="item:1A", order_by="position", k=2)
        content = str(message.content)
        assert markers(message) == ["D3", "D4", "D5"]
        assert "[D5] Part I › Item 1A › Financial Risks (pp. 13–14)" in content

    async def test_page_ranges_appear_in_evidence(self, tool: BaseTool) -> None:
        """A chunk spanning pages cites them as a range."""
        message = await call(tool, query="risk factors", section="item:1A", order_by="position", k=2)
        evidence = {item.id: item for item in evidence_of(message)}
        assert evidence["D5"].source == "Form 10-K FY2025 › Part I › Item 1A › Financial Risks, pp. 13–14"

    async def test_other_sections_return_units_of_every_kind(self, tool: BaseTool) -> None:
        """Outside Item 1A, position order includes every unit; Item 8 continues into its notes."""
        message = await call(tool, query="statements", section="item:8", order_by="position", k=2)
        assert markers(message) == ["D8", "D9"]

    async def test_position_needs_a_section(self, tool: BaseTool) -> None:
        """Without a section there is no document order to follow, so the model is told to add one."""
        message = await call(tool, query="risk factors", order_by="position")
        assert str(message.content).startswith(MISSING_SECTION)
        assert evidence_of(message) == []


class TestErrors:
    """Problems come back to the model as messages it can act on, never as exceptions."""

    async def test_unknown_section_lists_the_valid_ones(self, tool: BaseTool) -> None:
        """An invalid section ID returns the IDs the model can use."""
        message = await call(tool, query="tax", section="item:99")
        content = str(message.content)
        assert content.startswith(UNKNOWN_SECTION)
        assert "item:1A" in content
        assert "note:7" in content
        assert evidence_of(message) == []

    async def test_not_found_in_a_section_suggests_dropping_the_filter(self, tool: BaseTool) -> None:
        """A miss inside a section tells the model to retry without the section filter."""
        message = await call(tool, query="tax rates", section="item:1")
        assert str(message.content) == f"{NO_RELEVANT_CONTENT} in item:1: retry without the section filter"
        assert evidence_of(message) == []

    async def test_not_found_anywhere(self, tool: BaseTool) -> None:
        """A miss across the whole filing says the filing doesn't cover it."""
        message = await call(tool, query="weather forecast")
        assert str(message.content).startswith(NO_RELEVANT_CONTENT)
        assert evidence_of(message) == []


class TestOutputLimit:
    """Output is capped at tool_output_max_chars without breaking citations."""

    async def test_drops_whole_passages_and_their_evidence(self) -> None:
        """Under a small cap, the output stays within it and Evidence covers exactly the passages shown."""
        small_tool = build_tool(tool_output_max_chars=SMALL_OUTPUT_LIMIT)
        message = await call(small_tool, query="tax rates", section="item:1A", k=1)
        evidence = evidence_of(message)
        assert len(str(message.content)) <= SMALL_OUTPUT_LIMIT
        assert markers(message)
        assert [item.id for item in evidence] == markers(message)
