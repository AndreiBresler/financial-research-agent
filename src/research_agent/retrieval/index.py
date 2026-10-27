"""Index (LLD section 7): query-side access to the filing's Qdrant collection, safe across worker threads.

Local Qdrant allows one client per storage folder, so concurrent searches share this client, and every
query to it holds a lock. Query embedding runs outside the lock, so parallel searches embed concurrently.
Queries take milliseconds, so the lock costs nothing noticeable.
"""

import threading

from pydantic import BaseModel, ConfigDict
from qdrant_client import QdrantClient, models

from research_agent.ingestion.embeddings import DenseEmbedder, SparseEmbedder
from research_agent.ingestion.indexer import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    PAYLOAD_KIND,
    PAYLOAD_SECTION_ID,
    SPARSE_VECTOR_NAME,
)
from research_agent.models import ChunkKind


class QueryVectors(BaseModel):
    """A query embedded for both retrievers."""

    model_config = ConfigDict(frozen=True)

    dense: list[float]
    sparse: models.SparseVector


class ScoredSeq(BaseModel):
    """A chunk's sequence number with its raw similarity score."""

    model_config = ConfigDict(frozen=True)

    seq: int
    score: float


def chunk_filter(section_ids: list[str] | None, kind: ChunkKind | None) -> models.Filter | None:
    """Return a filter on any of the sections and on the chunk kind, or None to search everything."""
    conditions: list[models.Condition] = []
    if section_ids is not None:
        section_match = models.MatchAny(any=section_ids)
        conditions.append(models.FieldCondition(key=PAYLOAD_SECTION_ID, match=section_match))
    if kind is not None:
        kind_match = models.MatchValue(value=kind)
        conditions.append(models.FieldCondition(key=PAYLOAD_KIND, match=kind_match))
    if not conditions:
        return None
    return models.Filter(must=conditions)


class Index:
    """Embeds queries and runs dense and hybrid queries against the collection."""

    def __init__(
        self,
        client: QdrantClient,
        dense_embedder: DenseEmbedder,
        sparse_embedder: SparseEmbedder,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        """Keep the client, the embedders and a lock shared by all searches."""
        self.client = client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.collection_name = collection_name
        self.lock = threading.Lock()

    def embed_query(self, query: str) -> QueryVectors:
        """Embed a query for the dense and the sparse retriever."""
        dense_vector = self.dense_embedder.embed_query(query)
        sparse_vector = self.sparse_embedder.embed_query(query)
        return QueryVectors(dense=dense_vector, sparse=sparse_vector)

    def best_dense(
        self, vectors: QueryVectors, section_ids: list[str] | None, kind: ChunkKind | None, limit: int
    ) -> list[ScoredSeq]:
        """Return the top dense matches with their raw cosine scores, best first."""
        query_filter = chunk_filter(section_ids, kind)
        with self.lock:
            response = self.client.query_points(
                self.collection_name,
                query=vectors.dense,
                using=DENSE_VECTOR_NAME,
                query_filter=query_filter,
                limit=limit,
            )
        scored: list[ScoredSeq] = []
        for point in response.points:
            sequence_number = int(point.id)
            scored.append(ScoredSeq(seq=sequence_number, score=point.score))
        return scored

    def hybrid(
        self,
        vectors: QueryVectors,
        section_ids: list[str] | None,
        kind: ChunkKind | None,
        prefetch_limit: int,
        rrf_k: int,
        limit: int,
    ) -> list[int]:
        """Return sequence numbers ranked by Qdrant's RRF fusion of the dense and sparse rankings."""
        query_filter = chunk_filter(section_ids, kind)
        prefetches = [
            models.Prefetch(query=vectors.dense, using=DENSE_VECTOR_NAME, filter=query_filter, limit=prefetch_limit),
            models.Prefetch(query=vectors.sparse, using=SPARSE_VECTOR_NAME, filter=query_filter, limit=prefetch_limit),
        ]
        # k is explicit because the client default (2) weights top ranks far more than the standard 60.
        rrf_parameters = models.Rrf(k=rrf_k)
        fusion = models.RrfQuery(rrf=rrf_parameters)
        with self.lock:
            response = self.client.query_points(self.collection_name, prefetch=prefetches, query=fusion, limit=limit)
        return [int(point.id) for point in response.points]
