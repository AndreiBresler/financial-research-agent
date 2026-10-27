"""Hybrid search (LLD section 7): relevance gate on the raw dense score, RRF fusion, one-hop cross-references.

Searches are synchronous CPU work; search_10k runs them in a worker thread.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from research_agent.config import Settings
from research_agent.models import Chunk
from research_agent.retrieval.index import Index, QueryVectors
from research_agent.retrieval.store import ChunkStore

BEST_MATCH_LIMIT = 1
NO_MATCH_SCORE = 0.0


class NotFound(BaseModel):
    """No passage cleared the relevance threshold; section is the filter that was searched, if any."""

    section: str | None


@dataclass(frozen=True)
class SearchConfig:
    """The thresholds search needs, taken from Settings."""

    min_dense_score: float
    prefetch_limit: int
    rrf_k: int
    xref_max_extra: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "SearchConfig":
        """Copy the search thresholds from Settings."""
        return cls(
            min_dense_score=settings.min_dense_score,
            prefetch_limit=settings.prefetch_limit,
            rrf_k=settings.rrf_k,
            xref_max_extra=settings.xref_max_extra,
        )


class Searcher:
    """Searches the filing: gate on relevance, fuse dense and sparse rankings, then follow cross-references."""

    def __init__(self, store: ChunkStore, index: Index, config: SearchConfig) -> None:
        """Keep the store, the index and the thresholds."""
        self.store = store
        self.index = index
        self.config = config

    def scope(self, section: str | None) -> list[str] | None:
        """Return the sections a filter covers, or None for the whole filing."""
        if section is None:
            return None
        return self.store.section_scope(section)

    def best_score(self, vectors: QueryVectors, section_ids: list[str] | None) -> float:
        """Return the best raw dense score within the sections, or 0 when there is nothing to match."""
        best_matches = self.index.best_dense(vectors, section_ids, BEST_MATCH_LIMIT)
        if not best_matches:
            return NO_MATCH_SCORE
        return best_matches[0].score

    def best_dense_score(self, query: str, section: str | None) -> float:
        """Return the best raw dense score for a query; the eval uses it to calibrate the threshold."""
        vectors = self.index.embed_query(query)
        section_ids = self.scope(section)
        return self.best_score(vectors, section_ids)

    def search(self, query: str, section: str | None, k: int) -> list[Chunk] | NotFound:
        """Return the k best passages plus cross-referenced ones, or NotFound when nothing is relevant enough."""
        vectors = self.index.embed_query(query)
        section_ids = self.scope(section)
        # RRF scores are rank-based and can't tell a weak match from a strong one, so the gate uses the raw cosine.
        best = self.best_score(vectors, section_ids)
        if best < self.config.min_dense_score:
            return NotFound(section=section)
        ranked_seqs = self.index.hybrid(vectors, section_ids, self.config.prefetch_limit, self.config.rrf_k, k)
        ranked = [self.store.get(seq) for seq in ranked_seqs]
        return self.expand_cross_refs(ranked, vectors)

    def expand_cross_refs(self, ranked: list[Chunk], vectors: QueryVectors) -> list[Chunk]:
        """Add the best relevant passage of each section the ranked passages refer to, one hop, up to the cap."""
        results = list(ranked)
        present_seqs = {chunk.seq for chunk in ranked}
        visited_sections = {chunk.section_id for chunk in ranked}
        added_count = 0
        for chunk in ranked:
            for reference in chunk.cross_refs:
                if added_count >= self.config.xref_max_extra:
                    return results
                if reference in visited_sections or not self.store.has_section(reference):
                    continue
                visited_sections.add(reference)
                reference_scope = self.store.section_scope(reference)
                matches = self.index.best_dense(vectors, reference_scope, BEST_MATCH_LIMIT)
                if not matches:
                    continue
                best_match = matches[0]
                if best_match.score < self.config.min_dense_score or best_match.seq in present_seqs:
                    continue
                added_chunk = self.store.get(best_match.seq)
                results.append(added_chunk)
                present_seqs.add(best_match.seq)
                added_count += 1
        return results
