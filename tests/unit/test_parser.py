"""Unit tests for the 10-K parser stages (LLD section 6, stages 1-7) on the synthetic fixture."""

import re

import pytest
from bs4 import BeautifulSoup

from filing_support import MINI_FILING_PATH, PAGE_FOOTER_PATTERN, markdown_table_rows, read_filing
from research_agent.ingestion.parser import (
    Block,
    assign_pages,
    assign_sections,
    clean,
    convert_tables,
    linearize,
    parse_filing,
    resolve_cross_refs,
    split_risk_factors,
)
from research_agent.ingestion.tables import TableCell

PART_I = "Part I"
PART_II = "Part II"
PART_II_HEADING = "PART II"
PART_II_SECTION_ID = "part:II"
PART_II_INTRO = "Part II covers the Company’s market information"
COVER_SECTION_ID = "cover"
COVER_PATH = ["Cover"]

ITEM_1_HEADING = "Item 1. Business"
ITEM_1A_HEADING = "Item 1A. Risk Factors"
ITEM_6_HEADING = "Item 6. [Reserved]"
ITEM_7_HEADING = "Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations"
ITEM_8_HEADING = "Item 8. Financial Statements and Supplementary Data"
ITEM_9_HEADING = "Item 9. Changes in and Disagreements with Accountants on Accounting and Financial Disclosure"
NOTE_1_HEADING = "Note 1 – Summary of Significant Accounting Policies"
NOTE_2_HEADING = "Note 2 – Revenue"
AUDITOR_REPORT_HEADING = "Report of Independent Registered Public Accounting Firm"
FAKE_NOTE_HEADING = "Note 5 – Not a Note Outside Item 8"

MACROECONOMIC_CATEGORY = "Macroeconomic and Industry Risks"
FINANCIAL_CATEGORY = "Financial Risks"
RISK_FACTOR_1_TITLE = (
    "The Company’s operations and performance depend significantly on global and regional economic conditions "
    "and adverse economic conditions can materially adversely affect the Company’s business."
)
RISK_FACTOR_2_TITLE = "The Company depends on the performance of carriers and other resellers."
RISK_FACTOR_3_TITLE = "The Company’s net sales and gross margins are subject to volatility and downward pressure."

TWELVE_WORD_BOLD_HEADING = "Products and Services Gross Margin Percentage by Fiscal Year and Reportable Segment"
FOURTEEN_WORD_BOLD_SENTENCE = (
    "The following discussion compares gross margin for fiscal 2025 with the prior fiscal year."
)

ITEM_1A_INTRO = "This section should be read in conjunction with Part II, Item 7"
EMPTY_ITALIC_SPAN_PARAGRAPH = "Adverse macroeconomic conditions, including inflation"
ONE_ITALIC_WORD_PARAGRAPH = "Uncertainty about economic conditions can also reduce iPhone demand"
RISK_FACTOR_2_PARAGRAPH = "The Company distributes its products through cellular network carriers"
GROSS_MARGIN_XREF_PARAGRAPH = "Gross margin pressure is discussed in Part I, Item 1A"
CONTINUATION_PARAGRAPH = "As discussed earlier in Item 7"
NOTE_1_PARAGRAPH = "The consolidated financial statements are described in this Note 1"
PLAIN_TEXT_ITEM_MENTION = "Item 7. Management’s Discussion and Analysis is mentioned here only as plain text."

TRAP_MARKERS = ["HIDDEN_XBRL_HEADER_FACT", "HIDDEN_DIV_TEXT", "HIDDEN_SPAN_TEXT", "SCRIPT_TEXT", "STYLE_TEXT"]
FIXTURE_TABLE_COUNT = 6
LAST_FOOTER_PAGE = 6


@pytest.fixture(scope="module")
def mini_html() -> str:
    """Return the synthetic filing's HTML."""
    return read_filing(MINI_FILING_PATH)


@pytest.fixture(scope="module")
def cleaned_document(mini_html: str) -> BeautifulSoup:
    """Return the fixture after stage 1."""
    return clean(mini_html)


@pytest.fixture(scope="module")
def linearized_blocks(cleaned_document: BeautifulSoup) -> list[Block]:
    """Return the fixture after stages 1-2."""
    return linearize(cleaned_document)


@pytest.fixture(scope="module")
def paged_blocks(linearized_blocks: list[Block]) -> list[Block]:
    """Return the fixture after stages 1-3."""
    return assign_pages(linearized_blocks, PAGE_FOOTER_PATTERN)


@pytest.fixture(scope="module")
def sectioned_blocks(paged_blocks: list[Block]) -> list[Block]:
    """Return the fixture after stages 1-4."""
    return assign_sections(paged_blocks)


@pytest.fixture(scope="module")
def risk_blocks(sectioned_blocks: list[Block]) -> list[Block]:
    """Return the fixture after stages 1-5."""
    return split_risk_factors(sectioned_blocks)


@pytest.fixture(scope="module")
def parsed_blocks(mini_html: str) -> list[Block]:
    """Return the fixture after the whole parser."""
    return parse_filing(mini_html, PAGE_FOOTER_PATTERN)


def find_block(blocks: list[Block], fragment: str, section_id: str | None = None) -> Block:
    """Return the single block whose text contains the fragment, optionally within one section."""
    matches = [
        block for block in blocks if fragment in block.text and (section_id is None or block.section_id == section_id)
    ]
    assert len(matches) == 1, f"expected one block containing {fragment!r}, found {len(matches)}"
    return matches[0]


def find_heading(blocks: list[Block], heading_text: str) -> Block:
    """Return the single heading block with exactly this text."""
    matches = [block for block in blocks if block.kind == "heading" and block.text == heading_text]
    assert len(matches) == 1, f"expected one heading {heading_text!r}, found {len(matches)}"
    return matches[0]


def find_table_with_cell(blocks: list[Block], cell_text: str) -> Block:
    """Return the single unconverted table block that has a cell with exactly this text."""
    matches = [
        block
        for block in blocks
        if block.kind == "table" and any(cell.text == cell_text for row in block.rows for cell in row)
    ]
    assert len(matches) == 1, f"expected one table with cell {cell_text!r}, found {len(matches)}"
    return matches[0]


def first_position(texts: list[str], fragment: str) -> int:
    """Return the index of the first text containing the fragment."""
    positions = [index for index, text in enumerate(texts) if fragment in text]
    assert positions, f"no text contains {fragment!r}"
    return positions[0]


def text_block(text: str, section_id: str | None = None) -> Block:
    """Build a plain text block for stage tests that don't need the fixture."""
    return Block(kind="text", text=text, section_id=section_id)


class TestClean:
    """Stage 1: remove inline-XBRL headers, hidden elements, scripts and styles; normalize spaces."""

    def test_removes_inline_xbrl_header(self, cleaned_document: BeautifulSoup) -> None:
        """The ix:header element and its hidden facts are gone."""
        assert cleaned_document.find("ix:header") is None
        document_text = cleaned_document.get_text()
        assert "HIDDEN_XBRL_HEADER_FACT" not in document_text

    def test_removes_hidden_elements(self, cleaned_document: BeautifulSoup) -> None:
        """Elements styled display:none are removed, both block-level and inline."""
        document_text = cleaned_document.get_text()
        assert "HIDDEN_DIV_TEXT" not in document_text
        assert "HIDDEN_SPAN_TEXT" not in document_text

    def test_removes_scripts_and_styles(self, cleaned_document: BeautifulSoup) -> None:
        """Script and style contents never reach the text."""
        document_text = cleaned_document.get_text()
        assert "SCRIPT_TEXT" not in document_text
        assert "STYLE_TEXT" not in document_text


class TestLinearize:
    """Stage 2: one block per top-level div, p or table, with bold and italic flags."""

    def test_normalizes_non_breaking_spaces(self, linearized_blocks: list[Block]) -> None:
        """Text extraction turns non-breaking spaces into plain spaces, in text blocks and table cells alike."""
        cell_texts = [cell.text for block in linearized_blocks for row in block.rows for cell in row]
        block_texts = [block.text for block in linearized_blocks]
        assert all("\xa0" not in text for text in [*block_texts, *cell_texts])

    def test_emits_paragraph_elements_as_blocks(self, linearized_blocks: list[Block]) -> None:
        """A top-level p is a block like a div."""
        block = find_block(linearized_blocks, "Securities registered pursuant to Section 12(g)")
        assert block.kind == "text"

    def test_emits_tables_inside_wrapper_divs_as_table_blocks(self, linearized_blocks: list[Block]) -> None:
        """Each table, though wrapped in a div, is one table block carrying its rows."""
        table_blocks = [block for block in linearized_blocks if block.kind == "table"]
        assert len(table_blocks) == FIXTURE_TABLE_COUNT
        assert all(block.rows for block in table_blocks)

    def test_sees_through_inline_xbrl_wrappers(self, linearized_blocks: list[Block]) -> None:
        """Divs inside ix:nonNumeric and ix:continuation are separate blocks, in document order."""
        texts = [block.text for block in linearized_blocks]
        wrapped_fragments = [
            GROSS_MARGIN_XREF_PARAGRAPH,
            "Products and Services gross margin for 2025",
            CONTINUATION_PARAGRAPH,
        ]
        positions = [first_position(texts, fragment) for fragment in wrapped_fragments]
        distinct_positions = set(positions)
        assert positions == sorted(positions)
        assert len(distinct_positions) == len(wrapped_fragments)

    def test_skips_empty_blocks(self, linearized_blocks: list[Block]) -> None:
        """Blocks with no visible text (spacer divs, hr) are not emitted."""
        text_blocks = [block for block in linearized_blocks if block.kind == "text"]
        assert all(block.text.strip() for block in text_blocks)

    def test_joins_text_split_across_spans_and_xbrl_tags(self, linearized_blocks: list[Block]) -> None:
        """Text split across spans and ix tags reads naturally, with whitespace collapsed."""
        find_block(linearized_blocks, "For the fiscal year ended September 27, 2025")
        item_heading = find_block(linearized_blocks, "Item 1A.")
        assert item_heading.text == ITEM_1A_HEADING

    def test_bold_requires_all_text_to_be_bold(self, linearized_blocks: list[Block]) -> None:
        """A block is bold only when every character is; one regular-weight checkbox makes it not bold."""
        form_title = find_block(linearized_blocks, "FORM 10-K")
        annual_report_line = find_block(linearized_blocks, "ANNUAL REPORT PURSUANT TO SECTION 13")
        assert form_title.bold
        assert not annual_report_line.bold

    def test_italic_requires_all_text_to_be_italic(self, linearized_blocks: list[Block]) -> None:
        """An empty italic span or a single italic word does not make a paragraph italic."""
        risk_title = find_block(linearized_blocks, RISK_FACTOR_1_TITLE)
        empty_italic_span = find_block(linearized_blocks, EMPTY_ITALIC_SPAN_PARAGRAPH)
        one_italic_word = find_block(linearized_blocks, ONE_ITALIC_WORD_PARAGRAPH)
        non_bold_italic = find_block(linearized_blocks, RISK_FACTOR_3_TITLE)
        assert risk_title.italic and risk_title.bold
        assert not empty_italic_span.italic
        assert not one_italic_word.italic
        assert non_bold_italic.italic and not non_bold_italic.bold


class TestAssignPages:
    """Stage 3: a footer closes its page, then is dropped."""

    def test_footer_assigns_its_page_to_preceding_blocks_and_is_dropped(self) -> None:
        """Every block since the previous footer gets that footer's page number."""
        blocks = [
            text_block("first"),
            text_block("second"),
            text_block("Apple Inc. | 2025 Form 10-K | 1"),
            text_block("third"),
            text_block("Apple Inc. | 2025 Form 10-K | 2"),
        ]
        paged = assign_pages(blocks, PAGE_FOOTER_PATTERN)
        assert [block.text for block in paged] == ["first", "second", "third"]
        assert [block.page for block in paged] == [1, 1, 2]

    def test_blocks_after_last_footer_get_the_next_page(self) -> None:
        """Trailing blocks with no footer after them are on the page after the last footer."""
        blocks = [text_block("body"), text_block("Apple Inc. | 2025 Form 10-K | 7"), text_block("signatures")]
        paged = assign_pages(blocks, PAGE_FOOTER_PATTERN)
        assert [block.page for block in paged] == [7, 8]

    def test_footer_must_match_the_whole_block(self) -> None:
        """A sentence that merely contains footer-like text is content, not a footer."""
        sentence = "See Apple Inc. | 2025 Form 10-K | 7 for details."
        blocks = [text_block(sentence), text_block("Apple Inc. | 2025 Form 10-K | 7")]
        paged = assign_pages(blocks, PAGE_FOOTER_PATTERN)
        assert [block.text for block in paged] == [sentence]

    @pytest.mark.parametrize(
        ("fragment", "expected_page"),
        [
            ("FORM 10-K", 1),
            (ITEM_1A_HEADING, 2),
            (ONE_ITALIC_WORD_PARAGRAPH, 3),
            (ITEM_7_HEADING, 4),
            (ITEM_8_HEADING, 5),
            (NOTE_2_HEADING, 6),
            ("SIGNATURES", LAST_FOOTER_PAGE + 1),
        ],
    )
    def test_fixture_pages(self, paged_blocks: list[Block], fragment: str, expected_page: int) -> None:
        """Fixture blocks land on the pages their footers close; page 2's footer is written with nbsp."""
        block = find_block(paged_blocks, fragment)
        assert block.page == expected_page

    def test_no_footer_survives(self, paged_blocks: list[Block]) -> None:
        """No block matches the footer pattern after stage 3."""
        footer_pattern = re.compile(PAGE_FOOTER_PATTERN)
        assert not any(footer_pattern.match(block.text) for block in paged_blocks)


class TestAssignSections:
    """Stage 4: Part, Item, Note and subsection headings give every block a section_id and section_path."""

    def test_blocks_before_part_one_belong_to_the_cover(self, sectioned_blocks: list[Block]) -> None:
        """Front matter gets the cover section."""
        block = find_block(sectioned_blocks, "Shares outstanding were reported")
        assert block.section_id == COVER_SECTION_ID
        assert block.section_path[0] == COVER_PATH[0]

    def test_table_of_contents_entries_are_not_headings(self, sectioned_blocks: list[Block]) -> None:
        """Item names inside the contents table don't open sections; each Item heading appears once."""
        find_heading(sectioned_blocks, ITEM_1A_HEADING)
        contents_table = find_table_with_cell(sectioned_blocks, "Risk Factors")
        assert contents_table.section_id == COVER_SECTION_ID

    def test_item_blocks_get_part_item_and_subsection_path(self, sectioned_blocks: list[Block]) -> None:
        """A paragraph under a subsection carries Part › Item › subsection, with the Part title-cased."""
        block = find_block(sectioned_blocks, "The Company designs, manufactures and markets")
        assert block.section_id == "item:1"
        assert block.section_path == [PART_I, ITEM_1_HEADING, "Company Background"]

    def test_item_ids_keep_their_letter_suffix(self, sectioned_blocks: list[Block]) -> None:
        """Item 1A is item:1A, and a paragraph directly under it has a two-level path."""
        block = find_block(sectioned_blocks, ITEM_1A_INTRO)
        assert block.section_id == "item:1A"
        assert block.section_path == [PART_I, ITEM_1A_HEADING]

    def test_part_heading_opens_a_part_section(self, sectioned_blocks: list[Block]) -> None:
        """A Part heading keeps the filing's text and opens part:<numeral> with a title-cased path."""
        heading = find_heading(sectioned_blocks, PART_II_HEADING)
        assert heading.section_id == PART_II_SECTION_ID
        assert heading.section_path == [PART_II]

    def test_blocks_between_part_and_first_item_belong_to_the_part(self, sectioned_blocks: list[Block]) -> None:
        """Text after a Part heading and before its first Item sits in the Part section."""
        block = find_block(sectioned_blocks, PART_II_INTRO)
        assert block.section_id == PART_II_SECTION_ID
        assert block.section_path == [PART_II]

    def test_headings_are_kept_as_heading_blocks(self, sectioned_blocks: list[Block]) -> None:
        """A heading block carries the section it opens, so even an empty Item is recorded."""
        heading = find_heading(sectioned_blocks, ITEM_6_HEADING)
        assert heading.section_id == "item:6"
        assert heading.section_path == [PART_II, ITEM_6_HEADING]

    def test_new_subsection_replaces_the_previous_one(self, sectioned_blocks: list[Block]) -> None:
        """Subsections don't nest: 'Products' replaces 'Company Background'."""
        block = find_block(sectioned_blocks, "iPhone is the Company’s line of smartphones")
        assert block.section_path == [PART_I, ITEM_1_HEADING, "Products"]

    def test_notes_are_sections_inside_item_8(self, sectioned_blocks: list[Block]) -> None:
        """Note headings in Item 8 open note sections; a new note resets the subsection."""
        note_1_block = find_block(sectioned_blocks, NOTE_1_PARAGRAPH)
        note_2_block = find_block(sectioned_blocks, "The Company records revenue when control")
        assert note_1_block.section_id == "note:1"
        assert note_1_block.section_path == [PART_II, ITEM_8_HEADING, NOTE_1_HEADING, "Basis of Presentation"]
        assert note_2_block.section_id == "note:2"
        assert note_2_block.section_path == [PART_II, ITEM_8_HEADING, NOTE_2_HEADING]

    def test_auditor_report_after_the_notes_belongs_to_item_8(self, sectioned_blocks: list[Block]) -> None:
        """The auditor's report follows the last note but is part of Item 8, so it isn't cited as Note 3."""
        heading = find_heading(sectioned_blocks, AUDITOR_REPORT_HEADING)
        block = find_block(sectioned_blocks, "In our opinion, the consolidated financial statements present fairly")
        assert heading.section_id == "item:8"
        assert block.section_id == "item:8"
        assert block.section_path == [PART_II, ITEM_8_HEADING, AUDITOR_REPORT_HEADING]

    def test_note_heading_outside_item_8_is_only_a_subsection(self, sectioned_blocks: list[Block]) -> None:
        """'Note 5 – ...' under Item 9 is a subsection heading, not a note section."""
        heading = find_heading(sectioned_blocks, FAKE_NOTE_HEADING)
        assert heading.section_id == "item:9"
        assert heading.section_path == [PART_II, ITEM_9_HEADING, FAKE_NOTE_HEADING]
        assert not any(block.section_id == "note:5" for block in sectioned_blocks)

    def test_short_bold_block_is_a_subsection_heading(self, sectioned_blocks: list[Block]) -> None:
        """A bold block of 12 words is a subsection heading."""
        heading = find_heading(sectioned_blocks, TWELVE_WORD_BOLD_HEADING)
        assert heading.section_path == [PART_II, ITEM_7_HEADING, TWELVE_WORD_BOLD_HEADING]

    def test_long_bold_block_is_body_text(self, sectioned_blocks: list[Block]) -> None:
        """A bold block of more than 12 words stays body text in the current subsection."""
        block = find_block(sectioned_blocks, FOURTEEN_WORD_BOLD_SENTENCE)
        assert block.kind == "text"
        assert block.section_path == [PART_II, ITEM_7_HEADING, TWELVE_WORD_BOLD_HEADING]

    def test_non_bold_item_text_is_not_a_heading(self, sectioned_blocks: list[Block]) -> None:
        """A regular-weight paragraph starting with 'Item 7.' is body text of the current section."""
        block = find_block(sectioned_blocks, PLAIN_TEXT_ITEM_MENTION)
        assert block.kind == "text"
        assert block.section_id == "item:9"

    def test_every_block_has_a_section(self, sectioned_blocks: list[Block]) -> None:
        """No block is left without a section_id and section_path."""
        assert all(block.section_id and block.section_path for block in sectioned_blocks)


class TestSplitRiskFactors:
    """Stage 5: inside Item 1A, an italic block starts a risk factor that owns the paragraphs after it."""

    def test_italic_block_starts_a_risk_factor(self, risk_blocks: list[Block]) -> None:
        """The italic title block is body text that belongs to its own risk factor."""
        title = find_block(risk_blocks, RISK_FACTOR_1_TITLE)
        assert title.kind == "text"
        assert title.risk_factor == RISK_FACTOR_1_TITLE

    def test_following_paragraphs_belong_to_it_across_pages(self, risk_blocks: list[Block]) -> None:
        """Paragraphs after the title belong to it, including after a page break."""
        members = [block for block in risk_blocks if block.risk_factor == RISK_FACTOR_1_TITLE]
        member_pages = {block.page for block in members}
        assert len(members) == 4
        assert member_pages == {2, 3}

    def test_partially_italic_paragraphs_do_not_start_risk_factors(self, risk_blocks: list[Block]) -> None:
        """An empty italic span or one italic word leaves the paragraph in the current risk factor."""
        empty_italic_span = find_block(risk_blocks, EMPTY_ITALIC_SPAN_PARAGRAPH)
        one_italic_word = find_block(risk_blocks, ONE_ITALIC_WORD_PARAGRAPH)
        assert empty_italic_span.risk_factor == RISK_FACTOR_1_TITLE
        assert one_italic_word.risk_factor == RISK_FACTOR_1_TITLE

    def test_short_bold_italic_title_is_a_risk_factor_not_a_heading(self, risk_blocks: list[Block]) -> None:
        """An 11-word bold italic title starts a risk factor; the subsection-heading rule doesn't take it."""
        title = find_block(risk_blocks, RISK_FACTOR_2_TITLE)
        paragraph = find_block(risk_blocks, RISK_FACTOR_2_PARAGRAPH)
        assert title.kind == "text"
        assert title.risk_factor == RISK_FACTOR_2_TITLE
        assert paragraph.risk_factor == RISK_FACTOR_2_TITLE

    def test_italic_title_need_not_be_bold(self, risk_blocks: list[Block]) -> None:
        """A regular-weight italic block also starts a risk factor."""
        paragraph = find_block(risk_blocks, "Competitive pressures and component costs")
        assert paragraph.risk_factor == RISK_FACTOR_3_TITLE

    def test_category_headings_are_subsections_of_item_1a(self, risk_blocks: list[Block]) -> None:
        """Short bold non-italic blocks are category headings, belong to no risk factor, and appear in paths."""
        category = find_heading(risk_blocks, FINANCIAL_CATEGORY)
        first_risk_paragraph = find_block(risk_blocks, "The Company has international operations")
        third_risk_paragraph = find_block(risk_blocks, "Competitive pressures and component costs")
        assert category.risk_factor is None
        assert first_risk_paragraph.section_path == [PART_I, ITEM_1A_HEADING, MACROECONOMIC_CATEGORY]
        assert third_risk_paragraph.section_path == [PART_I, ITEM_1A_HEADING, FINANCIAL_CATEGORY]

    def test_fixture_has_exactly_three_risk_factors(self, risk_blocks: list[Block]) -> None:
        """Only whole-italic blocks inside Item 1A start risk factors."""
        titles = {block.risk_factor for block in risk_blocks if block.risk_factor is not None}
        assert titles == {RISK_FACTOR_1_TITLE, RISK_FACTOR_2_TITLE, RISK_FACTOR_3_TITLE}

    def test_intro_paragraph_belongs_to_no_risk_factor(self, risk_blocks: list[Block]) -> None:
        """Item 1A text before the first italic block is not part of a risk factor."""
        intro = find_block(risk_blocks, ITEM_1A_INTRO)
        assert intro.risk_factor is None

    def test_italic_outside_item_1a_is_not_a_risk_factor(self, risk_blocks: list[Block]) -> None:
        """The italic product name 'iPhone' in Item 1 starts nothing."""
        product_names = [block for block in risk_blocks if block.text == "iPhone"]
        assert len(product_names) == 1
        assert product_names[0].risk_factor is None

    def test_risk_factor_ends_at_the_next_item(self, risk_blocks: list[Block]) -> None:
        """Item 1B's body belongs to no risk factor."""
        block = find_block(risk_blocks, "None.", section_id="item:1B")
        assert block.risk_factor is None


class TestConvertTables:
    """Stage 6 in the parser: data tables become Markdown, layout tables become text."""

    @pytest.fixture
    def converted_blocks(self) -> list[Block]:
        """Run stage 6 alone on a data table, a layout table inside a risk factor, and a text block."""
        data_rows = [
            [TableCell(text=""), TableCell(text="2025")],
            [TableCell(text="Total net sales"), TableCell(text="$416,161")],
        ]
        layout_rows = [[TableCell(text="Large accelerated filer"), TableCell(text="☒")]]
        blocks = [
            Block(kind="table", rows=data_rows, page=4, section_id="item:7", section_path=[PART_II, ITEM_7_HEADING]),
            Block(kind="table", rows=layout_rows, page=3, section_id="item:1A", risk_factor=RISK_FACTOR_2_TITLE),
            text_block("Unchanged paragraph.", section_id="item:7"),
        ]
        return convert_tables(blocks)

    def test_data_table_block_gets_markdown_and_keeps_its_metadata(self, converted_blocks: list[Block]) -> None:
        """A data table stays a table block, its text becomes Markdown, and page and section are kept."""
        table = converted_blocks[0]
        rows = markdown_table_rows(table.text)
        assert table.kind == "table"
        assert rows == [["", "2025"], ["Total net sales", "$416,161"]]
        assert table.page == 4
        assert table.section_path == [PART_II, ITEM_7_HEADING]

    def test_layout_table_block_becomes_text_and_keeps_its_risk_factor(self, converted_blocks: list[Block]) -> None:
        """A layout table becomes a text block with flattened text, still inside its risk factor."""
        flattened = converted_blocks[1]
        assert flattened.kind == "text"
        assert flattened.text == "Large accelerated filer ☒"
        assert flattened.risk_factor == RISK_FACTOR_2_TITLE
        assert flattened.page == 3

    def test_text_blocks_pass_through_in_order(self, converted_blocks: list[Block]) -> None:
        """Non-table blocks are untouched and block order is preserved."""
        assert len(converted_blocks) == 3
        assert converted_blocks[2] == text_block("Unchanged paragraph.", section_id="item:7")

    def test_data_table_becomes_markdown_in_its_subsection(self, parsed_blocks: list[Block]) -> None:
        """The gross margin table renders as Markdown and stays in Item 7 › Gross Margin."""
        table = find_block(parsed_blocks, "$112,887")
        rows = markdown_table_rows(table.text)
        assert table.kind == "table"
        assert table.section_path == [PART_II, ITEM_7_HEADING, "Gross Margin"]
        assert ["Products", "$112,887", "$109,633"] in rows

    def test_layout_table_becomes_text(self, parsed_blocks: list[Block]) -> None:
        """The cover's checkbox table becomes a text block in the cover section."""
        block = find_block(parsed_blocks, "Large accelerated filer")
        assert block.kind == "text"
        assert "|" not in block.text
        assert block.section_id == COVER_SECTION_ID


class TestResolveCrossRefs:
    """Stage 7: references in text blocks map to existing section IDs, excluding the block's own section."""

    def test_maps_references_dedupes_and_drops_self_and_unknown(self) -> None:
        """Part/Item and Note references resolve in order of first mention; self and unknown targets drop."""
        referring_text = "See Part II, Item 8 and Note 5. As noted in Item 7, see Note 99 and Note 5 again."
        blocks = [
            text_block(referring_text, section_id="item:7"),
            text_block("Financial statements.", section_id="item:8"),
            text_block("Property, plant and equipment.", section_id="note:5"),
        ]
        resolved = resolve_cross_refs(blocks)
        assert resolved[0].cross_refs == ["item:8", "note:5"]

    def test_tables_get_no_cross_references(self) -> None:
        """Only text blocks are scanned."""
        blocks = [
            Block(kind="table", text="| See Note 5 | 1 |\n|---|---|\n| a | 2 |", section_id="item:7"),
            text_block("Property, plant and equipment.", section_id="note:5"),
        ]
        resolved = resolve_cross_refs(blocks)
        assert resolved[0].cross_refs == []

    @pytest.mark.parametrize(
        ("fragment", "expected_references"),
        [
            (ITEM_1A_INTRO, ["item:7", "item:8"]),
            (RISK_FACTOR_2_PARAGRAPH, ["note:2"]),
            (GROSS_MARGIN_XREF_PARAGRAPH, ["item:1A", "note:2"]),
            (CONTINUATION_PARAGRAPH, []),
            (NOTE_1_PARAGRAPH, ["note:3"]),
            (PLAIN_TEXT_ITEM_MENTION, ["item:7"]),
        ],
    )
    def test_fixture_references(
        self, parsed_blocks: list[Block], fragment: str, expected_references: list[str]
    ) -> None:
        """Fixture paragraphs resolve to the expected sections."""
        block = find_block(parsed_blocks, fragment)
        assert block.cross_refs == expected_references


class TestParseFiling:
    """The whole parser on the fixture."""

    def test_no_hidden_script_or_style_text_reaches_a_block(self, parsed_blocks: list[Block]) -> None:
        """Nothing removed in stage 1 reappears."""
        for marker in TRAP_MARKERS:
            assert not any(marker in block.text for block in parsed_blocks), marker

    def test_every_block_has_a_page_and_a_section(self, parsed_blocks: list[Block]) -> None:
        """Pages and sections are complete after parsing."""
        assert all(block.page is not None for block in parsed_blocks)
        assert all(block.section_id for block in parsed_blocks)

    def test_pages_never_decrease(self, parsed_blocks: list[Block]) -> None:
        """Blocks stay in document order."""
        pages = [block.page for block in parsed_blocks if block.page is not None]
        assert pages == sorted(pages)
