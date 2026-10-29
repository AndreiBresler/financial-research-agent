"""Parser checks on the real FY2025 Apple 10-K (LLD section 6, "Parser checks"); skipped if the filing is absent."""

import pytest

from filing_support import PAGE_FOOTER_PATTERN, REAL_FILING_PATH, markdown_table_rows, read_filing
from research_agent.ingestion.parser import Block, parse_filing

pytestmark = pytest.mark.skipif(not REAL_FILING_PATH.exists(), reason=f"{REAL_FILING_PATH} not downloaded")

ITEM_ID_PREFIX = "item:"
PART_ID_PREFIX = "part:"
NOTE_ID_PREFIX = "note:"
AUDITOR_REPORT = "Report of Independent Registered Public Accounting Firm"
ITEM_1A_SECTION_ID = "item:1A"
ITEM_7_SECTION_ID = "item:7"
ITEM_8_SECTION_ID = "item:8"
FIRST_PAGE = 1
LAST_PAGE = 58

# Page of each Item heading as printed in the filing's table of contents.
# fmt: off
TABLE_OF_CONTENTS_PAGES = {
    "1": 1, "1A": 5, "1B": 17, "1C": 17, "2": 17, "3": 18, "4": 18,
    "5": 19, "6": 20, "7": 21, "7A": 27, "8": 28,
    "9": 52, "9A": 52, "9B": 53, "9C": 53,
    "10": 53, "11": 53, "12": 53, "13": 53, "14": 53,
    "15": 54, "16": 57,
}
# fmt: on
PART_HEADINGS = ["Part I", "Part II", "Part III", "Part IV"]
NOTE_COUNT = 13

RISK_FACTOR_COUNT = 27
RISK_CATEGORIES = [
    "Macroeconomic and Industry Risks",
    "Business Risks",
    "Legal and Regulatory Compliance Risks",
    "Financial Risks",
    "General Risks",
]
FIRST_RISK_FACTOR_PREFIX = "The Company’s operations and performance depend significantly on global and regional"
LAST_RISK_FACTOR = "The price of the Company’s stock is subject to volatility."

XBRL_HEADER_MARKER = "fasb.org/us-gaap/2025#"


@pytest.fixture(scope="module")
def real_blocks() -> list[Block]:
    """Return the real filing parsed once for the whole module."""
    html = read_filing(REAL_FILING_PATH)
    return parse_filing(html, PAGE_FOOTER_PATTERN)


def heading_blocks(blocks: list[Block]) -> list[Block]:
    """Return the heading blocks."""
    return [block for block in blocks if block.kind == "heading"]


def item_heading_pages(blocks: list[Block]) -> dict[str, list[int | None]]:
    """Map each Item number to the pages of the headings that open it."""
    pages: dict[str, list[int | None]] = {}
    for block in heading_blocks(blocks):
        section_id = block.section_id or ""
        # An Item heading's path is [Part, Item]; subsection headings inside the Item have a third element.
        opens_item = section_id.startswith(ITEM_ID_PREFIX) and block.section_path[1:] == [block.text]
        if opens_item:
            item_number = section_id.removeprefix(ITEM_ID_PREFIX)
            item_pages = pages.setdefault(item_number, [])
            item_pages.append(block.page)
    return pages


def table_rows_in_section(blocks: list[Block], section_id: str) -> list[list[str]]:
    """Return every Markdown row of every data table in a section."""
    rows: list[list[str]] = []
    for block in blocks:
        if block.kind == "table" and block.section_id == section_id:
            table_rows = markdown_table_rows(block.text)
            rows.extend(table_rows)
    return rows


def test_each_standard_item_heading_found_once_on_its_contents_page(real_blocks: list[Block]) -> None:
    """Every standard 10-K Item is found exactly once, on the page the table of contents gives."""
    pages = item_heading_pages(real_blocks)
    expected_pages = {item_number: [page] for item_number, page in TABLE_OF_CONTENTS_PAGES.items()}
    assert pages == expected_pages


def test_each_part_heading_found_once(real_blocks: list[Block]) -> None:
    """Parts I-IV each open exactly once, with title-cased path names."""
    part_paths = [
        block.section_path
        for block in heading_blocks(real_blocks)
        if (block.section_id or "").startswith(PART_ID_PREFIX)
    ]
    assert part_paths == [[part] for part in PART_HEADINGS]


def test_every_block_has_a_page_in_range_and_in_order(real_blocks: list[Block]) -> None:
    """Every block has a page between 1 and 58, and pages never decrease."""
    pages = [block.page for block in real_blocks]
    assert all(page is not None and FIRST_PAGE <= page <= LAST_PAGE for page in pages)
    known_pages = [page for page in pages if page is not None]
    assert known_pages == sorted(known_pages)


def test_every_block_has_a_section(real_blocks: list[Block]) -> None:
    """No block is left without a section."""
    assert all(block.section_id and block.section_path for block in real_blocks)


def test_auditor_reports_after_the_notes_belong_to_item_8(real_blocks: list[Block]) -> None:
    """Both auditor's reports follow Note 13 but are part of Item 8, so they aren't cited as Note 13."""
    reports = [block for block in real_blocks if block.kind == "heading" and block.text.startswith(AUDITOR_REPORT)]
    assert len(reports) == 2
    assert all(block.section_id == "item:8" for block in reports)


def test_notes_one_to_thirteen_found_once_inside_item_8(real_blocks: list[Block]) -> None:
    """Each note opens once, and every note section sits under Item 8."""
    note_ids = [
        block.section_id
        for block in heading_blocks(real_blocks)
        if (block.section_id or "").startswith(NOTE_ID_PREFIX) and len(block.section_path) == 3
    ]
    expected_note_ids = [f"{NOTE_ID_PREFIX}{number}" for number in range(1, NOTE_COUNT + 1)]
    assert note_ids == expected_note_ids
    note_blocks = [block for block in real_blocks if block.section_id in expected_note_ids]
    assert all(block.section_path[1].startswith("Item 8.") for block in note_blocks)


def test_risk_factors_and_categories(real_blocks: list[Block]) -> None:
    """Item 1A splits into 27 risk factors under 5 categories, in document order."""
    risk_titles = list(dict.fromkeys(block.risk_factor for block in real_blocks if block.risk_factor is not None))
    categories = [
        block.text
        for block in heading_blocks(real_blocks)
        if block.section_id == ITEM_1A_SECTION_ID and len(block.section_path) == 3
    ]
    assert len(risk_titles) == RISK_FACTOR_COUNT
    assert risk_titles[0].startswith(FIRST_RISK_FACTOR_PREFIX)
    assert risk_titles[-1] == LAST_RISK_FACTOR
    assert categories == RISK_CATEGORIES


def test_risk_factors_stay_inside_item_1a(real_blocks: list[Block]) -> None:
    """No block outside Item 1A belongs to a risk factor."""
    risk_factor_sections = {block.section_id for block in real_blocks if block.risk_factor is not None}
    assert risk_factor_sections == {ITEM_1A_SECTION_ID}


def test_gross_margin_percentage_table(real_blocks: list[Block]) -> None:
    """Item 7's gross margin percentage table renders with merged % cells (required query 2: 46.9%)."""
    rows = table_rows_in_section(real_blocks, ITEM_7_SECTION_ID)
    assert ["Total gross margin percentage", "46.9%", "46.2%", "44.1%"] in rows


def test_research_and_development_rows(real_blocks: list[Block]) -> None:
    """R&D renders with its change columns in Item 7 and as plain figures in Item 8 (required query 1)."""
    item_7_rows = table_rows_in_section(real_blocks, ITEM_7_SECTION_ID)
    item_8_rows = table_rows_in_section(real_blocks, ITEM_8_SECTION_ID)
    assert ["Research and development", "$34,550", "10%", "$31,370", "5%", "$29,915"] in item_7_rows
    assert ["Research and development", "34,550", "31,370", "29,915"] in item_8_rows


def test_item_1a_intro_cross_references(real_blocks: list[Block]) -> None:
    """The Item 1A intro's references to Part II, Items 7 and 8 resolve."""
    intro_blocks = [block for block in real_blocks if "This section should be read in conjunction" in block.text]
    assert len(intro_blocks) == 1
    assert intro_blocks[0].cross_refs == [ITEM_7_SECTION_ID, ITEM_8_SECTION_ID]


def test_no_xbrl_header_or_non_breaking_space_in_text(real_blocks: list[Block]) -> None:
    """The hidden ix:header facts are gone and spaces are normalized."""
    assert not any(XBRL_HEADER_MARKER in block.text for block in real_blocks)
    assert not any("\xa0" in block.text for block in real_blocks)
