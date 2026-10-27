"""The search_10k tool (LLD section 7): cited passages from the filing, never a generated answer.

The model sees passages headed by citation markers; the Evidence artifact, which the model never sees,
gives the renderer each marker's source line.
"""

import asyncio
import re
from typing import Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from research_agent.models import Chunk, Evidence
from research_agent.retrieval.search import NotFound, Searcher
from research_agent.retrieval.store import ChunkStore

TOOL_NAME = "search_10k"
NO_RELEVANT_CONTENT = "NO_RELEVANT_CONTENT"
UNKNOWN_SECTION = "ERROR unknown_section"
MISSING_SECTION = "ERROR missing_section"

MAX_QUERY_CHARS = 300
MIN_K = 1
MAX_K = 10
OrderBy = Literal["relevance", "position"]
RELEVANCE_ORDER: OrderBy = "relevance"
POSITION_ORDER: OrderBy = "position"
RISK_FACTORS_SECTION = "item:1A"
RISK_FACTOR_KIND = "risk_factor"
DOC_EVIDENCE_KIND: Literal["doc"] = "doc"
DOC_ID_PREFIX = "D"

PATH_SEPARATOR = " › "
ITEM_HEADING_PATTERN = re.compile(r"^(Item \d+[A-C]?)\.")
PASSAGE_SEPARATOR = "\n\n"
HEADER_SEPARATOR = "\n"
SECTION_LIST_SEPARATOR = ", "
TRUNCATION_MARK = "…"


class SearchTenKArguments(BaseModel):
    """Arguments of search_10k."""

    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS, description="What to look for in the 10-K.")
    section: str | None = Field(
        default=None,
        description="Optional section ID to search within, e.g. item:1A, item:7 or note:7; item:8 includes its notes.",
    )
    order_by: OrderBy = Field(
        default=RELEVANCE_ORDER,
        description="relevance: best matches. position: the first k units of the section in document order "
        "(in item:1A, the first k risk factors); needs a section.",
    )
    k: int | None = Field(default=None, ge=MIN_K, le=MAX_K, description="How many passages or units to return.")


def display_path(section_path: list[str]) -> str:
    """Render a section path for citations, shortening Item headings to 'Item 7'."""
    shortened = []
    for element in section_path:
        item_match = ITEM_HEADING_PATTERN.match(element)
        shortened.append(item_match.group(1) if item_match else element)
    return PATH_SEPARATOR.join(shortened)


def page_label(page_start: int, page_end: int) -> str:
    """Render a page or page range: 'p. 12' or 'pp. 13–14'."""
    if page_start == page_end:
        return f"p. {page_start}"
    return f"pp. {page_start}–{page_end}"


def citation_id(chunk: Chunk) -> str:
    """Return the chunk's stable citation ID."""
    return f"{DOC_ID_PREFIX}{chunk.seq}"


def passage(chunk: Chunk) -> str:
    """Format one passage for the model: marker, path and page, then the text."""
    path = display_path(chunk.section_path)
    pages = page_label(chunk.page_start, chunk.page_end)
    return f"[{citation_id(chunk)}] {path} ({pages}){HEADER_SEPARATOR}{chunk.text}"


def evidence(chunk: Chunk, filing_label: str) -> Evidence:
    """Build the Evidence the renderer prints for a chunk."""
    path = display_path(chunk.section_path)
    pages = page_label(chunk.page_start, chunk.page_end)
    return Evidence(id=citation_id(chunk), kind=DOC_EVIDENCE_KIND, source=f"{filing_label} › {path}, {pages}")


def render(chunks: list[Chunk], filing_label: str, max_chars: int) -> tuple[str, list[Evidence]]:
    """Format passages within max_chars, dropping whole trailing passages so every marker has its Evidence."""
    shown_passages: list[str] = []
    shown_evidence: list[Evidence] = []
    used_chars = 0
    for chunk in chunks:
        formatted = passage(chunk)
        separator_chars = len(PASSAGE_SEPARATOR) if shown_passages else 0
        if used_chars + separator_chars + len(formatted) > max_chars:
            break
        shown_passages.append(formatted)
        shown_evidence.append(evidence(chunk, filing_label))
        used_chars += separator_chars + len(formatted)
    if not shown_passages and chunks:
        first_chunk = chunks[0]
        first_passage = passage(first_chunk)
        truncated = first_passage[: max_chars - len(TRUNCATION_MARK)] + TRUNCATION_MARK
        return truncated, [evidence(first_chunk, filing_label)]
    content = PASSAGE_SEPARATOR.join(shown_passages)
    return content, shown_evidence


def not_found_message(section: str | None) -> str:
    """Tell the model nothing relevant was found, and what to do next."""
    if section is not None:
        return f"{NO_RELEVANT_CONTENT} in {section}: retry without the section filter"
    return f"{NO_RELEVANT_CONTENT}: the 10-K has no passage relevant to this query; list it under Data gaps"


def make_search_10k(
    store: ChunkStore,
    searcher: Searcher,
    top_k: int,
    tool_output_max_chars: int,
    filing_label: str,
) -> BaseTool:
    """Build the search_10k tool over the given store and searcher."""

    @tool(TOOL_NAME, args_schema=SearchTenKArguments, response_format="content_and_artifact")
    async def search_10k(
        query: str,
        section: str | None = None,
        order_by: OrderBy = RELEVANCE_ORDER,
        k: int | None = None,
    ) -> tuple[str, list[Evidence]]:
        """Search Apple's fiscal 2025 Form 10-K and return cited passages, not an answer.

        Use it for risk factors, strategy, management's explanations and reported figures. Each passage starts
        with a citation marker such as [D137]; cite facts with exactly those markers. relevance returns the best
        matches for the query, plus passages from sections they cross-reference. position returns the first k
        units of a section in document order; in item:1A these are the risk factors in the order the filing
        lists them. Tables come as Markdown, with figures in the filing's units (mostly millions of dollars).
        """
        count = k or top_k
        if order_by == POSITION_ORDER and section is None:
            return f"{MISSING_SECTION}: order_by=position needs a section, such as item:1A", []
        if section is not None and not store.has_section(section):
            valid_sections = SECTION_LIST_SEPARATOR.join(store.section_ids())
            return f"{UNKNOWN_SECTION}: {section}. Valid sections: {valid_sections}", []
        if order_by == POSITION_ORDER and section is not None:
            kind = RISK_FACTOR_KIND if section == RISK_FACTORS_SECTION else None
            units = store.first_units(section, count, kind)
            chunks = [chunk for unit in units for chunk in unit]
        else:
            result = await asyncio.to_thread(searcher.search, query, section, count)
            if isinstance(result, NotFound):
                return not_found_message(result.section), []
            chunks = result
        if not chunks:
            return not_found_message(section), []
        return render(chunks, filing_label, tool_output_max_chars)

    return search_10k
