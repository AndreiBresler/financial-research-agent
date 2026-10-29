"""Output formatting shared by the tools (LLD section 7): the not-found code and the output cap.

Every marker the model sees must have its Evidence, so the cap drops whole passages together with their Evidence
rather than cutting text mid-passage.
"""

from pydantic import BaseModel, ConfigDict

from research_agent.models import Evidence

NO_RELEVANT_CONTENT = "NO_RELEVANT_CONTENT"
PASSAGE_SEPARATOR = "\n\n"
HEADER_SEPARATOR = "\n"
TRUNCATION_MARK = "…"


class Passage(BaseModel):
    """One formatted tool result, headed by its citation marker, and the Evidence behind that marker."""

    model_config = ConfigDict(frozen=True)

    text: str
    evidence: Evidence


def truncate(text: str, max_chars: int) -> str:
    """Cut text to at most max_chars, marking the cut with an ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(TRUNCATION_MARK)] + TRUNCATION_MARK


def fit_to_limit(passages: list[Passage], max_chars: int) -> tuple[str, list[Evidence]]:
    """Join passages within max_chars, dropping whole trailing ones so every marker shown has its Evidence."""
    shown_texts: list[str] = []
    shown_evidence: list[Evidence] = []
    used_chars = 0
    for passage in passages:
        separator_chars = len(PASSAGE_SEPARATOR) if shown_texts else 0
        if used_chars + separator_chars + len(passage.text) > max_chars:
            break
        shown_texts.append(passage.text)
        shown_evidence.append(passage.evidence)
        used_chars += separator_chars + len(passage.text)
    if not shown_texts and passages:
        first_passage = passages[0]
        return truncate(first_passage.text, max_chars), [first_passage.evidence]
    content = PASSAGE_SEPARATOR.join(shown_texts)
    return content, shown_evidence
