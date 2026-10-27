"""Unit tests for ChunkStore (LLD section 7): lookups by seq, section and position, with Item 8 covering its notes."""

from pathlib import Path

import pytest

from research_agent.ingestion.pipeline import write_chunks
from research_agent.models import Chunk
from research_agent.retrieval.store import ChunkStore
from retrieval_fakes import build_corpus

ITEM_8_SCOPE = ["item:8", "note:2", "note:3", "note:4", "note:7"]


@pytest.fixture
def store() -> ChunkStore:
    """Return a store over the twelve-chunk corpus."""
    return ChunkStore(build_corpus())


def unit_sequences(units: list[list[Chunk]]) -> list[list[int]]:
    """Render units as lists of their chunks' sequence numbers."""
    return [[chunk.seq for chunk in unit] for unit in units]


def test_loads_chunks_written_by_ingestion(tmp_path: Path) -> None:
    """A store loaded from an index folder holds exactly the chunks ingestion wrote."""
    corpus = build_corpus()
    write_chunks(corpus, tmp_path)
    store = ChunkStore.load(tmp_path)
    assert [store.get(chunk.seq) for chunk in corpus] == corpus


def test_get_returns_a_chunk_by_seq(store: ChunkStore) -> None:
    """Lookup by sequence number returns that chunk; an unknown one raises KeyError."""
    assert store.get(4).text.startswith("Changes in tax rates")
    with pytest.raises(KeyError):
        store.get(999)


def test_section_ids_in_document_order(store: ChunkStore) -> None:
    """Each section appears once, in the order the filing presents it."""
    assert store.section_ids() == ["item:1", "item:1A", "item:7", *ITEM_8_SCOPE]


def test_has_section(store: ChunkStore) -> None:
    """Known sections are recognized; unknown ones are not."""
    assert store.has_section("note:7")
    assert not store.has_section("item:99")


def test_item_8_scope_includes_its_notes(store: ChunkStore) -> None:
    """Searching Item 8 means its statements and every note."""
    assert store.section_scope("item:8") == ITEM_8_SCOPE


def test_other_scopes_are_just_the_section(store: ChunkStore) -> None:
    """A note or any other Item covers only itself."""
    assert store.section_scope("note:7") == ["note:7"]
    assert store.section_scope("item:1A") == ["item:1A"]


def test_first_units_in_position_order(store: ChunkStore) -> None:
    """The first k units of a section, by position, include every kind."""
    units = store.first_units("item:1A", 2)
    assert unit_sequences(units) == [[2], [3]]


def test_first_units_of_one_kind_keep_all_parts(store: ChunkStore) -> None:
    """Filtering to risk factors skips the intro, and a split risk factor comes back with both parts."""
    units = store.first_units("item:1A", 2, kind="risk_factor")
    assert unit_sequences(units) == [[3], [4, 5]]


def test_first_units_of_item_8_walk_statements_and_notes(store: ChunkStore) -> None:
    """Position order over Item 8 follows the document through the statements and into the notes."""
    units = store.first_units("item:8", 3)
    assert unit_sequences(units) == [[8], [9], [10]]


def test_first_units_never_returns_more_than_exist(store: ChunkStore) -> None:
    """Asking for more units than a section has returns all of them."""
    units = store.first_units("item:7", 10)
    assert unit_sequences(units) == [[6], [7]]
