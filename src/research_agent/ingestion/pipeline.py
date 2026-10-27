"""Ingestion pipeline: parse, chunk and index the filing, then write chunks.jsonl and, last, manifest.json."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import structlog

from research_agent.ingestion.chunker import TokenCounter, build_chunks
from research_agent.ingestion.manifest import document_sha256, remove_manifest, write_manifest
from research_agent.ingestion.parser import PARSER_VERSION, parse_filing
from research_agent.models import Chunk, Manifest

CHUNKS_FILE_NAME = "chunks.jsonl"
QDRANT_DIRECTORY_NAME = "qdrant"
FILE_ENCODING = "utf-8"
LINE_SEPARATOR = "\n"

logger = structlog.get_logger(__name__)


class ChunkIndexer(Protocol):
    """Builds the vector index from chunks and names the models it used."""

    @property
    def dense_model(self) -> str:
        """Return the dense model's name."""
        ...

    @property
    def sparse_model(self) -> str:
        """Return the sparse model's name."""
        ...

    def build(self, chunks: list[Chunk]) -> None:
        """Replace the index with these chunks."""
        ...


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


def write_chunks(chunks: list[Chunk], index_dir: Path) -> None:
    """Write one JSON chunk per line to chunks.jsonl."""
    lines = [chunk.model_dump_json() for chunk in chunks]
    content = LINE_SEPARATOR.join(lines) + LINE_SEPARATOR
    chunks_path = index_dir / CHUNKS_FILE_NAME
    chunks_path.write_text(content, encoding=FILE_ENCODING)


def read_chunks(index_dir: Path) -> list[Chunk]:
    """Read the chunks written by the last ingestion."""
    chunks_path = index_dir / CHUNKS_FILE_NAME
    content = chunks_path.read_text(encoding=FILE_ENCODING)
    return [Chunk.model_validate_json(line) for line in content.splitlines() if line]


def run_ingestion(
    source_path: Path,
    index_dir: Path,
    page_footer_pattern: str,
    chunk_max_tokens: int,
    indexer: ChunkIndexer,
    count_tokens: TokenCounter,
    now: Callable[[], datetime] = utc_now,
) -> Manifest:
    """Rebuild the index from the filing; the manifest is removed first and written last, so a crash leaves none."""
    index_dir.mkdir(parents=True, exist_ok=True)
    remove_manifest(index_dir)
    source_bytes = source_path.read_bytes()
    html = source_bytes.decode(FILE_ENCODING)
    blocks = parse_filing(html, page_footer_pattern)
    chunks = build_chunks(blocks, count_tokens, chunk_max_tokens)
    logger.info("chunked filing", source=str(source_path), blocks=len(blocks), chunks=len(chunks))
    indexer.build(chunks)
    write_chunks(chunks, index_dir)
    manifest = Manifest(
        doc_sha256=document_sha256(source_bytes),
        parser_version=PARSER_VERSION,
        dense_model=indexer.dense_model,
        sparse_model=indexer.sparse_model,
        chunk_count=len(chunks),
        built_at=now(),
    )
    write_manifest(manifest, index_dir)
    logger.info("index built", index_dir=str(index_dir), chunks=manifest.chunk_count)
    return manifest
