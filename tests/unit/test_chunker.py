"""Unit tests for chunking (LLD section 6, stage 8), with a word counter standing in for the tokenizer."""

import itertools

import pytest

from filing_support import (
    MINI_FILING_PATH,
    PAGE_FOOTER_PATTERN,
    REAL_FILING_PATH,
    markdown_table_rows,
    read_filing,
)
from ingestion_fakes import count_words
from research_agent.ingestion.chunker import build_chunks, embedding_text
from research_agent.ingestion.parser import Block, parse_filing
from research_agent.models import Chunk

LARGE_TOKEN_LIMIT = 400
SMALL_TOKEN_LIMIT = 60
SMALL_OVERLAP = 10
FIXTURE_CHUNK_COUNT = 23
REAL_RISK_FACTOR_COUNT = 27

PART_I = "Part I"
PART_II = "Part II"
ITEM_1A_HEADING = "Item 1A. Risk Factors"
ITEM_6_HEADING = "Item 6. [Reserved]"
ITEM_7_HEADING = "Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations"
ITEM_8_HEADING = "Item 8. Financial Statements and Supplementary Data"
STATEMENT_HEADING = "CONSOLIDATED STATEMENTS OF OPERATIONS"
PERCENTAGE_HEADING = "Products and Services Gross Margin Percentage by Fiscal Year and Reportable Segment"
MACROECONOMIC_CATEGORY = "Macroeconomic and Industry Risks"

RISK_FACTOR_1_TITLE = (
    "The Company’s operations and performance depend significantly on global and regional economic conditions "
    "and adverse economic conditions can materially adversely affect the Company’s business."
)
RISK_FACTOR_2_TITLE = "The Company depends on the performance of carriers and other resellers."
RISK_FACTOR_3_TITLE = "The Company’s net sales and gross margins are subject to volatility and downward pressure."
GROSS_MARGIN_INTRO = "Products and Services gross margin for 2025 and 2024 were as follows (dollars in millions):"
PATH_SEPARATOR = " › "
PARAGRAPH_SEPARATOR = "\n\n"

LONG_RISK_PATH = [PART_I, ITEM_1A_HEADING, MACROECONOMIC_CATEGORY]
LONG_RISK_TITLE = "A long risk factor title used to test splitting."
PARAGRAPH_WORDS = 30
PARAGRAPH_PAGES = [2, 2, 3, 3, 4, 4]


@pytest.fixture(scope="module")
def fixture_chunks() -> list[Chunk]:
    """Return the synthetic filing parsed and chunked with a generous limit."""
    html = read_filing(MINI_FILING_PATH)
    blocks = parse_filing(html, PAGE_FOOTER_PATTERN)
    return build_chunks(blocks, count_words, LARGE_TOKEN_LIMIT)


def chunks_in_section(chunks: list[Chunk], section_id: str) -> list[Chunk]:
    """Return a section's chunks in document order."""
    return [chunk for chunk in chunks if chunk.section_id == section_id]


def find_chunk(chunks: list[Chunk], fragment: str) -> Chunk:
    """Return the single chunk whose text contains the fragment."""
    matches = [chunk for chunk in chunks if fragment in chunk.text]
    assert len(matches) == 1, f"expected one chunk containing {fragment!r}, found {len(matches)}"
    return matches[0]


def numbered_words(prefix: str, count: int) -> str:
    """Return a paragraph of distinct, recognizable words."""
    return " ".join(f"{prefix}{number}" for number in range(1, count + 1))


def long_risk_factor_blocks() -> list[Block]:
    """Build an Item 1A risk factor whose six 30-word paragraphs span pages 2 to 4."""
    title = Block(
        kind="text",
        text=LONG_RISK_TITLE,
        italic=True,
        page=2,
        section_id="item:1A",
        section_path=LONG_RISK_PATH,
        risk_factor=LONG_RISK_TITLE,
    )
    paragraphs = [
        Block(
            kind="text",
            text=numbered_words(f"p{index}w", PARAGRAPH_WORDS),
            page=page,
            section_id="item:1A",
            section_path=LONG_RISK_PATH,
            risk_factor=LONG_RISK_TITLE,
        )
        for index, page in enumerate(PARAGRAPH_PAGES, start=1)
    ]
    return [title, *paragraphs]


def markdown_table(row_count: int) -> str:
    """Build a Markdown table with a header and numbered rows."""
    header = "| Region | 2025 | 2024 |\n|---|---|---|"
    rows = [f"| Region {number} | ${number},000 | ${number},500 |" for number in range(1, row_count + 1)]
    return "\n".join([header, *rows])


class TestEmbeddingText:
    """What gets embedded: the section path on one line, then the chunk text."""

    def test_puts_the_section_path_on_the_first_line(self, fixture_chunks: list[Chunk]) -> None:
        """The path is joined with › and separated from the text by a newline."""
        chunk = find_chunk(fixture_chunks, RISK_FACTOR_2_TITLE)
        expected_path_line = PATH_SEPARATOR.join(chunk.section_path)
        assert embedding_text(chunk) == f"{expected_path_line}\n{chunk.text}"


class TestUnits:
    """Blocks are grouped into units: one risk factor, one subsection's paragraphs, or one table."""

    def test_fixture_chunk_count_and_global_sequence(self, fixture_chunks: list[Chunk]) -> None:
        """Every unit fits the generous limit, so there is one chunk per unit, numbered 1..n in document order."""
        sequence_numbers = [chunk.seq for chunk in fixture_chunks]
        pages = [chunk.page_start for chunk in fixture_chunks]
        assert len(fixture_chunks) == FIXTURE_CHUNK_COUNT
        assert sequence_numbers == list(range(1, FIXTURE_CHUNK_COUNT + 1))
        assert pages == sorted(pages)

    def test_headings_are_not_chunked(self, fixture_chunks: list[Chunk]) -> None:
        """Heading text lives in the section path, so an Item with only a heading has no chunks."""
        assert chunks_in_section(fixture_chunks, "item:6") == []
        assert not any(chunk.text == ITEM_6_HEADING for chunk in fixture_chunks)

    def test_risk_factor_is_one_unit_with_its_title_and_paragraphs(self, fixture_chunks: list[Chunk]) -> None:
        """A risk factor's title and paragraphs form one chunk, joined by blank lines, across a page break."""
        chunk = find_chunk(fixture_chunks, RISK_FACTOR_1_TITLE)
        paragraphs = chunk.text.split(PARAGRAPH_SEPARATOR)
        assert chunk.kind == "risk_factor"
        assert chunk.unit == RISK_FACTOR_1_TITLE
        assert paragraphs[0] == RISK_FACTOR_1_TITLE
        assert len(paragraphs) == 4
        assert (chunk.page_start, chunk.page_end) == (2, 3)
        assert chunk.section_path == [PART_I, ITEM_1A_HEADING, MACROECONOMIC_CATEGORY]

    def test_item_1a_units_are_numbered_in_order(self, fixture_chunks: list[Chunk]) -> None:
        """The intro paragraph is unit 1, then each risk factor in document order."""
        section_chunks = chunks_in_section(fixture_chunks, "item:1A")
        units = [(chunk.position, chunk.kind, chunk.unit) for chunk in section_chunks]
        assert units == [
            (1, "text", ITEM_1A_HEADING),
            (2, "risk_factor", RISK_FACTOR_1_TITLE),
            (3, "risk_factor", RISK_FACTOR_2_TITLE),
            (4, "risk_factor", RISK_FACTOR_3_TITLE),
        ]

    def test_subsection_paragraphs_form_one_unit_named_after_the_subsection(self, fixture_chunks: list[Chunk]) -> None:
        """Consecutive paragraphs of one subsection are one text chunk whose unit is the subsection heading."""
        chunk = find_chunk(fixture_chunks, "Gross margin pressure is discussed")
        assert chunk.kind == "text"
        assert chunk.unit == "Gross Margin"
        assert chunk.position == 1
        assert chunk.text.endswith(GROSS_MARGIN_INTRO)

    def test_a_table_ends_the_text_unit_before_it(self, fixture_chunks: list[Chunk]) -> None:
        """Item 7 reads text, table, table, text: four units in that order."""
        section_chunks = chunks_in_section(fixture_chunks, "item:7")
        units = [(chunk.position, chunk.kind, chunk.unit) for chunk in section_chunks]
        assert units == [
            (1, "text", "Gross Margin"),
            (2, "table", "Gross Margin"),
            (3, "table", PERCENTAGE_HEADING),
            (4, "text", PERCENTAGE_HEADING),
        ]

    def test_unit_defaults_to_the_last_path_element(self, fixture_chunks: list[Chunk]) -> None:
        """Text directly under a Part or Item is named after that Part or Item."""
        part_chunks = chunks_in_section(fixture_chunks, "part:II")
        item_16_chunks = chunks_in_section(fixture_chunks, "item:16")
        assert [chunk.unit for chunk in part_chunks] == [PART_II]
        assert [chunk.unit for chunk in item_16_chunks] == ["Item 16. Form 10-K Summary", "SIGNATURES"]

    def test_chunks_carry_their_blocks_cross_references(self, fixture_chunks: list[Chunk]) -> None:
        """Cross-references of a unit's blocks are combined in order of first mention."""
        intro = find_chunk(fixture_chunks, "This section should be read in conjunction")
        gross_margin = find_chunk(fixture_chunks, "Gross margin pressure is discussed")
        assert intro.cross_refs == ["item:7", "item:8"]
        assert gross_margin.cross_refs == ["item:1A", "note:2"]

    def test_layout_table_text_stays_in_its_text_unit(self, fixture_chunks: list[Chunk]) -> None:
        """A layout table flattened to text joins the surrounding paragraphs of the cover."""
        chunk = find_chunk(fixture_chunks, "Large accelerated filer")
        assert chunk.kind == "text"
        assert "Shares outstanding were reported" in chunk.text


class TestTableChunks:
    """A data table is its own chunk, with the preceding paragraph of its subsection in front."""

    def test_table_carries_its_intro_paragraph(self, fixture_chunks: list[Chunk]) -> None:
        """The paragraph before the gross margin table opens the table chunk, then the Markdown follows."""
        chunk = find_chunk(fixture_chunks, "$112,887")
        intro, markdown = chunk.text.split(PARAGRAPH_SEPARATOR, maxsplit=1)
        rows = markdown_table_rows(markdown)
        assert chunk.kind == "table"
        assert intro == GROSS_MARGIN_INTRO
        assert ["Products", "$112,887", "$109,633"] in rows

    def test_intro_comes_only_from_the_same_subsection(self, fixture_chunks: list[Chunk]) -> None:
        """The percentage table has no paragraph before it in its own subsection, so it starts with the table."""
        chunk = find_chunk(fixture_chunks, "46.9%")
        assert chunk.text.startswith("|")

    def test_statement_table_uses_the_units_line_as_intro(self, fixture_chunks: list[Chunk]) -> None:
        """'(In millions)' precedes the statement table in its subsection, so it travels with the table."""
        chunk = find_chunk(fixture_chunks, "$(321)")
        assert chunk.text.startswith(f"(In millions){PARAGRAPH_SEPARATOR}|")
        assert chunk.section_path == [PART_II, ITEM_8_HEADING, STATEMENT_HEADING]

    def test_oversized_table_is_split_by_rows_with_the_header_repeated(self) -> None:
        """Each part fits the limit, starts with the intro and header, and together the parts keep every row."""
        path = [PART_II, ITEM_7_HEADING, "Segment Operating Performance"]
        intro = Block(
            kind="text", text="Net sales by region were as follows:", page=4, section_id="item:7", section_path=path
        )
        table = Block(kind="table", text=markdown_table(40), page=4, section_id="item:7", section_path=path)
        chunks = build_chunks([intro, table], count_words, SMALL_TOKEN_LIMIT, SMALL_OVERLAP)
        table_chunks = [chunk for chunk in chunks if chunk.kind == "table"]
        body_rows: list[list[str]] = []
        for chunk in table_chunks:
            chunk_intro, markdown = chunk.text.split(PARAGRAPH_SEPARATOR, maxsplit=1)
            rows = markdown_table_rows(markdown)
            assert chunk_intro == intro.text
            assert rows[0] == ["Region", "2025", "2024"]
            assert count_words(embedding_text(chunk)) <= SMALL_TOKEN_LIMIT
            body_rows.extend(rows[1:])
        expected_rows = markdown_table_rows(table.text)[1:]
        assert len(table_chunks) > 1
        assert body_rows == expected_rows
        assert {chunk.position for chunk in table_chunks} == {2}


class TestSplitting:
    """A unit over the limit is split; the limit counts the section-path line too."""

    @pytest.fixture
    def split_chunks(self) -> list[Chunk]:
        """Chunk one long risk factor with a small limit."""
        blocks = long_risk_factor_blocks()
        return build_chunks(blocks, count_words, SMALL_TOKEN_LIMIT, SMALL_OVERLAP)

    def test_every_chunk_fits_the_limit_including_the_path_line(self, split_chunks: list[Chunk]) -> None:
        """No embedded text exceeds the limit, and the unit needed more than one chunk."""
        assert len(split_chunks) > 1
        assert all(count_words(embedding_text(chunk)) <= SMALL_TOKEN_LIMIT for chunk in split_chunks)

    def test_split_chunks_share_the_unit_and_position(self, split_chunks: list[Chunk]) -> None:
        """All parts belong to one risk factor and one position, with consecutive sequence numbers."""
        sequence_numbers = [chunk.seq for chunk in split_chunks]
        assert {chunk.unit for chunk in split_chunks} == {LONG_RISK_TITLE}
        assert {chunk.position for chunk in split_chunks} == {1}
        assert {chunk.kind for chunk in split_chunks} == {"risk_factor"}
        assert sequence_numbers == list(range(1, len(split_chunks) + 1))

    def test_no_text_is_lost(self, split_chunks: list[Chunk]) -> None:
        """Every word of every paragraph appears in some chunk."""
        chunk_words = {word for chunk in split_chunks for word in chunk.text.split()}
        source_words = {word for block in long_risk_factor_blocks() for word in block.text.split()}
        assert source_words <= chunk_words

    def test_page_ranges_follow_the_text_each_chunk_holds(self, split_chunks: list[Chunk]) -> None:
        """The unit runs from page 2 to 4, and a chunk holding only page-3 text is on page 3 alone."""
        page_three_chunk = find_chunk(split_chunks, "p3w15")
        assert split_chunks[0].page_start == 2
        assert split_chunks[-1].page_end == 4
        assert all(chunk.page_start <= chunk.page_end for chunk in split_chunks)
        assert (page_three_chunk.page_start, page_three_chunk.page_end) == (3, 3)

    def test_long_paragraph_splits_with_overlap(self) -> None:
        """A single paragraph over the limit splits on words, and consecutive parts overlap."""
        path = [PART_II, ITEM_7_HEADING, "Overview"]
        block = Block(kind="text", text=numbered_words("w", 150), page=5, section_id="item:7", section_path=path)
        chunks = build_chunks([block], count_words, SMALL_TOKEN_LIMIT, SMALL_OVERLAP)
        assert len(chunks) > 2
        for previous, following in itertools.pairwise(chunks):
            previous_words = set(previous.text.split())
            following_words = set(following.text.split())
            assert previous_words & following_words

    def test_path_line_counts_toward_the_limit(self) -> None:
        """Text that fits alone but not with its path line is split."""
        path = [PART_II, ITEM_7_HEADING, "Overview"]
        path_line_words = count_words(PATH_SEPARATOR.join(path))
        text_words = SMALL_TOKEN_LIMIT - path_line_words + 5
        block = Block(kind="text", text=numbered_words("x", text_words), page=5, section_id="item:7", section_path=path)
        chunks = build_chunks([block], count_words, SMALL_TOKEN_LIMIT, SMALL_OVERLAP)
        assert text_words <= SMALL_TOKEN_LIMIT
        assert len(chunks) == 2


@pytest.fixture(scope="module")
def real_chunks() -> list[Chunk]:
    """Return the real filing parsed and chunked, once per module."""
    html = read_filing(REAL_FILING_PATH)
    blocks = parse_filing(html, PAGE_FOOTER_PATTERN)
    return build_chunks(blocks, count_words, LARGE_TOKEN_LIMIT)


@pytest.mark.skipif(not REAL_FILING_PATH.exists(), reason=f"{REAL_FILING_PATH} not downloaded")
class TestRealFilingChunks:
    """Chunk structure on the real filing (word counts stand in for tokens here)."""

    def test_every_risk_factor_becomes_a_unit(self, real_chunks: list[Chunk]) -> None:
        """Item 1A yields 27 risk-factor units, numbered after the intro."""
        risk_chunks = [chunk for chunk in real_chunks if chunk.kind == "risk_factor"]
        units = list(dict.fromkeys(chunk.unit for chunk in risk_chunks))
        positions = sorted({chunk.position for chunk in risk_chunks})
        assert len(units) == REAL_RISK_FACTOR_COUNT
        assert positions == list(range(2, REAL_RISK_FACTOR_COUNT + 2))

    def test_sequence_is_global_and_every_chunk_fits(self, real_chunks: list[Chunk]) -> None:
        """Sequence numbers run 1..n and no embedded text exceeds the limit."""
        sequence_numbers = [chunk.seq for chunk in real_chunks]
        assert sequence_numbers == list(range(1, len(real_chunks) + 1))
        assert all(count_words(embedding_text(chunk)) <= LARGE_TOKEN_LIMIT for chunk in real_chunks)
