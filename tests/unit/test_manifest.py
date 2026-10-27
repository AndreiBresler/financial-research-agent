"""Unit tests for the index manifest: hashing, persistence and the stale-index check (LLD sections 5, 6, 10)."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research_agent.ingestion.manifest import (
    MANIFEST_FILE_NAME,
    IndexIdentity,
    document_sha256,
    read_manifest,
    remove_manifest,
    stale_reasons,
    write_manifest,
)
from research_agent.models import Manifest

SOURCE_BYTES = b"<html><body>synthetic filing</body></html>"
BUILT_AT = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def identity() -> IndexIdentity:
    """Return the identity the configuration expects."""
    return IndexIdentity(
        doc_sha256=document_sha256(SOURCE_BYTES),
        parser_version="1",
        dense_model="BAAI/bge-small-en-v1.5",
        sparse_model="Qdrant/bm25",
    )


@pytest.fixture
def manifest(identity: IndexIdentity) -> Manifest:
    """Return a manifest built with the expected identity."""
    return Manifest(
        doc_sha256=identity.doc_sha256,
        parser_version=identity.parser_version,
        dense_model=identity.dense_model,
        sparse_model=identity.sparse_model,
        chunk_count=23,
        built_at=BUILT_AT,
    )


def test_document_hash_is_the_sha256_of_the_source_bytes() -> None:
    """The hash identifies the exact filing that was indexed."""
    expected = hashlib.sha256(SOURCE_BYTES).hexdigest()
    assert document_sha256(SOURCE_BYTES) == expected


def test_write_then_read_round_trips(tmp_path: Path, manifest: Manifest) -> None:
    """A written manifest reads back equal, from manifest.json in the index folder."""
    write_manifest(manifest, tmp_path)
    assert (tmp_path / MANIFEST_FILE_NAME).exists()
    assert read_manifest(tmp_path) == manifest


def test_missing_manifest_reads_as_none(tmp_path: Path) -> None:
    """No manifest means no usable index."""
    assert read_manifest(tmp_path) is None


def test_corrupt_manifest_reads_as_none(tmp_path: Path) -> None:
    """A half-written or hand-edited manifest is treated like a missing one."""
    manifest_path = tmp_path / MANIFEST_FILE_NAME
    manifest_path.write_text("{not json", encoding="utf-8")
    assert read_manifest(tmp_path) is None


def test_remove_manifest_is_safe_when_absent(tmp_path: Path, manifest: Manifest) -> None:
    """Removing deletes an existing manifest and does nothing when there is none."""
    write_manifest(manifest, tmp_path)
    remove_manifest(tmp_path)
    remove_manifest(tmp_path)
    assert read_manifest(tmp_path) is None


def test_current_index_has_no_stale_reasons(manifest: Manifest, identity: IndexIdentity) -> None:
    """A manifest matching the expected identity is current."""
    assert stale_reasons(manifest, identity) == []


def test_missing_index_is_stale(identity: IndexIdentity) -> None:
    """No manifest yields a reason, so the CLI refuses to start."""
    reasons = stale_reasons(None, identity)
    assert len(reasons) == 1


@pytest.mark.parametrize("field_name", ["doc_sha256", "parser_version", "dense_model", "sparse_model"])
def test_each_identity_field_is_checked(manifest: Manifest, identity: IndexIdentity, field_name: str) -> None:
    """A different document, parser version or model each makes the index stale, naming the field."""
    changed_manifest = manifest.model_copy(update={field_name: "something else"})
    reasons = stale_reasons(changed_manifest, identity)
    assert len(reasons) == 1
    assert field_name in reasons[0]


def test_every_mismatch_is_reported(manifest: Manifest, identity: IndexIdentity) -> None:
    """Several mismatches give several reasons."""
    changed_manifest = manifest.model_copy(update={"parser_version": "0", "dense_model": "other/model"})
    reasons = stale_reasons(changed_manifest, identity)
    assert len(reasons) == 2
