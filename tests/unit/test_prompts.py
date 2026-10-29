"""Unit tests for prompt loading and templating (LLD section 8): files read once, strict placeholders, real prompts."""

import re
from pathlib import Path

import pytest

from filing_support import PROJECT_ROOT
from research_agent.prompts import Prompts

FILE_ENCODING = "utf-8"
REAL_PROMPTS_DIR = PROJECT_ROOT / "prompts"
SECTIONS = "item:1A Risk Factors, item:7 Management’s Discussion and Analysis"
PLAN = "1. Find Apple's gross margin in Item 7 (search_10k)"
MAX_TOOL_ROUNDS = 6

SYSTEM_TEMPLATE = "Rules. Sections: $sections. Plan: $plan. Tool rounds: $max_tool_rounds."
EXAMPLES_TEMPLATE = "Example: net sales were $$416,161 million [D120]."
PLANNER_TEMPLATE = "Plan the question. Sections: $sections."
FINAL_TEMPLATE = "No tool rounds left; answer now.\nQuestion: $question\nResults:\n$tool_results"
QUESTION = "What is Apple's gross margin?"
TOOL_RESULTS = "[D4] Part II › Item 7 › Gross Margin (p. 23)\nTotal gross margin percentage 46.9%"

ASSUMPTIONS_HEADING = "### Assumptions"
DATA_GAPS_HEADING = "### Data gaps"
UNTRUSTED_TAG = "<untrusted_web_content>"
CITATION_PREFIXES = ("[D", "[W", "[C")
URL_PATTERN = re.compile(r"https?://")


def write_prompts(
    directory: Path,
    system: str = SYSTEM_TEMPLATE,
    examples: str = EXAMPLES_TEMPLATE,
    planner: str = PLANNER_TEMPLATE,
    final: str = FINAL_TEMPLATE,
) -> Path:
    """Write the four prompt files into directory and return it."""
    (directory / "system.txt").write_text(system, encoding=FILE_ENCODING)
    (directory / "examples.txt").write_text(examples, encoding=FILE_ENCODING)
    (directory / "planner.txt").write_text(planner, encoding=FILE_ENCODING)
    (directory / "final.txt").write_text(final, encoding=FILE_ENCODING)
    return directory


class TestFilling:
    """Placeholders are filled with string.Template, so braces need no escaping but dollars do."""

    def test_planner_prompt_fills_the_sections(self, tmp_path: Path) -> None:
        """The planner prompt gets the section list."""
        prompts = Prompts(write_prompts(tmp_path))
        assert prompts.planner_prompt(SECTIONS) == f"Plan the question. Sections: {SECTIONS}."

    def test_system_prompt_fills_all_placeholders_and_appends_examples(self, tmp_path: Path) -> None:
        """The system prompt is system.txt then examples.txt, with sections, plan and tool budget filled in."""
        prompts = Prompts(write_prompts(tmp_path))
        system_prompt = prompts.system_prompt(SECTIONS, PLAN, MAX_TOOL_ROUNDS)
        assert system_prompt.startswith(f"Rules. Sections: {SECTIONS}. Plan: {PLAN}. Tool rounds: 6.")
        assert system_prompt.endswith("Example: net sales were $416,161 million [D120].")

    def test_final_prompt_fills_the_question_and_tool_results(self, tmp_path: Path) -> None:
        """At the tool budget, the model gets the question and the gathered tool output as plain text."""
        prompts = Prompts(write_prompts(tmp_path))
        final_prompt = prompts.final_prompt(QUESTION, TOOL_RESULTS)
        assert final_prompt == f"No tool rounds left; answer now.\nQuestion: {QUESTION}\nResults:\n{TOOL_RESULTS}"

    def test_braces_need_no_escaping(self, tmp_path: Path) -> None:
        """JSON-like braces in examples pass through unchanged."""
        prompts = Prompts(write_prompts(tmp_path, examples='{"tool": "calculator"} costs $$1'))
        system_prompt = prompts.system_prompt(SECTIONS, PLAN, MAX_TOOL_ROUNDS)
        assert system_prompt.endswith('{"tool": "calculator"} costs $1')

    def test_values_are_not_templated_again(self, tmp_path: Path) -> None:
        """A dollar sign inside a filled value, such as a plan step quoting a figure, is inserted as is."""
        prompts = Prompts(write_prompts(tmp_path))
        system_prompt = prompts.system_prompt(SECTIONS, "Compare $AAPL with $plan", MAX_TOOL_ROUNDS)
        assert "Plan: Compare $AAPL with $plan." in system_prompt

    def test_files_are_read_once(self, tmp_path: Path) -> None:
        """Prompts are loaded at construction; editing a file afterwards doesn't change a running agent."""
        prompts_dir = write_prompts(tmp_path)
        prompts = Prompts(prompts_dir)
        (prompts_dir / "planner.txt").write_text("Changed.", encoding=FILE_ENCODING)
        assert prompts.planner_prompt(SECTIONS) == f"Plan the question. Sections: {SECTIONS}."


class TestValidation:
    """A broken prompt file fails at startup, naming the file, rather than mid-question."""

    @pytest.mark.parametrize(
        ("file_name", "templates"),
        [
            ("system.txt", {"system": "Net sales were $416,161 million."}),
            ("examples.txt", {"examples": "Ticker $AAPL."}),
            ("planner.txt", {"planner": "Sections: $sections. Plan: $plan."}),
            ("system.txt", {"system": "Sections: $section."}),
            ("final.txt", {"final": "Question: $question. Plan: $plan."}),
        ],
    )
    def test_unknown_or_invalid_placeholders_are_rejected(
        self, tmp_path: Path, file_name: str, templates: dict[str, str]
    ) -> None:
        """A literal dollar written as $ instead of $$, or a placeholder the file doesn't get, is an error."""
        prompts_dir = write_prompts(tmp_path, **templates)
        with pytest.raises(ValueError, match=re.escape(file_name)):
            Prompts(prompts_dir)

    def test_missing_file_is_an_error(self, tmp_path: Path) -> None:
        """All four prompt files are required."""
        prompts_dir = write_prompts(tmp_path)
        (prompts_dir / "examples.txt").unlink()
        with pytest.raises(FileNotFoundError):
            Prompts(prompts_dir)


class TestRealPrompts:
    """The prompt files in prompts/ load, and carry the rules other modules depend on (CLAUDE.md invariants)."""

    @pytest.fixture
    def prompts(self) -> Prompts:
        """Load the real prompt files."""
        return Prompts(REAL_PROMPTS_DIR)

    def test_planner_prompt_lists_the_sections(self, prompts: Prompts) -> None:
        """The planner sees the section IDs it can plan searches over."""
        assert SECTIONS in prompts.planner_prompt(SECTIONS)

    def test_system_prompt_carries_the_filled_context(self, prompts: Prompts) -> None:
        """Sections, plan and the remaining tool rounds all reach the model."""
        system_prompt = prompts.system_prompt(SECTIONS, PLAN, MAX_TOOL_ROUNDS)
        assert SECTIONS in system_prompt
        assert PLAN in system_prompt
        assert str(MAX_TOOL_ROUNDS) in system_prompt

    def test_system_prompt_names_the_answer_headings(self, prompts: Prompts) -> None:
        """verify and render split the answer on these headings, so the prompt must use them verbatim."""
        system_prompt = prompts.system_prompt(SECTIONS, PLAN, MAX_TOOL_ROUNDS)
        assert ASSUMPTIONS_HEADING in system_prompt
        assert DATA_GAPS_HEADING in system_prompt

    def test_system_prompt_explains_markers_and_untrusted_content(self, prompts: Prompts) -> None:
        """The model is shown all three marker kinds and told what the untrusted wrapper means."""
        system_prompt = prompts.system_prompt(SECTIONS, PLAN, MAX_TOOL_ROUNDS)
        assert UNTRUSTED_TAG in system_prompt
        for prefix in CITATION_PREFIXES:
            assert prefix in system_prompt

    def test_final_prompt_asks_for_an_answer_with_data_gaps(self, prompts: Prompts) -> None:
        """At the budget the model must answer from what it has and list what's missing under Data gaps."""
        final_prompt = prompts.final_prompt(QUESTION, TOOL_RESULTS)
        assert QUESTION in final_prompt
        assert TOOL_RESULTS in final_prompt
        assert DATA_GAPS_HEADING in final_prompt

    def test_prompts_contain_no_urls(self, prompts: Prompts) -> None:
        """The model must never write URLs, so the examples it imitates contain none."""
        system_prompt = prompts.system_prompt(SECTIONS, PLAN, MAX_TOOL_ROUNDS)
        planner_prompt = prompts.planner_prompt(SECTIONS)
        final_prompt = prompts.final_prompt(QUESTION, TOOL_RESULTS)
        assert not URL_PATTERN.search(system_prompt)
        assert not URL_PATTERN.search(planner_prompt)
        assert not URL_PATTERN.search(final_prompt)
