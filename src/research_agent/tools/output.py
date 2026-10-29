"""What the tools share (LLD section 7): the citation markers, the not-found code and the output cap.

Every marker the model sees must have its Evidence, so the cap drops whole passages together with their Evidence
rather than cutting text mid-passage. verify and render parse answers with the same marker pattern.
"""

import hashlib
import re

from pydantic import BaseModel, ConfigDict

from research_agent.config import TEXT_ENCODING
from research_agent.models import Evidence

# A citation marker: [D137] for a 10-K chunk, [W3f9a1c] for a web page, [C7b2e04] for a calculation.
CITATION_PATTERN = re.compile(r"\[([DWC][0-9a-f]{1,8})\]")
HASHED_ID_HEX_CHARS = 6
NO_RELEVANT_CONTENT = "NO_RELEVANT_CONTENT"
PASSAGE_SEPARATOR = "\n\n"
HEADER_SEPARATOR = "\n"
TRUNCATION_MARK = "…"


class Passage(BaseModel):
    """One formatted tool result, headed by its citation marker, and the Evidence behind that marker."""

    model_config = ConfigDict(frozen=True)

    text: str
    evidence: Evidence


def hashed_citation_id(prefix: str, text: str) -> str:
    """Return a stable citation ID: the prefix plus the first 6 hex characters of the text's SHA-1."""
    encoded_text = text.encode(TEXT_ENCODING)
    digest = hashlib.sha1(encoded_text).hexdigest()
    return f"{prefix}{digest[:HASHED_ID_HEX_CHARS]}"


def cited_ids(text: str) -> list[str]:
    """Return the citation IDs in text, each once, in order of first use."""
    markers = CITATION_PATTERN.findall(text)
    return list(dict.fromkeys(markers))


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
