"""Smoke test for the composition root, src/main.py: it refuses to start before the index exists.

The rest of main.py is wiring, exercised by the end-to-end tests; this checks the startup gate without loading
models or calling an API.
"""

from pathlib import Path

import pytest

import main as main_script
from research_agent.cli import INDEX_NOT_READY_EXIT_CODE, INGEST_COMMAND
from research_agent.ingestion.manifest import MISSING_INDEX_REASON


def test_missing_index_exits_with_code_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without an index, main prints why and the ingest command, and exits 2 before loading anything."""
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("LOG_PATH", str(tmp_path / "logs" / "agent.jsonl"))
    exit_code = main_script.main(["What is Apple's gross margin?"])
    output = capsys.readouterr().out
    assert exit_code == INDEX_NOT_READY_EXIT_CODE
    assert MISSING_INDEX_REASON in output
    assert INGEST_COMMAND in output
