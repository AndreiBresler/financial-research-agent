"""Answer verification (LLD section 9): deterministic checks in code, never a model call.

The evidence registry is derived from the Evidence on the thread's tool results. Only the answer body is checked,
everything above ### Assumptions or ### Data gaps: every marker must resolve, every paragraph, list item and table
row must cite, every sentence with a digit must be followed by a marker within its unit, and the body must contain
no URL. A marker may close a run of sentences, as citations usually do; a figure after a unit's last marker is
uncited.
"""

import re
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage, ToolMessage

from research_agent.agent.nodes import VERIFY_NODE
from research_agent.agent.render import render_answer
from research_agent.agent.state import AgentState
from research_agent.log import NODE_KIND, log_call
from research_agent.models import Evidence, Verification

CITATION_PATTERN = re.compile(r"\[([DWC][0-9a-f]{1,8})\]")
ASSUMPTIONS_HEADING = "### Assumptions"
DATA_GAPS_HEADING = "### Data gaps"
BODY_END_PATTERN = re.compile(rf"^(?:{re.escape(ASSUMPTIONS_HEADING)}|{re.escape(DATA_GAPS_HEADING)})\b", re.MULTILINE)
URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)
DIGIT_PATTERN = re.compile(r"\d")
# A standalone year, as in "fiscal 2025", labels a period rather than stating a figure.
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
# A sentence ends at . ! or ? followed by whitespace and a capital letter or digit, so "Inc. reported" and "8.3%"
# stay whole, and a marker written after the full stop stays with its sentence.
SENTENCE_BREAK_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9$])")
ABBREVIATION_PATTERN = re.compile(r"\b(?:Inc|Corp|Co|Ltd|No|U\.S|vs|e\.g|i\.e)\.$")
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
EMPHASIS_CHARACTERS = "*_"
# A line that is bold and nothing else, such as **Top 3 risk factors**, is a heading.
BOLD_LINE_PATTERN = re.compile(r"^(\*\*|__)[^*_]+\1$")
HEADING_PREFIX = "#"
TABLE_PREFIX = "|"
LEAD_IN_SUFFIX = ":"
PARAGRAPH_JOINER = " "
BLOCK_SEPARATOR_PATTERN = re.compile(r"\n\s*\n")


def evidence_registry(messages: Sequence[BaseMessage]) -> dict[str, Evidence]:
    """Collect the Evidence of every tool result in the thread, keyed by citation ID."""
    registry: dict[str, Evidence] = {}
    for message in messages:
        if not isinstance(message, ToolMessage) or not isinstance(message.artifact, list):
            continue
        for item in message.artifact:
            # Artifacts restored from a checkpoint come back as dicts.
            evidence = Evidence.model_validate(item)
            registry[evidence.id] = evidence
    return registry


def answer_body(answer: str) -> str:
    """Return the answer up to ### Assumptions or ### Data gaps, which describe limits rather than make claims."""
    body_end = BODY_END_PATTERN.search(answer)
    body = answer[: body_end.start()] if body_end else answer
    return body.strip()


def cited_ids(text: str) -> list[str]:
    """Return the citation IDs in text, each once, in order of first use."""
    markers = CITATION_PATTERN.findall(text)
    return list(dict.fromkeys(markers))


def has_marker(text: str) -> bool:
    """Tell whether text cites any source."""
    return CITATION_PATTERN.search(text) is not None


def has_digit(text: str) -> bool:
    """Tell whether text states a figure, ignoring the digits inside markers and standalone years."""
    without_markers = CITATION_PATTERN.sub("", text)
    without_years = YEAR_PATTERN.sub("", without_markers)
    return DIGIT_PATTERN.search(without_years) is not None


def sentences(text: str) -> list[str]:
    """Split text into sentences, keeping abbreviations such as Inc. inside their sentence."""
    parts = SENTENCE_BREAK_PATTERN.split(text)
    merged: list[str] = []
    for part in parts:
        if merged and ABBREVIATION_PATTERN.search(merged[-1]):
            merged[-1] = f"{merged[-1]}{PARAGRAPH_JOINER}{part}"
        else:
            merged.append(part)
    return merged


def is_exempt(line: str) -> bool:
    """Headings, bold-only lines and lead-in lines ending in a colon, bold or not, make no claims."""
    stripped = LIST_ITEM_PATTERN.sub("", line).strip()
    if stripped.startswith(HEADING_PREFIX) or BOLD_LINE_PATTERN.match(stripped):
        return True
    without_emphasis = stripped.strip(EMPHASIS_CHARACTERS)
    return without_emphasis.endswith(LEAD_IN_SUFFIX)


def table_units(lines: list[str]) -> list[str]:
    """Return a table's data rows: the header row and the separator make no claims."""
    data_rows = [line.strip() for line in lines[1:]]
    return [row for row in data_rows if not TABLE_SEPARATOR_PATTERN.match(row)]


def indentation(line: str) -> int:
    """Return the number of leading spaces, which is how Markdown nests list items."""
    return len(line) - len(line.lstrip())


def list_units(lines: list[str]) -> list[str]:
    """Return each list item as a unit; items under a lead-in that cites a source inherit its markers."""
    units: list[str] = []
    lead_in_indent: int | None = None
    lead_in_markers = ""
    for line in lines:
        line_indent = indentation(line)
        if lead_in_indent is not None and line_indent <= lead_in_indent:
            lead_in_indent = None
        if is_exempt(line):
            markers = CITATION_PATTERN.findall(line)
            if markers:
                # A plain-line lead-in covers the list items at its own level; a list-item lead-in, its children.
                is_list_item = LIST_ITEM_PATTERN.match(line) is not None
                lead_in_indent = line_indent if is_list_item else line_indent - 1
                lead_in_markers = PARAGRAPH_JOINER.join(f"[{marker}]" for marker in markers)
            continue
        item = LIST_ITEM_PATTERN.sub("", line).strip()
        units.append(f"{item}{PARAGRAPH_JOINER}{lead_in_markers}" if lead_in_indent is not None else item)
    return units


def block_units(block: str) -> list[str]:
    """Split a block of lines into checkable units: list items, table rows or one paragraph."""
    lines = [line for line in block.splitlines() if line.strip()]
    if lines and lines[0].strip().startswith(TABLE_PREFIX):
        return table_units(lines)
    if any(LIST_ITEM_PATTERN.match(line) for line in lines):
        return list_units(lines)
    claim_lines = [line.strip() for line in lines if not is_exempt(line)]
    return [PARAGRAPH_JOINER.join(claim_lines)] if claim_lines else []


def claim_units(body: str) -> list[str]:
    """Return every paragraph, list item and table row of the body that must cite a source."""
    blocks = BLOCK_SEPARATOR_PATTERN.split(body)
    return [unit for block in blocks for unit in block_units(block)]


def figures_after_last_marker(unit: str) -> list[str]:
    """Return the sentences with a number that no marker follows within the unit."""
    pending: list[str] = []
    for sentence in sentences(unit):
        if has_marker(sentence):
            pending = []
        elif has_digit(sentence):
            pending.append(sentence)
    return pending


def uncited_text(units: list[str]) -> list[str]:
    """Flag each uncited unit once, and each figure after the last marker of a cited unit."""
    flagged: list[str] = []
    for unit in units:
        if has_marker(unit):
            flagged.extend(figures_after_last_marker(unit))
        else:
            flagged.append(unit)
    return flagged


def check_answer(answer: str, registry: dict[str, Evidence]) -> Verification:
    """Run the four checks on the answer body."""
    body = answer_body(answer)
    unknown_ids = [citation_id for citation_id in cited_ids(body) if citation_id not in registry]
    return Verification(
        unknown_ids=unknown_ids,
        uncited=uncited_text(claim_units(body)),
        has_urls=URL_PATTERN.search(body) is not None,
    )


@log_call(NODE_KIND, VERIFY_NODE)
async def verify_node(state: AgentState) -> dict[str, Any]:
    """Check the final answer against the thread's evidence and store it rendered, with Sources, as final."""
    messages = state["messages"]
    answer = messages[-1].text
    registry = evidence_registry(messages)
    verification = check_answer(answer, registry)
    return {"final": render_answer(answer, verification, registry)}
