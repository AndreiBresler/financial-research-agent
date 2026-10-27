"""Index (LLD section 7): query-side access to the filing's Qdrant collection, safe across worker threads.

Local Qdrant allows one client per storage folder, so concurrent searches share this client under a lock.
Searches take milliseconds, so the lock costs nothing noticeable.
"""

import threading
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from research_agent.ingestion.embeddings import DenseEmbedder, SparseEmbedder
from research_agent.ingestion.indexer import COLLECTION_NAME, DENSE_VECTOR_NAME, PAYLOAD_SECTION_ID, SPARSE_VECTOR_NAME


@dataclass(frozen=True)
class QueryVectors:
    """A query embedded for both retrievers."""

    dense: list[float]
    sparse: models.SparseVector


@dataclass(frozen=True)
class ScoredSeq:
    """A chunk's sequence number with its raw similarity score."""

    seq: int
    score: float


def section_filter(section_ids: list[str] | None) -> models.Filter | None:
    """Return a filter matching any of the sections, or None to search the whole filing."""
    if section_ids is None:
        return None
    condition = models.FieldCondition(key=PAYLOAD_SECTION_ID, match=models.MatchAny(any=section_ids))
    return models.Filter(must=[condition])


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

    def best_dense(self, vectors: QueryVectors, section_ids: list[str] | None, limit: int) -> list[ScoredSeq]:
        """Return the top dense matches with their raw cosine scores, best first."""
        query_filter = section_filter(section_ids)
        with self.lock:
            response = self.client.query_points(
                self.collection_name,
                query=vectors.dense,
                using=DENSE_VECTOR_NAME,
                query_filter=query_filter,
                limit=limit,
            )
        return [ScoredSeq(seq=int(point.id), score=point.score) for point in response.points]

    def hybrid(
        self, vectors: QueryVectors, section_ids: list[str] | None, prefetch_limit: int, rrf_k: int, limit: int
    ) -> list[int]:
        """Return sequence numbers ranked by Qdrant's RRF fusion of the dense and sparse rankings."""
        query_filter = section_filter(section_ids)
        prefetches = [
            models.Prefetch(query=vectors.dense, using=DENSE_VECTOR_NAME, filter=query_filter, limit=prefetch_limit),
            models.Prefetch(query=vectors.sparse, using=SPARSE_VECTOR_NAME, filter=query_filter, limit=prefetch_limit),
        ]
        # k is explicit because the client default (2) weights top ranks far more than the standard 60.
        fusion = models.RrfQuery(rrf=models.Rrf(k=rrf_k))
        with self.lock:
            response = self.client.query_points(self.collection_name, prefetch=prefetches, query=fusion, limit=limit)
        return [int(point.id) for point in response.points]
