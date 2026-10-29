"""10-K parser (LLD section 6, stages 1-7): HTML to page-, section- and risk-factor-aware blocks.

Each stage is a pure function over the previous stage's output; parse_filing runs them in order.
"""

import re
import warnings
from collections.abc import Callable, Iterator
from typing import Literal

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from bs4.element import PageElement, Tag
from pydantic import BaseModel, Field

from research_agent.ingestion.tables import TableCell, extract_rows, render_table
from research_agent.ingestion.text import element_text, is_text_node

# Bump when parser output changes; the manifest records it and a mismatch forces a re-ingest.
PARSER_VERSION = "2"

HTML_PARSER = "lxml"
INLINE_XBRL_HEADER_TAG = "ix:header"
INLINE_XBRL_PREFIX = "ix:"
REMOVED_TAGS = ["script", "style"]
STYLE_ATTRIBUTE = "style"
HIDDEN_STYLE_PATTERN = re.compile(r"display\s*:\s*none", re.IGNORECASE)
BLOCK_TAGS = {"div", "p", "table"}
TABLE_TAG = "table"

TEXT_KIND: Literal["text"] = "text"
TABLE_KIND: Literal["table"] = "table"
HEADING_KIND: Literal["heading"] = "heading"

FONT_WEIGHT_PATTERN = re.compile(r"font-weight\s*:\s*([^;]+)", re.IGNORECASE)
FONT_STYLE_PATTERN = re.compile(r"font-style\s*:\s*([^;]+)", re.IGNORECASE)
BOLD_KEYWORDS = {"bold", "bolder"}
MIN_BOLD_WEIGHT = 600
ITALIC_KEYWORDS = {"italic", "oblique"}

PAGE_NUMBER_GROUP = 1

COVER_SECTION_ID = "cover"
COVER_TITLE = "Cover"
PART_HEADING_PATTERN = re.compile(r"^PART\s+(IV|I{1,3})$", re.IGNORECASE)
ITEM_HEADING_PATTERN = re.compile(r"^Item\s+(\d+[A-C]?)\.(?:\s|$)", re.IGNORECASE)
NOTE_HEADING_PATTERN = re.compile(r"^Note\s+(\d+)\s*[–—-]", re.IGNORECASE)
# The auditor's reports follow the last note but belong to Item 8 itself.
AUDITOR_REPORT_PATTERN = re.compile(r"^Report of Independent Registered Public Accounting Firm", re.IGNORECASE)
PART_TITLE_PREFIX = "Part "
PART_ID_PREFIX = "part:"
ITEM_ID_PREFIX = "item:"
NOTE_ID_PREFIX = "note:"
NOTES_ITEM_NUMBER = "8"
RISK_FACTORS_SECTION_ID = "item:1A"
MAX_SUBSECTION_HEADING_WORDS = 12

CROSS_REFERENCE_PATTERN = re.compile(r"\bNote (?P<note>\d+)\b|\bItem (?P<item>\d+[A-C]?)\b(?!\.\d)")
NOTE_GROUP = "note"
ITEM_GROUP = "item"


class Block(BaseModel):
    """One top-level element of the filing, annotated stage by stage."""

    kind: Literal["text", "table", "heading"]
    text: str = ""
    rows: list[list[TableCell]] = Field(default_factory=list)
    bold: bool = False
    italic: bool = False
    page: int | None = None
    section_id: str | None = None
    section_path: list[str] = Field(default_factory=list)
    risk_factor: str | None = None
    cross_refs: list[str] = Field(default_factory=list)


# Stage 1: clean


def is_hidden(element: Tag) -> bool:
    """Tell whether an element is styled display:none."""
    style = element.get(STYLE_ATTRIBUTE)
    return isinstance(style, str) and HIDDEN_STYLE_PATTERN.search(style) is not None


def remove_elements(elements: list[Tag]) -> None:
    """Remove elements from their tree, skipping any already removed with an ancestor."""
    for element in elements:
        if not element.decomposed:
            element.decompose()


def clean(html: str) -> BeautifulSoup:
    """Parse the filing and strip the inline-XBRL header, hidden elements, scripts and styles.

    Non-breaking spaces need no pass here: text extraction normalizes them with all other whitespace.
    """
    with warnings.catch_warnings():
        # EDGAR inline-XBRL files carry an XML declaration but parse correctly as HTML.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        document = BeautifulSoup(html, HTML_PARSER)
    removable = [
        *document.find_all(INLINE_XBRL_HEADER_TAG),
        *document.find_all(is_hidden),
        *document.find_all(REMOVED_TAGS),
    ]
    remove_elements([element for element in removable if isinstance(element, Tag)])
    return document


# Stage 2: linearize


def top_level_elements(container: Tag) -> Iterator[Tag]:
    """Yield the block-level children of a container in order, seeing through inline-XBRL wrappers."""
    for child in container.children:
        if not isinstance(child, Tag):
            continue
        if child.name.startswith(INLINE_XBRL_PREFIX):
            yield from top_level_elements(child)
        elif child.name in BLOCK_TAGS:
            yield child


def declared_value(node: PageElement, block_element: Tag, pattern: re.Pattern[str]) -> str | None:
    """Return the innermost value of a CSS property declared on a text node's ancestors within the block."""
    for ancestor in node.parents:
        style = ancestor.get(STYLE_ATTRIBUTE)
        if isinstance(style, str):
            match = pattern.search(style)
            if match is not None:
                declared = match.group(1)
                return declared.strip().lower()
        if ancestor is block_element:
            break
    return None


def is_bold_weight(weight: str | None) -> bool:
    """Tell whether a font-weight value is bold."""
    if weight is None:
        return False
    return weight in BOLD_KEYWORDS or (weight.isdigit() and int(weight) >= MIN_BOLD_WEIGHT)


def is_italic_style(style: str | None) -> bool:
    """Tell whether a font-style value is italic."""
    return style in ITALIC_KEYWORDS


def all_text_styled(block_element: Tag, pattern: re.Pattern[str], is_styled: Callable[[str | None], bool]) -> bool:
    """Tell whether every non-whitespace text node in the block carries the style."""
    visible_nodes = [node for node in block_element.descendants if is_text_node(node) and str(node).strip()]
    if not visible_nodes:
        return False
    for node in visible_nodes:
        value = declared_value(node, block_element, pattern)
        if not is_styled(value):
            return False
    return True


def element_block(element: Tag) -> Block | None:
    """Build the block for one top-level element, or None when it shows no text."""
    table = element if element.name == TABLE_TAG else element.find(TABLE_TAG)
    if isinstance(table, Tag):
        rows = extract_rows(table)
        has_text = any(cell.text for row in rows for cell in row)
        return Block(kind=TABLE_KIND, rows=rows) if has_text else None
    text = element_text(element)
    if not text:
        return None
    bold = all_text_styled(element, FONT_WEIGHT_PATTERN, is_bold_weight)
    italic = all_text_styled(element, FONT_STYLE_PATTERN, is_italic_style)
    return Block(kind=TEXT_KIND, text=text, bold=bold, italic=italic)


def linearize(document: BeautifulSoup) -> list[Block]:
    """Emit one block per top-level div, p or table of the body, in document order."""
    body = document.body
    if body is None:
        raise ValueError("filing has no <body>")
    blocks: list[Block] = []
    for element in top_level_elements(body):
        block = element_block(element)
        if block is not None:
            blocks.append(block)
    return blocks


# Stage 3: pages


def assign_pages(blocks: list[Block], page_footer_pattern: str) -> list[Block]:
    """Give each block the page its next footer closes, and drop the footers."""
    footer_pattern = re.compile(page_footer_pattern)
    paged: list[Block] = []
    pending: list[Block] = []
    last_page = 0
    for block in blocks:
        footer_match = footer_pattern.fullmatch(block.text) if block.kind == TEXT_KIND else None
        if footer_match is None:
            pending.append(block)
            continue
        page_number_text = footer_match.group(PAGE_NUMBER_GROUP)
        last_page = int(page_number_text)
        paged.extend(pending_block.model_copy(update={"page": last_page}) for pending_block in pending)
        pending = []
    trailing_page = last_page + 1
    paged.extend(pending_block.model_copy(update={"page": trailing_page}) for pending_block in pending)
    return paged


# Stage 4: sections


class SectionCursor:
    """Tracks the open Part, Item, Note and subsection while walking the blocks in order."""

    def __init__(self) -> None:
        """Start in the cover section, before any Part heading."""
        self.section_id = COVER_SECTION_ID
        self.section_base_path = [COVER_TITLE]
        self.part_title: str | None = None
        self.item_number: str | None = None
        self.item_path: list[str] = []
        self.subsection: str | None = None

    def path(self) -> list[str]:
        """Return the path of the current position, including the open subsection."""
        subsection_path = [self.subsection] if self.subsection is not None else []
        return [*self.section_base_path, *subsection_path]

    def part_path(self) -> list[str]:
        """Return the path of the open Part, empty before PART I."""
        return [self.part_title] if self.part_title is not None else []

    def open_heading(self, block: Block) -> bool:
        """Open the section or subsection a heading block starts; return False for non-headings."""
        if block.kind != TEXT_KIND or not block.bold:
            return False
        part_match = PART_HEADING_PATTERN.fullmatch(block.text)
        if part_match is not None:
            part_numeral = part_match.group(1)
            self.open_part(part_numeral.upper())
            return True
        item_match = ITEM_HEADING_PATTERN.match(block.text)
        if item_match is not None:
            item_number = item_match.group(1)
            self.open_item(item_number.upper(), block.text)
            return True
        note_match = NOTE_HEADING_PATTERN.match(block.text)
        if note_match is not None and self.item_number == NOTES_ITEM_NUMBER:
            self.open_note(note_match.group(1), block.text)
            return True
        if self.item_number == NOTES_ITEM_NUMBER and AUDITOR_REPORT_PATTERN.match(block.text):
            self.close_note()
            self.subsection = block.text
            return True
        if self.is_subsection_heading(block):
            self.subsection = block.text
            return True
        return False

    def is_subsection_heading(self, block: Block) -> bool:
        """Tell whether a bold block is a subsection heading; italic blocks in Item 1A are risk factors instead."""
        if self.section_id == RISK_FACTORS_SECTION_ID and block.italic:
            return False
        words = block.text.split()
        return len(words) <= MAX_SUBSECTION_HEADING_WORDS

    def open_part(self, numeral: str) -> None:
        """Open a Part; it closes the Item, Note and subsection."""
        self.part_title = f"{PART_TITLE_PREFIX}{numeral}"
        self.section_id = f"{PART_ID_PREFIX}{numeral}"
        self.section_base_path = [self.part_title]
        self.item_number = None
        self.item_path = []
        self.subsection = None

    def open_item(self, number: str, heading: str) -> None:
        """Open an Item within the current Part."""
        self.item_number = number
        self.item_path = [*self.part_path(), heading]
        self.section_id = f"{ITEM_ID_PREFIX}{number}"
        self.section_base_path = self.item_path
        self.subsection = None

    def open_note(self, number: str, heading: str) -> None:
        """Open a note to the financial statements within Item 8."""
        self.section_id = f"{NOTE_ID_PREFIX}{number}"
        self.section_base_path = [*self.item_path, heading]
        self.subsection = None

    def close_note(self) -> None:
        """Return from a note to Item 8 itself, which the auditor's reports after the notes belong to."""
        self.section_id = f"{ITEM_ID_PREFIX}{NOTES_ITEM_NUMBER}"
        self.section_base_path = self.item_path
        self.subsection = None


def assign_sections(blocks: list[Block]) -> list[Block]:
    """Give every block a section ID and path; headings become heading blocks carrying the section they open."""
    cursor = SectionCursor()
    sectioned: list[Block] = []
    for block in blocks:
        is_heading = cursor.open_heading(block)
        kind = HEADING_KIND if is_heading else block.kind
        current_path = cursor.path()
        update = {"kind": kind, "section_id": cursor.section_id, "section_path": current_path}
        sectioned.append(block.model_copy(update=update))
    return sectioned


# Stage 5: risk factors


def split_risk_factors(blocks: list[Block]) -> list[Block]:
    """Inside Item 1A, let each italic block start a risk factor that owns the blocks after it."""
    current_title: str | None = None
    result: list[Block] = []
    for block in blocks:
        in_risk_factors = block.section_id == RISK_FACTORS_SECTION_ID
        if not in_risk_factors or block.kind == HEADING_KIND:
            current_title = None
            result.append(block)
            continue
        if block.kind == TEXT_KIND and block.italic:
            current_title = block.text
        if current_title is None:
            result.append(block)
        else:
            result.append(block.model_copy(update={"risk_factor": current_title}))
    return result


# Stage 6: tables


def convert_tables(blocks: list[Block]) -> list[Block]:
    """Render table blocks: data tables as Markdown, layout tables as text blocks."""
    converted: list[Block] = []
    for block in blocks:
        if block.kind != TABLE_KIND:
            converted.append(block)
            continue
        rendering = render_table(block.rows)
        converted.append(block.model_copy(update={"kind": rendering.kind, "text": rendering.text}))
    return converted


# Stage 7: cross-references


def referenced_sections(text: str) -> list[str]:
    """Return the section IDs a text mentions, in order of first mention, without duplicates."""
    references: list[str] = []
    for match in CROSS_REFERENCE_PATTERN.finditer(text):
        note_number = match.group(NOTE_GROUP)
        item_number = match.group(ITEM_GROUP)
        reference = f"{NOTE_ID_PREFIX}{note_number}" if note_number else f"{ITEM_ID_PREFIX}{item_number}"
        if reference not in references:
            references.append(reference)
    return references


def resolve_cross_refs(blocks: list[Block]) -> list[Block]:
    """Attach to each text block the existing sections it refers to, other than its own."""
    existing_sections = {block.section_id for block in blocks if block.section_id is not None}
    resolved: list[Block] = []
    for block in blocks:
        if block.kind != TEXT_KIND:
            resolved.append(block)
            continue
        mentioned = referenced_sections(block.text)
        cross_refs = [
            section_id for section_id in mentioned if section_id in existing_sections and section_id != block.section_id
        ]
        resolved.append(block.model_copy(update={"cross_refs": cross_refs}))
    return resolved


def parse_filing(html: str, page_footer_pattern: str) -> list[Block]:
    """Run parser stages 1-7 over a filing's HTML."""
    document = clean(html)
    linear_blocks = linearize(document)
    paged_blocks = assign_pages(linear_blocks, page_footer_pattern)
    sectioned_blocks = assign_sections(paged_blocks)
    risk_blocks = split_risk_factors(sectioned_blocks)
    table_blocks = convert_tables(risk_blocks)
    return resolve_cross_refs(table_blocks)
