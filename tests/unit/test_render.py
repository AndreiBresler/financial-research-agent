"""Unit tests for rendering (LLD section 9): the Sources list from the registry, and the warning when checks fail."""

from research_agent.agent.render import (
    ISSUE_PREFIX,
    MAX_LISTED_ISSUES,
    SOURCES_HEADING,
    WARNING_PREFIX,
    render_answer,
)
from research_agent.models import Evidence, Verification

DOC_EVIDENCE = Evidence(id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12")
WEB_EVIDENCE = Evidence(id="W3f9a1c", kind="web", source="Microsoft Q1 FY2026 results, https://example.com/msft")
CALC_EVIDENCE = Evidence(id="C3bd255", kind="calc", source="34550 / 416161 * 100 = 8.302075")
REGISTRY = {item.id: item for item in (DOC_EVIDENCE, WEB_EVIDENCE, CALC_EVIDENCE)}
PASSED = Verification()


class TestSources:
    """Code, not the model, writes the Sources list: one line per cited marker, in order of first use."""

    def test_sources_follow_the_answer_in_order_of_first_use(self) -> None:
        """Each cited ID is listed once, with the source line its Evidence carries."""
        answer = "R&D was 8.3% of net sales [C3bd255]. Margin was 46.9% [D4]. R&D again [C3bd255]."
        rendered = render_answer(answer, PASSED, REGISTRY)
        assert rendered == (
            f"{answer}\n\n{SOURCES_HEADING}\n- [C3bd255] {CALC_EVIDENCE.source}\n- [D4] {DOC_EVIDENCE.source}"
        )

    def test_markers_under_assumptions_are_listed_too(self) -> None:
        """A marker anywhere in the answer gets its source, even outside the checked body."""
        answer = "Margin was 46.9% [D4].\n\n### Assumptions\n- Microsoft's latest quarter [W3f9a1c]."
        rendered = render_answer(answer, PASSED, REGISTRY)
        assert rendered.endswith(f"- [D4] {DOC_EVIDENCE.source}\n- [W3f9a1c] {WEB_EVIDENCE.source}")

    def test_unknown_markers_get_no_source_line(self) -> None:
        """There is nothing to render for an ID the tools never produced; the warning reports it instead."""
        answer = "Margin was 46.9% [D4] [D999]."
        rendered = render_answer(answer, Verification(unknown_ids=["D999"]), REGISTRY)
        sources = rendered.split(SOURCES_HEADING)[1]
        assert "[D999]" not in sources

    def test_no_markers_no_sources(self) -> None:
        """An answer that cites nothing gets no empty Sources heading."""
        answer = "The filing doesn't cover this."
        rendered = render_answer(answer, PASSED, REGISTRY)
        assert SOURCES_HEADING not in rendered

    def test_trailing_whitespace_is_trimmed_before_sources(self) -> None:
        """Exactly one blank line separates the answer from Sources."""
        rendered = render_answer("Margin was 46.9% [D4].\n\n\n", PASSED, REGISTRY)
        assert f"[D4].\n\n{SOURCES_HEADING}\n" in rendered


class TestWarning:
    """A failed check puts a warning above the answer, listing up to five issues; the answer is still shown."""

    def test_passing_answer_has_no_warning(self) -> None:
        """Nothing is prepended when every check passes."""
        answer = "Margin was 46.9% [D4]."
        assert render_answer(answer, PASSED, REGISTRY).startswith(answer)

    def test_warning_lists_each_kind_of_issue(self) -> None:
        """Unknown markers, uncited text and URLs each get an issue line, above the unchanged answer."""
        answer = "Margin was 46.9% [D999]. Net sales were $416 billion. See https://apple.com."
        verification = Verification(unknown_ids=["D999"], uncited=["Net sales were $416 billion."], has_urls=True)
        rendered = render_answer(answer, verification, REGISTRY)
        warning = rendered.split(answer)[0]
        issue_lines = [line for line in warning.splitlines() if line.startswith(ISSUE_PREFIX)]
        assert rendered.startswith(WARNING_PREFIX)
        assert len(issue_lines) == 3
        assert "D999" in issue_lines[0]
        assert "Net sales were $416 billion." in issue_lines[1]
        assert "URL" in issue_lines[2]
        assert answer in rendered

    def test_at_most_five_issues_are_listed(self) -> None:
        """Eight uncited sentences list five, then say how many more."""
        uncited = [f"Uncited claim number {index}." for index in range(1, 9)]
        rendered = render_answer(" ".join(uncited), Verification(uncited=uncited), REGISTRY)
        warning = rendered.split("Uncited claim number 1. Uncited claim number 2.")[0]
        issue_lines = [line for line in warning.splitlines() if line.startswith(ISSUE_PREFIX)]
        assert len(issue_lines) == MAX_LISTED_ISSUES + 1
        assert "3 more" in issue_lines[-1]

    def test_long_uncited_text_is_shortened_in_the_warning(self) -> None:
        """The warning quotes the start of an uncited paragraph, not all of it."""
        long_paragraph = "Apple faces risk" + " and more risk" * 40
        rendered = render_answer(long_paragraph, Verification(uncited=[long_paragraph]), REGISTRY)
        warning = rendered.split(long_paragraph)[0]
        assert "Apple faces risk" in warning
        assert len(warning) < len(long_paragraph)
