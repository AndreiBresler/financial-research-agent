"""Paths, constants and helpers shared by the ingestion tests."""

from pathlib import Path

from bs4 import BeautifulSoup, Tag

TESTS_DIRECTORY = Path(__file__).parent
PROJECT_ROOT = TESTS_DIRECTORY.parent
MINI_FILING_PATH = TESTS_DIRECTORY / "fixtures" / "mini_10k.htm"
REAL_FILING_PATH = PROJECT_ROOT / "data" / "aapl-20250927.htm"
FILE_ENCODING = "utf-8"
HTML_PARSER = "lxml"

PAGE_FOOTER_PATTERN = r"^Apple Inc\. \| \d{4} Form 10-K \| (\d+)$"

MARKDOWN_CELL_SEPARATOR = "|"
MARKDOWN_HEADER_RULE_CHARACTERS = set("|-: ")


def read_filing(path: Path) -> str:
    """Return the HTML text of a filing on disk."""
    return path.read_text(encoding=FILE_ENCODING)


def first_table(html_fragment: str) -> Tag:
    """Parse an HTML fragment and return its first table element."""
    document = BeautifulSoup(html_fragment, HTML_PARSER)
    table = document.find("table")
    assert isinstance(table, Tag), "fragment has no table"
    return table


def split_markdown_row(line: str) -> list[str]:
    """Split one Markdown table line into its stripped cell texts."""
    stripped_line = line.strip()
    inner_line = stripped_line.strip(MARKDOWN_CELL_SEPARATOR)
    cells = inner_line.split(MARKDOWN_CELL_SEPARATOR)
    return [cell.strip() for cell in cells]


def markdown_table_rows(markdown: str) -> list[list[str]]:
    """Return a Markdown table's header and body rows as cell lists, checking its shape on the way."""
    lines = [line for line in markdown.splitlines() if line.strip()]
    assert len(lines) >= 2, f"not a Markdown table:\n{markdown}"
    header_rule = lines[1]
    assert set(header_rule) <= MARKDOWN_HEADER_RULE_CHARACTERS, f"second line is not a header rule: {header_rule!r}"
    rows = [split_markdown_row(line) for index, line in enumerate(lines) if index != 1]
    column_counts = {len(row) for row in rows}
    assert len(column_counts) == 1, f"rows have different column counts: {rows}"
    return rows
