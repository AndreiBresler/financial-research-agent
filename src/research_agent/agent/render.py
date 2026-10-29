"""Answer rendering (LLD section 9): code, not the model, writes the Sources list and any verification warning."""

import re

from research_agent.models import Evidence, Verification
from research_agent.tools.output import truncate

SOURCES_HEADING = "### Sources"
SOURCE_PREFIX = "- "
WARNING_PREFIX = "> **Verification warning:**"
WARNING_TITLE = f"{WARNING_PREFIX} some claims could not be tied to a source."
ISSUE_PREFIX = "> - "
MAX_LISTED_ISSUES = 5
MAX_ISSUE_CHARS = 100
SECTION_SEPARATOR = "\n\n"
LINE_SEPARATOR = "\n"
CITATION_PATTERN = re.compile(r"\[([DWC][0-9a-f]{1,8})\]")
URL_ISSUE = "Contains a URL; sources are listed under Sources instead"


def issue_lines(verification: Verification) -> list[str]:
    """Describe each failed check in one line: unknown markers, uncited text, then URLs."""
    issues = [f"Unknown citation [{citation_id}]" for citation_id in verification.unknown_ids]
    issues.extend(f"Uncited: {truncate(text, MAX_ISSUE_CHARS)}" for text in verification.uncited)
    if verification.has_urls:
        issues.append(URL_ISSUE)
    return issues


def warning_block(verification: Verification) -> str:
    """Return the warning shown above a failed answer, listing at most five issues."""
    issues = issue_lines(verification)
    listed = issues[:MAX_LISTED_ISSUES]
    lines = [WARNING_TITLE, *(f"{ISSUE_PREFIX}{issue}" for issue in listed)]
    hidden_count = len(issues) - len(listed)
    if hidden_count:
        lines.append(f"{ISSUE_PREFIX}…and {hidden_count} more")
    return LINE_SEPARATOR.join(lines)


def sources_block(answer: str, registry: dict[str, Evidence]) -> str | None:
    """Return the Sources list for the markers the answer cites, in order of first use; None when there are none."""
    markers = dict.fromkeys(CITATION_PATTERN.findall(answer))
    lines = [f"{SOURCE_PREFIX}[{marker}] {registry[marker].source}" for marker in markers if marker in registry]
    if not lines:
        return None
    return LINE_SEPARATOR.join([SOURCES_HEADING, *lines])


def render_answer(answer: str, verification: Verification, registry: dict[str, Evidence]) -> str:
    """Return the answer with Sources appended and, when a check failed, a warning on top."""
    sections = [answer.strip()]
    if not verification.passed:
        sections.insert(0, warning_block(verification))
    sources = sources_block(answer, registry)
    if sources is not None:
        sections.append(sources)
    return SECTION_SEPARATOR.join(sections)
