"""Index build (LLD section 6, stage 9): a Qdrant collection with a dense and a sparse vector per chunk."""

from collections.abc import Iterator
from pathlib import Path

from qdrant_client import QdrantClient, models

from research_agent.ingestion.chunker import embedding_text
from research_agent.ingestion.embeddings import EMBED_BATCH_SIZE, DenseEmbedder, SparseEmbedder
from research_agent.models import Chunk

QDRANT_DIRECTORY_NAME = "qdrant"
COLLECTION_NAME = "filing"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PAYLOAD_SECTION_ID = "section_id"
PAYLOAD_KIND = "kind"


def open_qdrant(index_dir: Path) -> QdrantClient:
    """Open the local Qdrant storage in the index folder; local mode allows one client per folder."""
    return QdrantClient(path=str(index_dir / QDRANT_DIRECTORY_NAME))


def batched(chunks: list[Chunk], size: int) -> Iterator[list[Chunk]]:
    """Yield consecutive batches of at most size chunks."""
    for start in range(0, len(chunks), size):
        yield chunks[start : start + size]


class Indexer:
    """Rebuilds the filing's Qdrant collection from chunks; point ID is the chunk's seq."""

    def __init__(
        self,
        client: QdrantClient,
        dense_embedder: DenseEmbedder,
        sparse_embedder: SparseEmbedder,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        """Keep the client, the embedders and the collection to write."""
        self.client = client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.collection_name = collection_name

    @property
    def dense_model(self) -> str:
        """Return the dense model's name, for the manifest."""
        return self.dense_embedder.model_name

    @property
    def sparse_model(self) -> str:
        """Return the sparse model's name, for the manifest."""
        return self.sparse_embedder.model_name

    def recreate_collection(self) -> None:
        """Drop any existing collection and create it with a cosine dense vector and an IDF sparse vector."""
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        dense_params = models.VectorParams(size=self.dense_embedder.dimension, distance=models.Distance.COSINE)
        # BM25 vectors carry term frequencies only; Qdrant applies IDF across the collection.
        sparse_params = models.SparseVectorParams(modifier=models.Modifier.IDF)
        self.client.create_collection(
            self.collection_name,
            vectors_config={DENSE_VECTOR_NAME: dense_params},
            sparse_vectors_config={SPARSE_VECTOR_NAME: sparse_params},
        )

    def points(self, chunks: list[Chunk]) -> list[models.PointStruct]:
        """Embed a batch of chunks and build their points."""
        texts = [embedding_text(chunk) for chunk in chunks]
        dense_vectors = self.dense_embedder.embed_documents(texts)
        sparse_vectors = self.sparse_embedder.embed_documents(texts)
        return [
            models.PointStruct(
                id=chunk.seq,
                vector={DENSE_VECTOR_NAME: dense_vector, SPARSE_VECTOR_NAME: sparse_vector},
                payload={PAYLOAD_SECTION_ID: chunk.section_id, PAYLOAD_KIND: chunk.kind},
            )
            for chunk, dense_vector, sparse_vector in zip(chunks, dense_vectors, sparse_vectors, strict=True)
        ]

    def build(self, chunks: list[Chunk]) -> None:
        """Recreate the collection and index every chunk, embedding in batches."""
        self.recreate_collection()
        for batch in batched(chunks, EMBED_BATCH_SIZE):
            batch_points = self.points(batch)
            self.client.upsert(self.collection_name, batch_points)
