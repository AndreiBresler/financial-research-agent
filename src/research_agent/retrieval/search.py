"""Hybrid search (LLD section 7): relevance gate on the raw dense score, RRF fusion, one-hop cross-references.

Searches are synchronous CPU work; search_10k runs them in a worker thread.
"""

from pydantic import BaseModel

from research_agent.config import Settings
from research_agent.models import Chunk, ChunkKind
from research_agent.retrieval.index import Index, QueryVectors
from research_agent.retrieval.store import ChunkStore

BEST_MATCH_LIMIT = 1
NO_MATCH_SCORE = 0.0


class NotFound(BaseModel):
    """No passage cleared the relevance threshold; section and kind are the filters that were searched, if any."""

    section: str | None
    kind: ChunkKind | None = None


class Searcher:
    """Searches the filing: gate on relevance, fuse dense and sparse rankings, then follow cross-references."""

    def __init__(self, store: ChunkStore, index: Index, settings: Settings) -> None:
        """Keep the store, the index and the settings that hold the search thresholds."""
        self.store = store
        self.index = index
        self.settings = settings

    def scope(self, section: str | None) -> list[str] | None:
        """Return the sections a filter covers, or None for the whole filing."""
        if section is None:
            return None
        return self.store.section_scope(section)

    def best_score(self, vectors: QueryVectors, section_ids: list[str] | None, kind: ChunkKind | None) -> float:
        """Return the best raw dense score within the filters, or 0 when there is nothing to match."""
        best_matches = self.index.best_dense(vectors, section_ids, kind, BEST_MATCH_LIMIT)
        if not best_matches:
            return NO_MATCH_SCORE
        return best_matches[0].score

    def best_dense_score(self, query: str, section: str | None, kind: ChunkKind | None = None) -> float:
        """Return the best raw dense score for a query; the eval uses it to calibrate the threshold."""
        vectors = self.index.embed_query(query)
        section_ids = self.scope(section)
        return self.best_score(vectors, section_ids, kind)

    def search(self, query: str, section: str | None, k: int, kind: ChunkKind | None = None) -> list[Chunk] | NotFound:
        """Return the k best passages plus cross-referenced ones, or NotFound when nothing is relevant enough."""
        vectors = self.index.embed_query(query)
        section_ids = self.scope(section)
        # RRF scores are rank-based and can't tell a weak match from a strong one, so the gate uses the raw cosine.
        best = self.best_score(vectors, section_ids, kind)
        if best < self.settings.min_dense_score:
            return NotFound(section=section, kind=kind)
        prefetch_limit = self.settings.prefetch_limit
        ranked_seqs = self.index.hybrid(vectors, section_ids, kind, prefetch_limit, self.settings.rrf_k, k)
        ranked = [self.store.get(seq) for seq in ranked_seqs]
        return self.expand_cross_refs(ranked, vectors, kind)

    def expand_cross_refs(self, ranked: list[Chunk], vectors: QueryVectors, kind: ChunkKind | None) -> list[Chunk]:
        """Add the best relevant passage of each section the ranked passages refer to, one hop, up to the cap.

        A kind filter applies here too: a search for tables only ever adds tables.
        """
        results = list(ranked)
        present_seqs = {chunk.seq for chunk in ranked}
        visited_sections = {chunk.section_id for chunk in ranked}
        added_count = 0
        for chunk in ranked:
            for reference in chunk.cross_refs:
                if added_count >= self.settings.xref_max_extra:
                    return results
                if reference in visited_sections or not self.store.has_section(reference):
                    continue
                visited_sections.add(reference)
                reference_scope = self.store.section_scope(reference)
                matches = self.index.best_dense(vectors, reference_scope, kind, BEST_MATCH_LIMIT)
                if not matches:
                    continue
                best_match = matches[0]
                if best_match.score < self.settings.min_dense_score or best_match.seq in present_seqs:
                    continue
                added_chunk = self.store.get(best_match.seq)
                results.append(added_chunk)
                present_seqs.add(best_match.seq)
                added_count += 1
        return results
