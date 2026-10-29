"""Prompt loading and templating (LLD section 8): the prompt files are read once, at startup, and filled per call.

Placeholders use string.Template, so braces need no escaping but literal dollars are written $$. Each file may use
only the placeholders it is given; a stray $ or a misspelled placeholder fails at startup, naming the file, rather
than mid-question.
"""

from pathlib import Path
from string import Template

SYSTEM_FILE = "system.txt"
EXAMPLES_FILE = "examples.txt"
PLANNER_FILE = "planner.txt"
FINAL_FILE = "final.txt"
FILE_ENCODING = "utf-8"
SYSTEM_EXAMPLES_SEPARATOR = "\n\n"

SECTIONS = "sections"
PLAN = "plan"
MAX_TOOL_ROUNDS = "max_tool_rounds"
QUESTION = "question"
TOOL_RESULTS = "tool_results"
AGENT_PLACEHOLDERS = frozenset({SECTIONS, PLAN, MAX_TOOL_ROUNDS})
PLACEHOLDERS_BY_FILE = {
    SYSTEM_FILE: AGENT_PLACEHOLDERS,
    EXAMPLES_FILE: AGENT_PLACEHOLDERS,
    PLANNER_FILE: frozenset({SECTIONS}),
    FINAL_FILE: frozenset({QUESTION, TOOL_RESULTS}),
}


def load_template(path: Path, allowed_placeholders: frozenset[str]) -> Template:
    """Read a prompt file and check it uses only valid, allowed placeholders."""
    template = Template(path.read_text(encoding=FILE_ENCODING))
    if not template.is_valid():
        raise ValueError(f"{path.name}: invalid placeholder; write a literal dollar sign as $$")
    unknown_placeholders = set(template.get_identifiers()) - allowed_placeholders
    if unknown_placeholders:
        unknown = ", ".join(sorted(unknown_placeholders))
        allowed = ", ".join(sorted(allowed_placeholders))
        raise ValueError(f"{path.name}: unknown placeholder {unknown}; this file may use {allowed}")
    return template


class Prompts:
    """The prompt files, loaded once and filled on demand."""

    def __init__(self, prompts_dir: Path) -> None:
        """Load and validate every prompt file in prompts_dir."""
        self.templates = {
            file_name: load_template(prompts_dir / file_name, allowed_placeholders)
            for file_name, allowed_placeholders in PLACEHOLDERS_BY_FILE.items()
        }

    def planner_prompt(self, sections: str) -> str:
        """Fill the planner prompt with the section list."""
        return self.templates[PLANNER_FILE].substitute({SECTIONS: sections})

    def system_prompt(self, sections: str, plan: str, max_tool_rounds: int) -> str:
        """Fill the agent's system prompt, system.txt then examples.txt, with the sections, plan and tool budget."""
        values = {SECTIONS: sections, PLAN: plan, MAX_TOOL_ROUNDS: max_tool_rounds}
        rules = self.templates[SYSTEM_FILE].substitute(values)
        examples = self.templates[EXAMPLES_FILE].substitute(values)
        return f"{rules}{SYSTEM_EXAMPLES_SEPARATOR}{examples}"

    def final_prompt(self, question: str, tool_results: str) -> str:
        """Fill the prompt that forces an answer at the tool budget with the question and the gathered results."""
        return self.templates[FINAL_FILE].substitute({QUESTION: question, TOOL_RESULTS: tool_results})
