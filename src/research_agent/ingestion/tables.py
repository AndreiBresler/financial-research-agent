"""Table cleanup and rendering (LLD section 6, stage 6): EDGAR tables become Markdown, layout tables plain text."""

import re
from dataclasses import dataclass
from typing import Literal

from bs4 import Tag
from pydantic import BaseModel

from research_agent.ingestion.text import element_text

ROW_TAG = "tr"
CELL_TAGS = ["td", "th"]
COLSPAN_ATTRIBUTE = "colspan"
DEFAULT_COLSPAN = 1

DATA_TABLE_KIND: Literal["table"] = "table"
LAYOUT_TABLE_KIND: Literal["text"] = "text"
MIN_DATA_COLUMNS = 2

PREFIX_MARKERS = {"$"}
SUFFIX_MARKERS = {"%", ")", "%)"}
VALUE_PATTERN = re.compile(r"^\$?\(?\$?-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?\)?%?$")
BARE_YEAR_PATTERN = re.compile(r"^(?:19|20)\d{2}$")

MARKDOWN_CELL_SEPARATOR = " | "
MARKDOWN_PIPE = "|"
MARKDOWN_ESCAPED_PIPE = "\\|"
MARKDOWN_HEADER_RULE_CELL = "---"
FLATTENED_CELL_SEPARATOR = " "
LINE_SEPARATOR = "\n"
HEADER_PART_SEPARATOR = " "


class TableCell(BaseModel):
    """One HTML table cell: its normalized text and the number of grid columns it spans."""

    text: str
    colspan: int = DEFAULT_COLSPAN


class TableRendering(BaseModel):
    """A converted table: Markdown for a data table, plain text for a layout table."""

    kind: Literal["table", "text"]
    text: str


@dataclass(frozen=True)
class PlacedCell:
    """A non-empty cell's text and the inclusive range of grid slots it covers."""

    text: str
    start: int
    end: int


def read_colspan(cell: Tag) -> int:
    """Return a cell's colspan, falling back to 1 when it is missing or malformed."""
    raw_colspan = cell.get(COLSPAN_ATTRIBUTE)
    if isinstance(raw_colspan, str) and raw_colspan.isdigit():
        return max(int(raw_colspan), DEFAULT_COLSPAN)
    return DEFAULT_COLSPAN


def extract_rows(table: Tag) -> list[list[TableCell]]:
    """Read every row of an HTML table as cells with normalized text and colspan."""
    rows: list[list[TableCell]] = []
    for row in table.find_all(ROW_TAG):
        cells = [
            TableCell(text=element_text(cell), colspan=read_colspan(cell))
            for cell in row.find_all(CELL_TAGS, recursive=False)
        ]
        rows.append(cells)
    return rows


def place_row(row: list[TableCell]) -> list[PlacedCell]:
    """Lay a row's cells onto grid slots and keep the non-empty ones."""
    placed: list[PlacedCell] = []
    slot = 0
    for cell in row:
        end = slot + cell.colspan - 1
        if cell.text:
            placed.append(PlacedCell(text=cell.text, start=slot, end=end))
        slot = end + 1
    return placed


def merge_markers(cells: list[PlacedCell]) -> list[PlacedCell]:
    """Join '$' cells to the value after them and '%' or ')' cells to the value before them."""
    merged: list[PlacedCell] = []
    pending_prefix: PlacedCell | None = None
    for cell in cells:
        if cell.text in PREFIX_MARKERS:
            pending_prefix = cell if pending_prefix is None else join_cells(pending_prefix, cell)
        elif cell.text in SUFFIX_MARKERS and merged:
            merged[-1] = join_cells(merged[-1], cell)
        elif pending_prefix is not None:
            merged.append(join_cells(pending_prefix, cell))
            pending_prefix = None
        else:
            merged.append(cell)
    if pending_prefix is not None:
        merged.append(pending_prefix)
    return merged


def join_cells(left: PlacedCell, right: PlacedCell) -> PlacedCell:
    """Concatenate two adjacent cells into one covering both."""
    return PlacedCell(text=left.text + right.text, start=left.start, end=right.end)


def is_value(text: str) -> bool:
    """Tell whether a cell holds an amount, percentage or ratio; a bare year is a column label, not a value."""
    return VALUE_PATTERN.match(text) is not None and BARE_YEAR_PATTERN.match(text) is None


def row_has_value(row: list[PlacedCell]) -> bool:
    """Tell whether any cell in the row is a value."""
    return any(is_value(cell.text) for cell in row)


def count_header_rows(rows: list[list[PlacedCell]], label_start: int) -> int:
    """Count the leading rows without values, stopping at a row that holds only a row label."""
    header_count = 0
    for row in rows:
        is_label_only = len(row) == 1 and row[0].start == label_start
        if row_has_value(row) or is_label_only:
            break
        header_count += 1
    return header_count


def column_ranges(body_rows: list[list[PlacedCell]]) -> list[tuple[int, int]]:
    """Derive logical columns as merged slot ranges of the body cells.

    Rows with a single cell (row labels, footnotes) often span the whole width, so they don't define columns.
    """
    defining_rows = [row for row in body_rows if len(row) >= MIN_DATA_COLUMNS] or body_rows
    spans = sorted((cell.start, cell.end) for row in defining_rows for cell in row)
    ranges: list[tuple[int, int]] = []
    for start, end in spans:
        if ranges and start <= ranges[-1][1]:
            previous_start, previous_end = ranges[-1]
            ranges[-1] = (previous_start, max(previous_end, end))
        else:
            ranges.append((start, end))
    return ranges


def overlaps(cell: PlacedCell, column_range: tuple[int, int]) -> bool:
    """Tell whether a cell's slots overlap a column's slot range."""
    column_start, column_end = column_range
    return cell.start <= column_end and cell.end >= column_start


def column_for(cell: PlacedCell, ranges: list[tuple[int, int]]) -> int:
    """Return the index of the column a body cell belongs to: the one holding its first slot, else the nearest."""
    for index, (column_start, column_end) in enumerate(ranges):
        if column_start <= cell.start <= column_end:
            return index
    for index, column_range in enumerate(ranges):
        if overlaps(cell, column_range):
            return index
    later_columns = [index for index, (column_start, _) in enumerate(ranges) if column_start > cell.start]
    return later_columns[0] if later_columns else len(ranges) - 1


def header_texts(header_rows: list[list[PlacedCell]], ranges: list[tuple[int, int]]) -> list[str]:
    """Join header rows top to bottom per column; a spanning cell applies to every column it covers."""
    parts: list[list[str]] = [[] for _ in ranges]
    for row in header_rows:
        for cell in row:
            for index, column_range in enumerate(ranges):
                if overlaps(cell, column_range):
                    parts[index].append(cell.text)
    return [HEADER_PART_SEPARATOR.join(column_parts) for column_parts in parts]


def body_texts(row: list[PlacedCell], ranges: list[tuple[int, int]]) -> list[str]:
    """Place a body row's cells into the logical columns."""
    parts: list[list[str]] = [[] for _ in ranges]
    for cell in row:
        index = column_for(cell, ranges)
        parts[index].append(cell.text)
    return [FLATTENED_CELL_SEPARATOR.join(column_parts) for column_parts in parts]


def markdown_line(cells: list[str]) -> str:
    """Render one Markdown table row, escaping pipes inside cells."""
    escaped_cells = [cell.replace(MARKDOWN_PIPE, MARKDOWN_ESCAPED_PIPE) for cell in cells]
    joined_cells = MARKDOWN_CELL_SEPARATOR.join(escaped_cells)
    return f"{MARKDOWN_PIPE} {joined_cells} {MARKDOWN_PIPE}"


def to_markdown(header: list[str], body: list[list[str]]) -> str:
    """Render a header and body rows as a Markdown table."""
    header_rule_cells = [MARKDOWN_HEADER_RULE_CELL for _ in header]
    joined_rule = MARKDOWN_PIPE.join(header_rule_cells)
    header_rule = f"{MARKDOWN_PIPE}{joined_rule}{MARKDOWN_PIPE}"
    body_lines = [markdown_line(row) for row in body]
    header_line = markdown_line(header)
    return LINE_SEPARATOR.join([header_line, header_rule, *body_lines])


def flatten(rows: list[list[PlacedCell]]) -> TableRendering:
    """Render a layout table as text: cells joined by spaces, rows by newlines."""
    lines = [FLATTENED_CELL_SEPARATOR.join(cell.text for cell in row) for row in rows]
    text = LINE_SEPARATOR.join(lines)
    return TableRendering(kind=LAYOUT_TABLE_KIND, text=text)


def render_table(rows: list[list[TableCell]]) -> TableRendering:
    """Clean up a table's cells and render it as Markdown if it holds data, or as text if it is layout."""
    placed_rows = [place_row(row) for row in rows]
    merged_rows = [merge_markers(row) for row in placed_rows]
    non_empty_rows = [row for row in merged_rows if row]
    has_values = any(row_has_value(row) for row in non_empty_rows)
    if not has_values:
        return flatten(non_empty_rows)
    label_start = min(cell.start for row in non_empty_rows for cell in row)
    header_count = count_header_rows(non_empty_rows, label_start)
    header_rows = non_empty_rows[:header_count]
    body_rows = non_empty_rows[header_count:]
    ranges = column_ranges(body_rows)
    if len(ranges) < MIN_DATA_COLUMNS:
        return flatten(non_empty_rows)
    header = header_texts(header_rows, ranges)
    body = [body_texts(row, ranges) for row in body_rows]
    markdown = to_markdown(header, body)
    return TableRendering(kind=DATA_TABLE_KIND, text=markdown)
