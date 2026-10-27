"""Text extraction and whitespace normalization shared by the parser and table cleanup."""

import re

from bs4.element import NavigableString, PreformattedString, Tag

NON_BREAKING_SPACE = "\xa0"
SPACE = " "
LINE_BREAK_TAG = "br"
WHITESPACE_RUN = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Turn non-breaking spaces into spaces, collapse whitespace runs and trim."""
    spaced_text = text.replace(NON_BREAKING_SPACE, SPACE)
    collapsed_text = WHITESPACE_RUN.sub(SPACE, spaced_text)
    return collapsed_text.strip()


def is_text_node(node: object) -> bool:
    """Tell whether a node is document text, as opposed to a comment, doctype or other markup string."""
    return isinstance(node, NavigableString) and not isinstance(node, PreformattedString)


def element_text(element: Tag) -> str:
    """Return an element's text joined without separators, with line breaks as spaces, normalized.

    Inline-XBRL tags split words and dates mid-token, so joining with a separator would insert stray spaces.
    """
    pieces: list[str] = []
    for node in element.descendants:
        if is_text_node(node):
            pieces.append(str(node))
        elif isinstance(node, Tag) and node.name == LINE_BREAK_TAG:
            pieces.append(SPACE)
    joined_text = "".join(pieces)
    return normalize_whitespace(joined_text)
