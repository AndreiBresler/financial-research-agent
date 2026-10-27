"""Unit tests for table cleanup and rendering (LLD section 6, stage 6)."""

from filing_support import first_table, markdown_table_rows
from research_agent.ingestion.tables import TableCell, extract_rows, render_table

NORMAL_STYLE = "font-family:'Helvetica',sans-serif;font-size:9pt;font-weight:400"
BOLD_STYLE = "font-family:'Helvetica',sans-serif;font-size:9pt;font-weight:700"

GROSS_MARGIN_TABLE = f"""
<table>
<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td colspan="3"></td><td colspan="3"><span style="{BOLD_STYLE}">2025</span></td><td colspan="3"></td>
    <td colspan="3"><span style="{BOLD_STYLE}">2024</span></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Gross margin:</span></td><td colspan="3"></td><td colspan="3"></td>
    <td colspan="3"></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Products</span></td><td><span style="{NORMAL_STYLE}">$</span></td>
    <td><span style="{NORMAL_STYLE}">112,887&#160;</span></td><td></td><td colspan="3"></td>
    <td><span style="{NORMAL_STYLE}">$</span></td><td><span style="{NORMAL_STYLE}">109,633&#160;</span></td><td></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Services</span></td>
    <td colspan="2"><span style="{NORMAL_STYLE}">82,314&#160;</span></td><td></td><td colspan="3"></td>
    <td colspan="2"><span style="{NORMAL_STYLE}">71,050&#160;</span></td><td></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Total gross margin</span></td><td><span style="{NORMAL_STYLE}">$</span></td>
    <td><span style="{NORMAL_STYLE}">195,201&#160;</span></td><td></td><td colspan="3"></td>
    <td><span style="{NORMAL_STYLE}">$</span></td><td><span style="{NORMAL_STYLE}">180,683&#160;</span></td><td></td></tr>
</table>
"""

GROSS_MARGIN_PERCENTAGE_TABLE = f"""
<table>
<tr><td colspan="3"></td><td colspan="3"><span style="{BOLD_STYLE}">2025</span></td><td colspan="3"></td>
    <td colspan="3"><span style="{BOLD_STYLE}">2024</span></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Total gross margin percentage</span></td>
    <td colspan="2"><span style="{NORMAL_STYLE}">46.9&#160;</span></td><td><span style="{NORMAL_STYLE}">%</span></td>
    <td colspan="3"></td>
    <td colspan="2"><span style="{NORMAL_STYLE}">46.2&#160;</span></td><td><span style="{NORMAL_STYLE}">%</span></td></tr>
</table>
"""

STATEMENT_OF_OPERATIONS_TABLE = f"""
<table>
<tr><td colspan="3"></td><td colspan="7"><span style="{BOLD_STYLE}">Years ended</span></td></tr>
<tr><td colspan="3"></td><td colspan="3"><span style="{BOLD_STYLE}">September 27,<br/>2025</span></td><td></td>
    <td colspan="3"><span style="{BOLD_STYLE}">September 28,<br/>2024</span></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Other income/(expense), net</span></td>
    <td><span style="{NORMAL_STYLE}">$</span></td><td><span style="{NORMAL_STYLE}">(321</span></td>
    <td><span style="{NORMAL_STYLE}">)</span></td><td></td>
    <td><span style="{NORMAL_STYLE}">$</span></td><td><span style="{NORMAL_STYLE}">269&#160;</span></td><td></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Restructuring charges</span></td>
    <td colspan="2"><span style="{NORMAL_STYLE}">&#8212;&#160;</span></td><td></td><td></td>
    <td colspan="2"><span style="{NORMAL_STYLE}">(1,234</span></td><td><span style="{NORMAL_STYLE}">)</span></td></tr>
</table>
"""

CHANGE_COLUMNS_TABLE = f"""
<table>
<tr><td colspan="3"></td><td colspan="2"><span style="{BOLD_STYLE}">2025</span></td><td></td>
    <td colspan="2"><span style="{BOLD_STYLE}">Change</span></td><td></td>
    <td colspan="2"><span style="{BOLD_STYLE}">2024</span></td></tr>
<tr><td colspan="3"><span style="{NORMAL_STYLE}">Research and development</span></td>
    <td><span style="{NORMAL_STYLE}">$</span></td><td><span style="{NORMAL_STYLE}">34,550</span></td><td></td>
    <td><span style="{NORMAL_STYLE}">10</span></td><td><span style="{NORMAL_STYLE}">%</span></td><td></td>
    <td><span style="{NORMAL_STYLE}">$</span></td><td><span style="{NORMAL_STYLE}">31,370</span></td></tr>
</table>
"""

CHECKBOX_LAYOUT_TABLE = f"""
<table>
<tr><td><span style="{NORMAL_STYLE}">Large accelerated filer</span></td><td><span style="{NORMAL_STYLE}">&#9746;</span></td>
    <td><span style="{NORMAL_STYLE}">Accelerated filer</span></td><td><span style="{NORMAL_STYLE}">&#9744;</span></td></tr>
<tr><td><span style="{NORMAL_STYLE}">Non-accelerated filer</span></td><td><span style="{NORMAL_STYLE}">&#9744;</span></td>
    <td><span style="{NORMAL_STYLE}">Smaller reporting company</span></td><td><span style="{NORMAL_STYLE}">&#9744;</span></td></tr>
</table>
"""

SINGLE_COLUMN_TABLE = f"""
<table>
<tr><td><span style="{NORMAL_STYLE}">Commission File Number: 001-36743</span></td></tr>
<tr><td></td></tr>
</table>
"""


def render_fragment(html_fragment: str) -> tuple[str, str]:
    """Extract and render the first table in a fragment, returning (kind, text)."""
    table = first_table(html_fragment)
    rows = extract_rows(table)
    rendering = render_table(rows)
    return rendering.kind, rendering.text


def render_fragment_rows(html_fragment: str) -> list[list[str]]:
    """Render the first table in a fragment as Markdown and return its rows, asserting it is a data table."""
    kind, text = render_fragment(html_fragment)
    assert kind == "table", f"expected a data table, got {kind}: {text}"
    return markdown_table_rows(text)


class TestExtractRows:
    """Stage 6 input: cell text and spans read from the HTML table."""

    def test_reads_cell_text_and_colspan(self) -> None:
        """Each cell keeps its text and colspan; cells without a colspan span one column."""
        table = first_table(GROSS_MARGIN_TABLE)
        rows = extract_rows(table)
        services_row = rows[4]
        assert services_row[0] == TableCell(text="Services", colspan=3)
        assert services_row[1] == TableCell(text="82,314", colspan=2)
        assert services_row[2] == TableCell(text="", colspan=1)

    def test_normalizes_whitespace_and_line_breaks(self) -> None:
        """Non-breaking spaces are stripped and a line break becomes a single space."""
        table = first_table(STATEMENT_OF_OPERATIONS_TABLE)
        rows = extract_rows(table)
        header_texts = [cell.text for cell in rows[1]]
        assert "September 27, 2025" in header_texts
        all_texts = [cell.text for row in rows for cell in row]
        assert not any("\xa0" in text for text in all_texts)


class TestDataTables:
    """Stage 6: data tables are cleaned up and rendered as Markdown."""

    def test_drops_spacer_columns_and_aligns_values_across_colspans(self) -> None:
        """Values split differently across colspans land in one column per year, with no empty spacer columns."""
        rows = render_fragment_rows(GROSS_MARGIN_TABLE)
        assert rows == [
            ["", "2025", "2024"],
            ["Gross margin:", "", ""],
            ["Products", "$112,887", "$109,633"],
            ["Services", "82,314", "71,050"],
            ["Total gross margin", "$195,201", "$180,683"],
        ]

    def test_merges_percent_cells_into_their_numbers(self) -> None:
        """A % in its own cell joins the number before it."""
        rows = render_fragment_rows(GROSS_MARGIN_PERCENTAGE_TABLE)
        assert rows[-1] == ["Total gross margin percentage", "46.9%", "46.2%"]

    def test_rejoins_split_negatives_and_keeps_dashes(self) -> None:
        """'(321' + ')' becomes '(321)', a leading $ still merges, and an em dash for zero is kept."""
        rows = render_fragment_rows(STATEMENT_OF_OPERATIONS_TABLE)
        assert rows[1] == ["Other income/(expense), net", "$(321)", "$269"]
        assert rows[2] == ["Restructuring charges", "—", "(1,234)"]

    def test_joins_multi_row_header_per_column_including_spanning_cells(self) -> None:
        """A header cell spanning several columns applies to each of them; header rows join top to bottom."""
        rows = render_fragment_rows(STATEMENT_OF_OPERATIONS_TABLE)
        assert rows[0] == ["", "Years ended September 27, 2025", "Years ended September 28, 2024"]

    def test_year_row_is_a_header_and_label_only_row_ends_the_header(self) -> None:
        """A row of bare years is still a header row; a row label with no values ('Gross margin:') is body."""
        rows = render_fragment_rows(GROSS_MARGIN_TABLE)
        assert rows[0] == ["", "2025", "2024"]
        assert rows[1][0] == "Gross margin:"

    def test_keeps_adjacent_value_columns_apart(self) -> None:
        """Percent-change columns next to amounts stay separate columns."""
        rows = render_fragment_rows(CHANGE_COLUMNS_TABLE)
        assert rows == [
            ["", "2025", "Change", "2024"],
            ["Research and development", "$34,550", "10%", "$31,370"],
        ]


class TestLayoutTables:
    """Stage 6: tables used for layout are flattened to text."""

    def test_table_without_numeric_cells_is_flattened(self) -> None:
        """A checkbox table has no numbers, so it becomes text in reading order, not Markdown."""
        kind, text = render_fragment(CHECKBOX_LAYOUT_TABLE)
        assert kind == "text"
        assert "|" not in text
        assert text.index("Large accelerated filer") < text.index("Smaller reporting company")
        assert "Accelerated filer ☐" in text

    def test_single_column_table_is_flattened_even_with_digits(self) -> None:
        """Fewer than 2 columns after cleanup means layout, even when a cell contains digits."""
        kind, text = render_fragment(SINGLE_COLUMN_TABLE)
        assert kind == "text"
        assert text == "Commission File Number: 001-36743"
