"""ChunkStore (LLD section 7): the indexed chunks in memory, with lookups by seq, section and position.

Structural queries, such as the first N risk factors or a cross-reference target, never touch the vector index.
"""

from pathlib import Path

from research_agent.ingestion.pipeline import read_chunks
from research_agent.models import Chunk

NOTES_PARENT_SECTION = "item:8"
NOTE_ID_PREFIX = "note:"


class ChunkStore:
    """All chunks of the filing, in document order."""

    def __init__(self, chunks: list[Chunk]) -> None:
        """Index the chunks by seq and record the sections in document order."""
        self.chunks = sorted(chunks, key=lambda chunk: chunk.seq)
        self.chunks_by_seq = {chunk.seq: chunk for chunk in self.chunks}
        section_order = dict.fromkeys(chunk.section_id for chunk in self.chunks)
        self.ordered_sections = list(section_order)
        self.known_sections = set(self.ordered_sections)

    @classmethod
    def load(cls, index_dir: Path) -> "ChunkStore":
        """Load the chunks written by the last ingestion."""
        chunks = read_chunks(index_dir)
        return cls(chunks)

    def get(self, seq: int) -> Chunk:
        """Return the chunk with this sequence number; raises KeyError when there is none."""
        return self.chunks_by_seq[seq]

    def section_ids(self) -> list[str]:
        """Return every section ID, in document order."""
        return list(self.ordered_sections)

    def has_section(self, section_id: str) -> bool:
        """Tell whether the filing has this section."""
        return section_id in self.known_sections

    def section_scope(self, section_id: str) -> list[str]:
        """Return the sections a filter on this section covers: Item 8 includes its notes, others only themselves."""
        if section_id != NOTES_PARENT_SECTION:
            return [section_id]
        note_sections = [section for section in self.ordered_sections if section.startswith(NOTE_ID_PREFIX)]
        return [section_id, *note_sections]

    def first_units(self, section_id: str, k: int, kind: str | None = None) -> list[Chunk]:
        """Return the opening part of each of the first k units of a section's scope, in document order.

        One part per unit, so a long unit (a risk factor split into twelve parts) can't push the next ones out of
        the tool's output cap; the opening part carries the unit's title.
        """
        scope = set(self.section_scope(section_id))
        openings: dict[tuple[str, int], Chunk] = {}
        for chunk in self.chunks:
            if chunk.section_id in scope and (kind is None or chunk.kind == kind):
                openings.setdefault((chunk.section_id, chunk.position), chunk)
        return list(openings.values())[:k]
