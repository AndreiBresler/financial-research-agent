"""Chunking (LLD section 6, stage 8): group parsed blocks into units and split each unit to the token limit."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from research_agent.ingestion.parser import HEADING_KIND, TABLE_KIND, Block
from research_agent.models import SECTION_PATH_SEPARATOR, Chunk, ChunkKind

TokenCounter = Callable[[str], int]

PATH_LINE_TERMINATOR = "\n"
PARAGRAPH_SEPARATOR = "\n\n"
MARKDOWN_LINE_SEPARATOR = "\n"
MARKDOWN_HEADER_LINES = 2
DEFAULT_OVERLAP_TOKENS = 40
FIRST_SEQUENCE_NUMBER = 1
TEXT_CHUNK_KIND: ChunkKind = "text"
RISK_FACTOR_CHUNK_KIND: ChunkKind = "risk_factor"
TABLE_CHUNK_KIND: ChunkKind = "table"
# Tokenizers don't add exactly, so a split can overshoot; each retry shrinks the splitter's budget by this factor.
BUDGET_SHRINK_FACTOR = 0.9
MIN_SPLIT_BUDGET = 8


@dataclass
class Unit:
    """Consecutive blocks that form one retrievable unit: a risk factor, a subsection's paragraphs or a table."""

    kind: ChunkKind
    name: str
    position: int
    section_id: str
    section_path: list[str]
    blocks: list[Block] = field(default_factory=list)
    intro: str | None = None  # tables only: the paragraph before the table in its subsection


@dataclass
class ChunkDraft:
    """A chunk's text and source range, before it gets its sequence number."""

    unit: Unit
    text: str
    page_start: int
    page_end: int
    cross_refs: list[str]


def path_line(section_path: list[str]) -> str:
    """Render a section path as one line."""
    return SECTION_PATH_SEPARATOR.join(section_path)


def embedding_text(chunk: Chunk) -> str:
    """Return the text that gets embedded: the section path on one line, then the chunk text."""
    rendered_path = path_line(chunk.section_path)
    return f"{rendered_path}{PATH_LINE_TERMINATOR}{chunk.text}"


def text_unit_kind(block: Block) -> ChunkKind:
    """Return the chunk kind for a text block's unit."""
    return RISK_FACTOR_CHUNK_KIND if block.risk_factor is not None else TEXT_CHUNK_KIND


def unit_name(block: Block) -> str:
    """Name a unit after its risk factor, or else the last element of its section path."""
    if block.risk_factor is not None:
        return block.risk_factor
    return block.section_path[-1]


def block_page(block: Block) -> int:
    """Return a block's page; the parser assigns one to every block."""
    if block.page is None:
        raise ValueError(f"block has no page: {block.text[:60]!r}")
    return block.page


def group_units(blocks: list[Block]) -> list[Unit]:
    """Group blocks into units in document order; headings end a unit and each table is a unit of its own."""
    units: list[Unit] = []
    positions: Counter[str] = Counter()
    last_paragraph: dict[tuple[str, tuple[str, ...]], str] = {}
    current: Unit | None = None
    current_key: tuple[str, tuple[str, ...], str | None] | None = None
    for block in blocks:
        if block.kind == HEADING_KIND:
            current = None
            continue
        section_id = block.section_id or ""
        subsection_key = (section_id, tuple(block.section_path))
        if block.kind == TABLE_KIND:
            positions[section_id] += 1
            table_unit = Unit(
                kind=TABLE_CHUNK_KIND,
                name=unit_name(block),
                position=positions[section_id],
                section_id=section_id,
                section_path=block.section_path,
                blocks=[block],
                intro=last_paragraph.get(subsection_key),
            )
            units.append(table_unit)
            current = None
            continue
        block_key = (section_id, tuple(block.section_path), block.risk_factor)
        if current is None or block_key != current_key:
            positions[section_id] += 1
            current = Unit(
                kind=text_unit_kind(block),
                name=unit_name(block),
                position=positions[section_id],
                section_id=section_id,
                section_path=block.section_path,
            )
            current_key = block_key
            units.append(current)
        current.blocks.append(block)
        last_paragraph[subsection_key] = block.text
    return units


def merge_cross_refs(blocks: list[Block]) -> list[str]:
    """Combine the blocks' cross-references in order of first mention."""
    merged: list[str] = []
    for block in blocks:
        for reference in block.cross_refs:
            if reference not in merged:
                merged.append(reference)
    return merged


def fits(text: str, section_path: list[str], count_tokens: TokenCounter, max_tokens: int) -> bool:
    """Tell whether a chunk text plus its path line fits the token limit."""
    rendered_path = path_line(section_path)
    embedded = f"{rendered_path}{PATH_LINE_TERMINATOR}{text}"
    return count_tokens(embedded) <= max_tokens


def block_spans(blocks: list[Block]) -> list[tuple[int, int]]:
    """Return each block's character range within the unit text joined by blank lines."""
    spans: list[tuple[int, int]] = []
    offset = 0
    for block in blocks:
        end = offset + len(block.text)
        spans.append((offset, end))
        offset = end + len(PARAGRAPH_SEPARATOR)
    return spans


def split_text(text: str, budget: int, overlap_tokens: int, count_tokens: TokenCounter) -> list[str]:
    """Split text into pieces of at most budget tokens with the recursive splitter."""
    overlap = min(overlap_tokens, budget // 2)
    splitter = RecursiveCharacterTextSplitter(chunk_size=budget, chunk_overlap=overlap, length_function=count_tokens)
    return splitter.split_text(text)


def split_to_fit(
    text: str, section_path: list[str], count_tokens: TokenCounter, max_tokens: int, overlap_tokens: int
) -> list[str]:
    """Split text until every piece fits with its path line, shrinking the budget when the tokenizer overshoots."""
    rendered_path = path_line(section_path)
    path_tokens = count_tokens(f"{rendered_path}{PATH_LINE_TERMINATOR}")
    budget = max(max_tokens - path_tokens, MIN_SPLIT_BUDGET)
    while True:
        pieces = split_text(text, budget, overlap_tokens, count_tokens)
        all_fit = all(fits(piece, section_path, count_tokens, max_tokens) for piece in pieces)
        if all_fit or budget <= MIN_SPLIT_BUDGET:
            return pieces
        shrunk_budget = int(budget * BUDGET_SHRINK_FACTOR)
        budget = max(shrunk_budget, MIN_SPLIT_BUDGET)


def piece_blocks(
    piece: str, unit_text: str, search_from: int, unit: Unit, spans: list[tuple[int, int]]
) -> tuple[list[Block], int]:
    """Return the blocks a split piece overlaps and where the piece starts in the unit text."""
    start = unit_text.find(piece, search_from)
    if start < 0:
        return unit.blocks, search_from
    end = start + len(piece)
    overlapped = [
        block
        for block, (block_start, block_end) in zip(unit.blocks, spans, strict=True)
        if block_start < end and block_end > start
    ]
    return overlapped or unit.blocks, start


def draft_from_blocks(unit: Unit, text: str, blocks: list[Block]) -> ChunkDraft:
    """Build a draft whose pages and cross-references come from the given blocks."""
    pages = [block_page(block) for block in blocks]
    cross_refs = merge_cross_refs(blocks)
    return ChunkDraft(unit=unit, text=text, page_start=min(pages), page_end=max(pages), cross_refs=cross_refs)


def text_unit_drafts(unit: Unit, count_tokens: TokenCounter, max_tokens: int, overlap_tokens: int) -> list[ChunkDraft]:
    """Chunk a text unit: whole if it fits, otherwise split with the recursive splitter."""
    texts = [block.text for block in unit.blocks]
    unit_text = PARAGRAPH_SEPARATOR.join(texts)
    if fits(unit_text, unit.section_path, count_tokens, max_tokens):
        return [draft_from_blocks(unit, unit_text, unit.blocks)]
    pieces = split_to_fit(unit_text, unit.section_path, count_tokens, max_tokens, overlap_tokens)
    spans = block_spans(unit.blocks)
    drafts: list[ChunkDraft] = []
    search_from = 0
    for piece in pieces:
        blocks, piece_start = piece_blocks(piece, unit_text, search_from, unit, spans)
        drafts.append(draft_from_blocks(unit, piece, blocks))
        search_from = piece_start + 1
    return drafts


def with_intro(intro: str | None, markdown: str) -> str:
    """Put a table's intro paragraph, if any, in front of its Markdown."""
    if intro is None:
        return markdown
    return f"{intro}{PARAGRAPH_SEPARATOR}{markdown}"


def table_unit_drafts(unit: Unit, count_tokens: TokenCounter, max_tokens: int) -> list[ChunkDraft]:
    """Chunk a table: whole if it fits, otherwise by rows, repeating the intro and header in each part."""
    table_block = unit.blocks[0]
    whole_text = with_intro(unit.intro, table_block.text)
    if fits(whole_text, unit.section_path, count_tokens, max_tokens):
        return [draft_from_blocks(unit, whole_text, unit.blocks)]
    lines = table_block.text.split(MARKDOWN_LINE_SEPARATOR)
    header = lines[:MARKDOWN_HEADER_LINES]
    rows = lines[MARKDOWN_HEADER_LINES:]
    parts: list[list[str]] = []
    current_rows: list[str] = []
    for row in rows:
        candidate_markdown = MARKDOWN_LINE_SEPARATOR.join([*header, *current_rows, row])
        candidate = with_intro(unit.intro, candidate_markdown)
        if current_rows and not fits(candidate, unit.section_path, count_tokens, max_tokens):
            parts.append(current_rows)
            current_rows = []
        current_rows.append(row)
    if current_rows:
        parts.append(current_rows)
    drafts: list[ChunkDraft] = []
    for part_rows in parts:
        part_markdown = MARKDOWN_LINE_SEPARATOR.join([*header, *part_rows])
        part_text = with_intro(unit.intro, part_markdown)
        drafts.append(draft_from_blocks(unit, part_text, unit.blocks))
    return drafts


def build_chunks(
    blocks: list[Block],
    count_tokens: TokenCounter,
    max_tokens: int,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Turn parsed blocks into chunks whose embedded text fits max_tokens, numbered in document order."""
    units = group_units(blocks)
    drafts: list[ChunkDraft] = []
    for unit in units:
        if unit.kind == TABLE_CHUNK_KIND:
            unit_drafts = table_unit_drafts(unit, count_tokens, max_tokens)
        else:
            unit_drafts = text_unit_drafts(unit, count_tokens, max_tokens, overlap_tokens)
        drafts.extend(unit_drafts)
    return [
        Chunk(
            seq=sequence_number,
            kind=draft.unit.kind,
            section_id=draft.unit.section_id,
            section_path=draft.unit.section_path,
            unit=draft.unit.name,
            position=draft.unit.position,
            page_start=draft.page_start,
            page_end=draft.page_end,
            cross_refs=draft.cross_refs,
            text=draft.text,
        )
        for sequence_number, draft in enumerate(drafts, start=FIRST_SEQUENCE_NUMBER)
    ]
