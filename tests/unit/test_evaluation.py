"""Unit tests for the retrieval eval (LLD section 12): loading the set, hit@k, not-found accuracy, the set itself."""

import json
from pathlib import Path

import pytest

from filing_support import PAGE_FOOTER_PATTERN, PROJECT_ROOT, REAL_FILING_PATH, read_filing
from research_agent.ingestion.parser import parse_filing
from research_agent.retrieval.evaluation import EvalCase, evaluate, load_eval_set
from research_agent.retrieval.search import Searcher
from retrieval_fakes import build_searcher

EVAL_SET_PATH = PROJECT_ROOT / "eval" / "retrieval_set.jsonl"
MIN_ON_TOPIC_CASES = 15
MIN_OFF_TOPIC_CASES = 3

FAKE_CASES = [
    EvalCase(question="tax rates", expected_sections=["item:1A"]),
    EvalCase(question="revenue", expected_sections=["item:8", "note:2"]),
    EvalCase(question="iphone", expected_sections=["item:7"]),
    EvalCase(question="weather forecast", expected_sections=[]),
    EvalCase(question="tax", expected_sections=[]),
]


@pytest.fixture
def searcher() -> Searcher:
    """Return a searcher over the indexed fake corpus."""
    return build_searcher()


def test_loads_cases_from_jsonl(tmp_path: Path) -> None:
    """Each line is one case; an empty expected list marks an off-topic question."""
    eval_file = tmp_path / "set.jsonl"
    lines = [
        json.dumps({"question": case.question, "expected_sections": case.expected_sections}) for case in FAKE_CASES
    ]
    eval_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cases = load_eval_set(eval_file)
    assert cases == FAKE_CASES
    assert [case.is_off_topic for case in cases] == [False, False, False, True, True]


def test_scores_hits_and_not_found_accuracy(searcher: Searcher) -> None:
    """Two of three on-topic cases hit at k=1; one of two off-topic cases correctly returns not found."""
    report = evaluate(searcher, FAKE_CASES, k=1)
    assert report.hit_at_k == pytest.approx(2 / 3)
    assert report.not_found_accuracy == pytest.approx(1 / 2)
    assert [result.passed for result in report.results] == [True, True, False, True, False]


def test_reports_what_each_case_returned(searcher: Searcher) -> None:
    """Per-case results show the sections returned and the best dense score, for diagnosing and calibrating."""
    report = evaluate(searcher, FAKE_CASES, k=1)
    tax_result, _, iphone_result, weather_result, _ = report.results
    assert tax_result.returned_sections == ["item:1A"]
    assert iphone_result.returned_sections == ["item:1"]
    assert weather_result.returned_sections == []
    assert tax_result.best_dense_score == pytest.approx(1.0)
    assert weather_result.best_dense_score == pytest.approx(0.0)


def test_hit_counts_only_the_top_k_ranked_results(searcher: Searcher) -> None:
    """Cross-referenced passages added after the ranked results don't count toward hit@k."""
    case = EvalCase(question="tax rates", expected_sections=["note:7"])
    report = evaluate(searcher, [case], k=1)
    assert report.results[0].returned_sections == ["item:1A"]
    assert not report.results[0].passed


@pytest.fixture(scope="module")
def cases() -> list[EvalCase]:
    """Load eval/retrieval_set.jsonl."""
    return load_eval_set(EVAL_SET_PATH)


class TestEvalSet:
    """The committed eval set is usable."""

    def test_has_enough_on_and_off_topic_questions(self, cases: list[EvalCase]) -> None:
        """About 15 on-topic questions and at least 3 off-topic ones, with no duplicates."""
        on_topic = [case for case in cases if not case.is_off_topic]
        off_topic = [case for case in cases if case.is_off_topic]
        questions = [case.question for case in cases]
        assert len(on_topic) >= MIN_ON_TOPIC_CASES
        assert len(off_topic) >= MIN_OFF_TOPIC_CASES
        assert len(questions) == len(set(questions))

    @pytest.mark.skipif(not REAL_FILING_PATH.exists(), reason=f"{REAL_FILING_PATH} not downloaded")
    def test_every_expected_section_exists_in_the_filing(self, cases: list[EvalCase]) -> None:
        """A typo in an expected section would silently count as a miss, so each must be a real section."""
        html = read_filing(REAL_FILING_PATH)
        blocks = parse_filing(html, PAGE_FOOTER_PATTERN)
        filing_sections = {block.section_id for block in blocks}
        expected_sections = {section for case in cases for section in case.expected_sections}
        assert expected_sections <= filing_sections
