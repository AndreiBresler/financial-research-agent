"""Opt-in tests with the real FastEmbed models and tokenizer (about 80 MB, downloaded on first run).

Run with: pytest -m embedding_models
"""

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from filing_support import PAGE_FOOTER_PATTERN, REAL_FILING_PATH
from research_agent.ingestion.chunker import embedding_text
from research_agent.ingestion.embeddings import EmbeddingTokenCounter, FastEmbedDense, FastEmbedSparse
from research_agent.ingestion.indexer import COLLECTION_NAME, DENSE_VECTOR_NAME, Indexer
from research_agent.ingestion.pipeline import read_chunks, run_ingestion
from research_agent.models import Chunk, Manifest

pytestmark = pytest.mark.embedding_models

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
DENSE_DIMENSION = 384
CHUNK_MAX_TOKENS = 400
MODEL_TOKEN_LIMIT = 512
REAL_RISK_FACTOR_COUNT = 27
SEARCH_DEPTH = 5


@pytest.fixture(scope="module")
def dense_embedder() -> FastEmbedDense:
    """Load the dense model once for the module."""
    return FastEmbedDense(DENSE_MODEL)


@pytest.fixture(scope="module")
def sparse_embedder() -> FastEmbedSparse:
    """Load the sparse model once for the module."""
    return FastEmbedSparse(SPARSE_MODEL)


@pytest.fixture(scope="module")
def token_counter() -> EmbeddingTokenCounter:
    """Load the dense model's tokenizer once for the module."""
    return EmbeddingTokenCounter(DENSE_MODEL)


def test_dense_model_produces_384_dimensional_vectors(dense_embedder: FastEmbedDense) -> None:
    """bge-small embeds passages and queries as 384 floats and reports its name and dimension."""
    vectors = dense_embedder.embed_documents(["Gross margin was 46.9 percent.", "Risk factors"])
    query_vector = dense_embedder.embed_query("What was the gross margin?")
    assert dense_embedder.model_name == DENSE_MODEL
    assert dense_embedder.dimension == DENSE_DIMENSION
    assert [len(vector) for vector in vectors] == [DENSE_DIMENSION, DENSE_DIMENSION]
    assert len(query_vector) == DENSE_DIMENSION


def test_sparse_model_produces_bm25_vectors(sparse_embedder: FastEmbedSparse) -> None:
    """BM25 returns sparse vectors with matching index and value lists."""
    vectors = sparse_embedder.embed_documents(["Gross margin was 46.9 percent."])
    assert sparse_embedder.model_name == SPARSE_MODEL
    assert vectors[0].indices
    assert len(vectors[0].indices) == len(vectors[0].values)


def test_token_counter_counts_model_tokens(token_counter: EmbeddingTokenCounter) -> None:
    """Counts grow with text length and differ from a plain word count."""
    short_count = token_counter("Gross margin")
    long_count = token_counter("Gross margin pressure from component costs and foreign exchange rates.")
    assert 0 < short_count < long_count


@pytest.fixture(scope="module")
def ingested(
    tmp_path_factory: pytest.TempPathFactory,
    dense_embedder: FastEmbedDense,
    sparse_embedder: FastEmbedSparse,
    token_counter: EmbeddingTokenCounter,
) -> tuple[Manifest, list[Chunk], QdrantClient]:
    """Ingest the real filing once and return the manifest, chunks and Qdrant client."""
    index_dir: Path = tmp_path_factory.mktemp("index")
    client = QdrantClient(path=str(index_dir / "qdrant"))
    indexer = Indexer(client, dense_embedder, sparse_embedder)
    manifest = run_ingestion(
        source_path=REAL_FILING_PATH,
        index_dir=index_dir,
        page_footer_pattern=PAGE_FOOTER_PATTERN,
        chunk_max_tokens=CHUNK_MAX_TOKENS,
        indexer=indexer,
        count_tokens=token_counter,
    )
    chunks = read_chunks(index_dir)
    return manifest, chunks, client


@pytest.mark.skipif(not REAL_FILING_PATH.exists(), reason=f"{REAL_FILING_PATH} not downloaded")
class TestRealIngestion:
    """The whole pipeline on the real filing with the real models, into an on-disk Qdrant."""

    def test_every_chunk_fits_the_token_limit(
        self, ingested: tuple[Manifest, list[Chunk], QdrantClient], token_counter: EmbeddingTokenCounter
    ) -> None:
        """No embedded text exceeds 400 model tokens, safely under the model's 512."""
        _, chunks, _ = ingested
        token_counts = [token_counter(embedding_text(chunk)) for chunk in chunks]
        assert max(token_counts) <= CHUNK_MAX_TOKENS < MODEL_TOKEN_LIMIT

    def test_manifest_and_index_agree(self, ingested: tuple[Manifest, list[Chunk], QdrantClient]) -> None:
        """The manifest names the real models and its chunk count matches both files."""
        manifest, chunks, client = ingested
        count = client.count(COLLECTION_NAME)
        risk_units = {chunk.unit for chunk in chunks if chunk.kind == "risk_factor"}
        assert (manifest.dense_model, manifest.sparse_model) == (DENSE_MODEL, SPARSE_MODEL)
        assert manifest.chunk_count == len(chunks) == count.count
        assert len(risk_units) == REAL_RISK_FACTOR_COUNT

    def test_dense_search_finds_the_gross_margin_table(
        self, ingested: tuple[Manifest, list[Chunk], QdrantClient], dense_embedder: FastEmbedDense
    ) -> None:
        """A plain-language question retrieves the table behind required query 2 in the top 5."""
        _, chunks, client = ingested
        chunks_by_seq = {chunk.seq: chunk for chunk in chunks}
        query_vector = dense_embedder.embed_query("What was Apple's total gross margin percentage?")
        response = client.query_points(COLLECTION_NAME, query=query_vector, using=DENSE_VECTOR_NAME, limit=SEARCH_DEPTH)
        top_texts = [chunks_by_seq[int(point.id)].text for point in response.points]
        assert any("46.9%" in text for text in top_texts)
