"""Unit tests for answer verification (LLD section 9): the evidence registry, the answer body and the four checks.

The checks are code, never a model call: every marker must resolve, every paragraph, list item and table row must
cite, every sentence with a digit must cite, and the model must not write URLs.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from research_agent.agent.verify import answer_body, check_answer, evidence_registry
from research_agent.models import Evidence, Verification

DOC_EVIDENCE = Evidence(id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12")
WEB_EVIDENCE = Evidence(id="W3f9a1c", kind="web", source="Microsoft Q1 FY2026 results, https://example.com/msft")
CALC_EVIDENCE = Evidence(id="C3bd255", kind="calc", source="34550 / 416161 * 100 = 8.302075")
REGISTRY = {item.id: item for item in (DOC_EVIDENCE, WEB_EVIDENCE, CALC_EVIDENCE)}


def tool_result(evidence: list[Evidence], call_id: str) -> ToolMessage:
    """Return a successful tool result carrying Evidence, as the tools produce."""
    return ToolMessage("passage", tool_call_id=call_id, artifact=evidence)


def uncited_issues(answer: str) -> list[str]:
    """Check an answer against the full registry and return what it flags as uncited."""
    return check_answer(answer, REGISTRY).uncited


class TestRegistry:
    """The registry is derived from the Evidence on the thread's tool results; it is never stored."""

    def test_collects_evidence_from_every_tool_result_in_the_thread(self) -> None:
        """Evidence from earlier questions counts too, since IDs are stable."""
        messages = [
            HumanMessage("first question"),
            AIMessage("", tool_calls=[{"name": "search_10k", "args": {}, "id": "call-1", "type": "tool_call"}]),
            tool_result([DOC_EVIDENCE], "call-1"),
            AIMessage("first answer [D4]"),
            HumanMessage("second question"),
            AIMessage("", tool_calls=[{"name": "calculator", "args": {}, "id": "call-2", "type": "tool_call"}]),
            tool_result([CALC_EVIDENCE], "call-2"),
        ]
        assert evidence_registry(messages) == {"D4": DOC_EVIDENCE, "C3bd255": CALC_EVIDENCE}

    def test_skips_error_results_and_empty_evidence(self) -> None:
        """Error results carry no artifact and not-found results an empty list; neither adds anything."""
        messages = [
            ToolMessage("ERROR web_unavailable: timed out", tool_call_id="call-1", status="error"),
            ToolMessage("NO_RELEVANT_CONTENT: nothing found", tool_call_id="call-2", artifact=[]),
            tool_result([WEB_EVIDENCE], "call-3"),
        ]
        assert evidence_registry(messages) == {"W3f9a1c": WEB_EVIDENCE}


class TestAnswerBody:
    """Only the body is checked: Assumptions and Data gaps describe limits rather than make claims."""

    def test_body_ends_at_assumptions(self) -> None:
        """Text from ### Assumptions on is not part of the body."""
        answer = "Margin was 46.9% [D4].\n\n### Assumptions\n- Fiscal 2025 means the year ended 2025-09-27."
        assert answer_body(answer) == "Margin was 46.9% [D4]."

    def test_body_ends_at_data_gaps(self) -> None:
        """Data gaps alone also ends the body."""
        answer = "Margin was 46.9% [D4].\n\n### Data gaps\n- Microsoft's 2025 margin was not found."
        assert answer_body(answer) == "Margin was 46.9% [D4]."

    def test_whole_answer_without_those_headings(self) -> None:
        """Other headings are part of the body."""
        answer = "## Margin\n\nMargin was 46.9% [D4]."
        assert answer_body(answer) == answer


class TestKnownIds:
    """Every marker in the body must match Evidence in the thread."""

    def test_unknown_markers_are_listed_once_in_order(self) -> None:
        """An invented marker is flagged, once, however often it appears."""
        answer = "Margin was 46.9% [D4] [D999]. Revenue grew [Wabc123]. Margin again [D999]."
        verification = check_answer(answer, REGISTRY)
        assert verification.unknown_ids == ["D999", "Wabc123"]

    def test_all_markers_known(self) -> None:
        """A fully cited answer passes."""
        answer = "Margin was 46.9% [D4]. Microsoft's was 69.8% [W3f9a1c]. R&D was 8.3% of net sales [C3bd255]."
        verification = check_answer(answer, REGISTRY)
        assert verification == Verification()
        assert verification.passed

    def test_markers_after_the_body_are_not_checked(self) -> None:
        """A marker under Data gaps is outside the body."""
        answer = "Margin was 46.9% [D4].\n\n### Data gaps\n- See [D999] for nothing."
        assert check_answer(answer, REGISTRY).unknown_ids == []


class TestParagraphCoverage:
    """Every paragraph, list item and table row cites a source; headings and lead-in lines are exempt."""

    def test_uncited_paragraph(self) -> None:
        """A claim without a marker is flagged even when it has no number."""
        issues = uncited_issues("Margin was 46.9% [D4].\n\nApple faces significant tax risk.")
        assert issues == ["Apple faces significant tax risk."]

    def test_uncited_list_item(self) -> None:
        """Each list item stands alone."""
        issues = uncited_issues("Key risks:\n\n- Tax rates can change [D4].\n- Competition is intense.")
        assert len(issues) == 1
        assert "Competition is intense." in issues[0]

    def test_headings_and_lead_in_lines_are_exempt(self) -> None:
        """Structure lines make no claims."""
        answer = "## Tax risk\n\nThe filing names these risks:\n\n- Tax rates can change [D4]."
        assert uncited_issues(answer) == []

    def test_table_rows_cite_but_header_and_separator_are_exempt(self) -> None:
        """A table row with a figure needs a marker; the header row and the separator don't."""
        answer = "| Company | Gross margin FY2025 |\n|---|---|\n| Apple | 46.9% [D4] |\n| Microsoft | 69.8% |"
        issues = uncited_issues(answer)
        assert len(issues) == 1
        assert "Microsoft" in issues[0]


class TestNumberCoverage:
    """Every sentence with a digit cites a source, even inside a cited paragraph."""

    def test_uncited_sentence_in_a_cited_paragraph(self) -> None:
        """The second figure has no marker of its own."""
        issues = uncited_issues("Gross margin was 46.9% [D4]. Net sales were $416 billion.")
        assert issues == ["Net sales were $416 billion."]

    def test_digits_inside_markers_do_not_count(self) -> None:
        """[D4] contains a digit, but the sentence makes no numeric claim."""
        assert uncited_issues("Tax rates can raise tax expense [D4].") == []

    def test_abbreviations_do_not_split_sentences_wrongly(self) -> None:
        """'Apple Inc.' ends no sentence that matters: the figure and its marker stay together."""
        assert uncited_issues("Apple Inc. reported a 46.9% gross margin [D4].") == []

    def test_decimal_points_do_not_split_sentences(self) -> None:
        """8.3% is one number, not the end of a sentence."""
        assert uncited_issues("R&D was 8.3% of net sales [C3bd255].") == []


class TestRealAnswers:
    """Cases taken from the first end-to-end run: markdown styles the checks must read, and slips they must catch."""

    def test_bold_line_is_a_heading(self) -> None:
        """**Top 3 risk factors** on its own line is a heading, not an uncited claim."""
        assert uncited_issues("**Top 3 risk factors**\n\nGross margin was 46.9% [D4].") == []

    def test_bold_lead_in_ending_in_a_colon(self) -> None:
        """A bold list lead-in ending in a colon introduces its nested items."""
        answer = "- **Product breakdown (fiscal 2025, $ millions):**\n  - iPhone: 209,586 [D4]"
        assert uncited_issues(answer) == []

    def test_nested_items_each_need_a_marker(self) -> None:
        """A marker on the last nested item doesn't cover the ones above it."""
        answer = "- **Product breakdown:**\n  - iPhone: 209,586\n  - Services: 109,158 [D4]"
        assert uncited_issues(answer) == ["iPhone: 209,586"]

    def test_marker_after_the_full_stop(self) -> None:
        """'...retaliation. [D4]' cites the sentence before it."""
        answer = "- New U.S. tariffs were announced in the second quarter of 2025, and others retaliated. [D4]"
        assert uncited_issues(answer) == []

    def test_marker_closing_a_run_of_sentences(self) -> None:
        """A marker at the end of a list item covers the figures in the sentences before it."""
        answer = "- **Tariffs:** New tariffs began in fiscal 2025. Apple says they can affect gross margin [D4]."
        assert uncited_issues(answer) == []

    def test_restated_figure_after_the_last_marker(self) -> None:
        """A number repeated after the last marker still needs its own."""
        issues = uncited_issues("Another source shows 39.3 [W3f9a1c]. That is close to the 39.86 above.")
        assert issues == ["That is close to the 39.86 above."]

    def test_items_under_a_cited_lead_in_inherit_its_marker(self) -> None:
        """'The risk factors list these drivers [D71]:' sources the items nested under it."""
        answer = (
            "- **Outlook.** Apple expects downward pressure [D4]. The risk factors list these drivers [W3f9a1c]:\n"
            "  - pricing pressure and competition\n  - foreign exchange"
        )
        assert uncited_issues(answer) == []

    def test_items_after_a_cited_plain_lead_in_inherit_its_marker(self) -> None:
        """A plain-line lead-in with a marker covers the list right below it."""
        assert uncited_issues("The filing lists these drivers [D4]:\n- pricing pressure\n- inflation") == []

    def test_inheritance_ends_with_the_nested_list(self) -> None:
        """A sibling after the nested items needs its own marker again."""
        answer = "- Drivers [D4]:\n  - pricing pressure\n- Apple faces significant tax risk."
        assert uncited_issues(answer) == ["Apple faces significant tax risk."]

    def test_a_year_is_not_a_figure(self) -> None:
        """'fiscal 2025' after the last marker labels a period; it is not an uncited number."""
        answer = "Diluted EPS was $7.46 [D4]. It is lower than the trailing figure because fiscal 2025 is older."
        assert uncited_issues(answer) == []

    def test_opener_without_a_marker(self) -> None:
        """A summary paragraph restating cited figures must cite them again."""
        answer = "Apple trades at a higher P/E than Microsoft, by about 10.6 turns.\n\n- Gap: 10.61 points [C3bd255]."
        assert uncited_issues(answer) == ["Apple trades at a higher P/E than Microsoft, by about 10.6 turns."]


class TestUrls:
    """Sources are rendered by code, so a URL in the body means the model wrote one itself."""

    @pytest.mark.parametrize("url", ["https://www.apple.com/investor", "http://example.com"])
    def test_url_in_body_is_flagged(self, url: str) -> None:
        """Any http or https link fails the check."""
        verification = check_answer(f"See {url} for details [D4].", REGISTRY)
        assert verification.has_urls
        assert not verification.passed

    def test_no_url(self) -> None:
        """A plain cited answer passes."""
        assert not check_answer("Margin was 46.9% [D4].", REGISTRY).has_urls


class TestBlocksOfContent:
    """Answers arrive as plain text; verify_node joins Claude's content blocks before checking (graph tests)."""

    def test_empty_answer_has_nothing_to_flag(self) -> None:
        """No claims, no issues; the answer's emptiness is visible to the user anyway."""
        assert check_answer("", REGISTRY) == Verification()
