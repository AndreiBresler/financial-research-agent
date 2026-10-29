"""Unit tests for the ingestion pipeline: parse, chunk, index, then write chunks.jsonl and manifest.json last."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from filing_support import MINI_FILING_PATH, PAGE_FOOTER_PATTERN, read_filing
from ingestion_fakes import FakeDenseEmbedder, FakeSparseEmbedder, count_words
from research_agent.ingestion.chunker import build_chunks
from research_agent.ingestion.indexer import COLLECTION_NAME, Indexer
from research_agent.ingestion.manifest import MANIFEST_FILE_NAME, read_manifest, write_manifest
from research_agent.ingestion.parser import PARSER_VERSION, parse_filing
from research_agent.ingestion.pipeline import CHUNKS_FILE_NAME, read_chunks, run_ingestion
from research_agent.models import Chunk, Manifest

CHUNK_MAX_TOKENS = 400
FIXTURE_CHUNK_COUNT = 24
BUILT_AT = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


class FailingIndexer:
    """An indexer whose build always fails, as a crash mid-ingestion would."""

    dense_model = "fake/dense-letters"
    sparse_model = "fake/sparse-words"

    def build(self, chunks: list[Chunk]) -> None:
        """Fail instead of indexing."""
        raise RuntimeError("embedding crashed")


def fixed_clock() -> datetime:
    """Return a fixed build time."""
    return BUILT_AT


@pytest.fixture
def client() -> QdrantClient:
    """Return a fresh in-memory Qdrant."""
    return QdrantClient(":memory:")


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    """Return an index folder that doesn't exist yet."""
    return tmp_path / "index"


@pytest.fixture
def manifest(client: QdrantClient, index_dir: Path) -> Manifest:
    """Run the pipeline on the synthetic filing with fakes and return its manifest."""
    indexer = Indexer(client, FakeDenseEmbedder(), FakeSparseEmbedder())
    return run_ingestion(
        source_path=MINI_FILING_PATH,
        index_dir=index_dir,
        page_footer_pattern=PAGE_FOOTER_PATTERN,
        chunk_max_tokens=CHUNK_MAX_TOKENS,
        indexer=indexer,
        count_tokens=count_words,
        now=fixed_clock,
    )


def test_writes_chunks_matching_the_chunker(manifest: Manifest, index_dir: Path) -> None:
    """chunks.jsonl holds exactly what the chunker produces for the filing, and reads back as Chunk models."""
    html = read_filing(MINI_FILING_PATH)
    blocks = parse_filing(html, PAGE_FOOTER_PATTERN)
    expected_chunks = build_chunks(blocks, count_words, CHUNK_MAX_TOKENS)
    stored_chunks = read_chunks(index_dir)
    lines = (index_dir / CHUNKS_FILE_NAME).read_text(encoding="utf-8").splitlines()
    assert stored_chunks == expected_chunks
    assert len(lines) == FIXTURE_CHUNK_COUNT


def test_manifest_records_what_built_the_index(manifest: Manifest, index_dir: Path) -> None:
    """The manifest names the document hash, parser version, models, chunk count and build time."""
    source_bytes = MINI_FILING_PATH.read_bytes()
    assert manifest.doc_sha256 == hashlib.sha256(source_bytes).hexdigest()
    assert manifest.parser_version == PARSER_VERSION
    assert manifest.dense_model == FakeDenseEmbedder.model_name
    assert manifest.sparse_model == FakeSparseEmbedder.model_name
    assert manifest.chunk_count == FIXTURE_CHUNK_COUNT
    assert manifest.built_at == BUILT_AT
    assert read_manifest(index_dir) == manifest


def test_indexes_every_chunk(manifest: Manifest, client: QdrantClient) -> None:
    """The vector index holds one point per chunk."""
    count = client.count(COLLECTION_NAME)
    assert count.count == manifest.chunk_count


def test_failed_build_leaves_no_manifest(tmp_path: Path) -> None:
    """A crash mid-build removes any earlier manifest and writes none, so the agent refuses to start."""
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    old_manifest = Manifest(
        doc_sha256="old",
        parser_version="0",
        dense_model="old/dense",
        sparse_model="old/sparse",
        chunk_count=1,
        built_at=BUILT_AT,
    )
    write_manifest(old_manifest, index_dir)
    with pytest.raises(RuntimeError):
        run_ingestion(
            source_path=MINI_FILING_PATH,
            index_dir=index_dir,
            page_footer_pattern=PAGE_FOOTER_PATTERN,
            chunk_max_tokens=CHUNK_MAX_TOKENS,
            indexer=FailingIndexer(),
            count_tokens=count_words,
            now=fixed_clock,
        )
    assert not (index_dir / MANIFEST_FILE_NAME).exists()
