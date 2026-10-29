"""Unit tests for the Qdrant index build (LLD section 6, stage 9) on an in-memory Qdrant with fake embedders."""

import pytest
from qdrant_client import QdrantClient, models

from ingestion_fakes import FakeDenseEmbedder, FakeSparseEmbedder
from research_agent.ingestion.chunker import embedding_text
from research_agent.ingestion.embeddings import EMBED_BATCH_SIZE
from research_agent.ingestion.indexer import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    Indexer,
)
from research_agent.models import Chunk

IN_MEMORY_LOCATION = ":memory:"
LARGE_BATCH_CHUNK_COUNT = 2 * EMBED_BATCH_SIZE + 2


def make_chunk(seq: int, text: str, section_id: str = "item:7", kind: str = "text") -> Chunk:
    """Build a chunk with plausible metadata around the given text."""
    return Chunk(
        seq=seq,
        kind=kind,
        section_id=section_id,
        section_path=["Part II", "Item 7. Management’s Discussion and Analysis", "Gross Margin"],
        unit="Gross Margin",
        position=seq,
        page_start=23,
        page_end=23,
        cross_refs=[],
        text=text,
    )


@pytest.fixture
def client() -> QdrantClient:
    """Return a fresh in-memory Qdrant."""
    return QdrantClient(IN_MEMORY_LOCATION)


@pytest.fixture
def dense_embedder() -> FakeDenseEmbedder:
    """Return a recording dense embedder."""
    return FakeDenseEmbedder()


@pytest.fixture
def sparse_embedder() -> FakeSparseEmbedder:
    """Return a recording sparse embedder."""
    return FakeSparseEmbedder()


@pytest.fixture
def indexer(client: QdrantClient, dense_embedder: FakeDenseEmbedder, sparse_embedder: FakeSparseEmbedder) -> Indexer:
    """Return an indexer wired to the in-memory Qdrant and the fakes."""
    return Indexer(client, dense_embedder, sparse_embedder)


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """Return three chunks with distinct text and metadata."""
    return [
        make_chunk(1, "Gross margin percentage was 46.9 percent."),
        make_chunk(2, "The Company depends on carriers and resellers.", section_id="item:1A", kind="risk_factor"),
        make_chunk(3, "| Products | $112,887 |\n|---|---|", kind="table"),
    ]


def test_creates_named_dense_and_sparse_vectors(
    client: QdrantClient, indexer: Indexer, sample_chunks: list[Chunk]
) -> None:
    """The collection has a cosine dense vector sized by the embedder and a sparse vector with the IDF modifier."""
    indexer.build(sample_chunks)
    collection = client.get_collection(COLLECTION_NAME)
    dense_params = collection.config.params.vectors[DENSE_VECTOR_NAME]
    sparse_params = collection.config.params.sparse_vectors[SPARSE_VECTOR_NAME]
    assert dense_params.size == FakeDenseEmbedder.dimension
    assert dense_params.distance == models.Distance.COSINE
    assert sparse_params.modifier == models.Modifier.IDF


def test_point_ids_are_chunk_sequence_numbers_with_payload(
    client: QdrantClient, indexer: Indexer, sample_chunks: list[Chunk]
) -> None:
    """Each chunk becomes one point whose ID is its seq and whose payload holds section_id and kind."""
    indexer.build(sample_chunks)
    points = client.retrieve(COLLECTION_NAME, ids=[1, 2, 3], with_payload=True)
    payloads = {point.id: point.payload for point in points}
    assert payloads == {
        1: {"section_id": "item:7", "kind": "text"},
        2: {"section_id": "item:1A", "kind": "risk_factor"},
        3: {"section_id": "item:7", "kind": "table"},
    }


def test_embeds_the_path_line_and_text(
    indexer: Indexer,
    dense_embedder: FakeDenseEmbedder,
    sparse_embedder: FakeSparseEmbedder,
    sample_chunks: list[Chunk],
) -> None:
    """Both embedders receive the embedding text (path line, then text), in chunk order."""
    indexer.build(sample_chunks)
    expected_texts = [embedding_text(chunk) for chunk in sample_chunks]
    dense_texts = [text for batch in dense_embedder.batches for text in batch]
    sparse_texts = [text for batch in sparse_embedder.batches for text in batch]
    assert dense_texts == expected_texts
    assert sparse_texts == expected_texts


def test_embeds_in_batches_of_64(
    indexer: Indexer, dense_embedder: FakeDenseEmbedder, sparse_embedder: FakeSparseEmbedder
) -> None:
    """130 chunks embed as batches of 64, 64 and 2."""
    chunks = [make_chunk(seq, f"chunk number {seq}") for seq in range(1, LARGE_BATCH_CHUNK_COUNT + 1)]
    indexer.build(chunks)
    dense_sizes = [len(batch) for batch in dense_embedder.batches]
    sparse_sizes = [len(batch) for batch in sparse_embedder.batches]
    assert dense_sizes == [EMBED_BATCH_SIZE, EMBED_BATCH_SIZE, 2]
    assert sparse_sizes == dense_sizes


def test_rebuild_replaces_the_previous_collection(
    client: QdrantClient, indexer: Indexer, sample_chunks: list[Chunk]
) -> None:
    """Building again recreates the collection, so no point from the old build survives."""
    indexer.build(sample_chunks)
    indexer.build(sample_chunks[:1])
    count = client.count(COLLECTION_NAME)
    assert count.count == 1


def test_dense_query_finds_the_matching_chunk(
    client: QdrantClient, indexer: Indexer, dense_embedder: FakeDenseEmbedder, sample_chunks: list[Chunk]
) -> None:
    """A dense query with a chunk's own embedding text returns that chunk first."""
    indexer.build(sample_chunks)
    target = sample_chunks[1]
    query_text = embedding_text(target)
    query_vector = dense_embedder.embed_query(query_text)
    response = client.query_points(COLLECTION_NAME, query=query_vector, using=DENSE_VECTOR_NAME, limit=1)
    assert response.points[0].id == target.seq


def test_exposes_the_model_names_for_the_manifest(indexer: Indexer) -> None:
    """The manifest records which models built the index."""
    assert indexer.dense_model == FakeDenseEmbedder.model_name
    assert indexer.sparse_model == FakeSparseEmbedder.model_name
