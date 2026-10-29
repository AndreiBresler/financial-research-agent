"""Unit tests for hybrid search (LLD section 7): relevance gate, section scope, RRF fusion and one-hop cross-references.

The corpus is indexed in an in-memory Qdrant with a topic-keyword embedder, so every dense score is known.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from research_agent.models import Chunk
from research_agent.retrieval.search import NotFound, Searcher
from retrieval_fakes import build_searcher

CONCURRENT_SEARCHES = 8


@pytest.fixture
def plain_searcher() -> Searcher:
    """Return a searcher that adds no cross-referenced chunks, to test retrieval alone."""
    return build_searcher(xref_max_extra=0)


@pytest.fixture
def searcher() -> Searcher:
    """Return a searcher that adds up to 3 cross-referenced chunks."""
    return build_searcher(xref_max_extra=3)


def found(result: list[Chunk] | NotFound) -> list[Chunk]:
    """Assert a search found passages and return them."""
    assert isinstance(result, list), f"expected passages, got {result}"
    return result


def sequence_numbers(result: list[Chunk] | NotFound) -> list[int]:
    """Return the sequence numbers of a successful search, in rank order."""
    chunks = found(result)
    return [chunk.seq for chunk in chunks]


class TestRelevanceGate:
    """'Not found' is decided on the best raw dense score, before fusion."""

    def test_unrelated_query_is_not_found(self, plain_searcher: Searcher) -> None:
        """A query matching nothing in the filing returns NotFound with no section."""
        result = plain_searcher.search("weather forecast", None, 3)
        assert result == NotFound(section=None)

    def test_unrelated_within_a_section_names_the_section(self, plain_searcher: Searcher) -> None:
        """Tax content exists, but not in Item 1, so the miss names the section that was searched."""
        result = plain_searcher.search("tax rates", "item:1", 3)
        assert result == NotFound(section="item:1")

    def test_best_dense_score_is_exposed_for_calibration(self, plain_searcher: Searcher) -> None:
        """The eval reads the best raw dense score to calibrate the threshold."""
        assert plain_searcher.best_dense_score("tax", None) == pytest.approx(1.0)
        assert plain_searcher.best_dense_score("weather forecast", None) == pytest.approx(0.0)
        assert plain_searcher.best_dense_score("tax", "item:1") == pytest.approx(0.0)


class TestScopeAndRanking:
    """Section filters, the Item 8 scope, k, and fusion order."""

    def test_section_filter_keeps_results_inside_the_section(self, plain_searcher: Searcher) -> None:
        """Every result of an Item 1A search comes from Item 1A."""
        chunks = found(plain_searcher.search("tax rates", "item:1A", 3))
        assert {chunk.section_id for chunk in chunks} == {"item:1A"}

    def test_item_8_search_reaches_its_notes(self, plain_searcher: Searcher) -> None:
        """Revenue lives in both the statements and Note 2; an Item 8 search finds both."""
        chunks = found(plain_searcher.search("revenue", "item:8", 3))
        sections = {chunk.section_id for chunk in chunks}
        assert {8, 9} <= {chunk.seq for chunk in chunks}
        assert sections <= {"item:8", "note:2", "note:3", "note:4", "note:7"}

    def test_note_filter_covers_only_that_note(self, plain_searcher: Searcher) -> None:
        """A note filter doesn't widen to the rest of Item 8."""
        assert sequence_numbers(plain_searcher.search("tax", "note:7", 3)) == [12]

    def test_returns_at_most_k_results(self, plain_searcher: Searcher) -> None:
        """k caps the fused results."""
        chunks = found(plain_searcher.search("tax", None, 2))
        assert len(chunks) == 2

    def test_dense_and_sparse_agreement_ranks_first(self, plain_searcher: Searcher) -> None:
        """The passage both retrievers rank first comes first after fusion."""
        assert sequence_numbers(plain_searcher.search("services margin", "item:7", 2))[0] == 6

    def test_exact_terms_lift_a_passage_within_a_topic(self, plain_searcher: Searcher) -> None:
        """Of two tax risk passages, the one that also says 'rates' ranks first."""
        assert sequence_numbers(plain_searcher.search("tax rates", "item:1A", 2)) == [4, 5]


class TestCrossReferences:
    """Referenced sections add their best passage, one hop only, up to the cap."""

    def test_adds_the_best_passage_of_each_referenced_section(self, searcher: Searcher) -> None:
        """The tax risk refers to Notes 7 and 3; each adds its best match, after the ranked results."""
        assert sequence_numbers(searcher.search("tax rates", "item:1A", 1)) == [4, 12, 10]

    def test_added_passages_are_not_expanded_again(self, searcher: Searcher) -> None:
        """Note 7 refers to Note 4, but added passages don't expand, so Note 4 stays out."""
        result = sequence_numbers(searcher.search("tax rates", "item:1A", 1))
        assert 11 not in result

    def test_stops_at_the_cap(self) -> None:
        """With a cap of one, only the first referenced section is added."""
        capped_searcher = build_searcher(xref_max_extra=1)
        assert sequence_numbers(capped_searcher.search("tax rates", "item:1A", 1)) == [4, 12]

    def test_skips_a_referenced_section_without_relevant_content(self, searcher: Searcher) -> None:
        """The gross margin passage refers to Item 1, which has nothing about margin, so nothing is added."""
        assert sequence_numbers(searcher.search("services margin", "item:7", 1)) == [6]

    def test_never_adds_a_passage_twice(self, searcher: Searcher) -> None:
        """Results stay unique even when a referenced passage is already ranked."""
        result = sequence_numbers(searcher.search("tax", None, 5))
        assert len(result) == len(set(result))


class TestKindFilter:
    """A kind filter narrows results to tables, risk factors or narrative text."""

    def test_returns_only_the_requested_kind(self, plain_searcher: Searcher) -> None:
        """A table search over the whole filing returns tables only, led by the revenue table."""
        chunks = found(plain_searcher.search("revenue", None, 3, kind="table"))
        assert {chunk.kind for chunk in chunks} == {"table"}
        assert chunks[0].seq == 8

    def test_combines_with_the_section_filter(self, plain_searcher: Searcher) -> None:
        """Section and kind filters apply together: text in Item 8 skips the revenue table for Note 2."""
        assert sequence_numbers(plain_searcher.search("revenue", "item:8", 1, kind="text")) == [9]

    def test_gate_applies_within_the_kind(self, plain_searcher: Searcher) -> None:
        """Tax content exists, but no tax table, so a table search misses and names the kind."""
        result = plain_searcher.search("tax", None, 3, kind="table")
        assert result == NotFound(section=None, kind="table")
        assert plain_searcher.best_dense_score("tax", None, kind="table") == pytest.approx(0.0)

    def test_cross_references_keep_the_kind(self, searcher: Searcher) -> None:
        """The tax risk refers to two notes, but they hold text, so a risk-factor search adds nothing."""
        assert sequence_numbers(searcher.search("tax rates", "item:1A", 1, kind="risk_factor")) == [4]


def test_concurrent_searches_share_the_index_safely(plain_searcher: Searcher) -> None:
    """Searches from several worker threads, as concurrent tool calls make, all return the same result."""
    with ThreadPoolExecutor(max_workers=CONCURRENT_SEARCHES) as executor:
        futures = [
            executor.submit(plain_searcher.search, "tax rates", "item:1A", 2) for _ in range(CONCURRENT_SEARCHES)
        ]
        results = [sequence_numbers(future.result()) for future in futures]
    assert results == [[4, 5]] * CONCURRENT_SEARCHES
