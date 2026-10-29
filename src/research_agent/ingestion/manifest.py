"""Index manifest: what built the index, and whether it still matches the configuration (LLD sections 5, 6, 10)."""

import hashlib
import os
from pathlib import Path

from pydantic import BaseModel, ValidationError

from research_agent.config import TEXT_ENCODING
from research_agent.models import Manifest

MANIFEST_FILE_NAME = "manifest.json"
TEMPORARY_SUFFIX = ".tmp"
JSON_INDENT = 2
MISSING_INDEX_REASON = "the index has not been built"


class IndexIdentity(BaseModel):
    """The manifest fields that must match the configuration for an index to be usable."""

    doc_sha256: str
    parser_version: str
    dense_model: str
    sparse_model: str


def document_sha256(source_bytes: bytes) -> str:
    """Return the hex SHA-256 of the filing's bytes."""
    digest = hashlib.sha256(source_bytes)
    return digest.hexdigest()


def manifest_path(index_dir: Path) -> Path:
    """Return where the manifest lives in an index folder."""
    return index_dir / MANIFEST_FILE_NAME


def write_manifest(manifest: Manifest, index_dir: Path) -> None:
    """Write the manifest atomically, so a crash never leaves a partial file."""
    index_dir.mkdir(parents=True, exist_ok=True)
    final_path = manifest_path(index_dir)
    temporary_path = final_path.with_suffix(TEMPORARY_SUFFIX)
    manifest_json = manifest.model_dump_json(indent=JSON_INDENT)
    temporary_path.write_text(manifest_json, encoding=TEXT_ENCODING)
    os.replace(temporary_path, final_path)


def read_manifest(index_dir: Path) -> Manifest | None:
    """Return the index's manifest, or None when it is missing or unreadable."""
    path = manifest_path(index_dir)
    if not path.exists():
        return None
    manifest_json = path.read_text(encoding=TEXT_ENCODING)
    try:
        return Manifest.model_validate_json(manifest_json)
    except ValidationError:
        return None


def remove_manifest(index_dir: Path) -> None:
    """Delete the manifest if there is one, marking the index as not ready."""
    path = manifest_path(index_dir)
    path.unlink(missing_ok=True)


def stale_reasons(manifest: Manifest | None, expected: IndexIdentity) -> list[str]:
    """Explain why an index can't be used; an empty list means it is current."""
    if manifest is None:
        return [MISSING_INDEX_REASON]
    reasons: list[str] = []
    for field_name in IndexIdentity.model_fields:
        actual_value = getattr(manifest, field_name)
        expected_value = getattr(expected, field_name)
        if actual_value != expected_value:
            reasons.append(f"{field_name} is {actual_value!r}, expected {expected_value!r}")
    return reasons
