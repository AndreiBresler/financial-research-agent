"""Retrieval eval (LLD section 12): hit@k for on-topic questions and not-found accuracy for off-topic ones.

Re-run after any parsing, chunking or embedding change; it is also how min_dense_score is calibrated.
"""

from pathlib import Path

from pydantic import BaseModel

from research_agent.config import TEXT_ENCODING
from research_agent.retrieval.search import NotFound, Searcher

DEFAULT_EVAL_K = 5
NO_CASES_SCORE = 0.0


class EvalCase(BaseModel):
    """A question and the sections that answer it; none means the 10-K doesn't cover it."""

    question: str
    expected_sections: list[str]

    @property
    def is_off_topic(self) -> bool:
        """Tell whether the search should return not found."""
        return not self.expected_sections


class CaseResult(BaseModel):
    """How one case went, with what's needed to diagnose a miss or calibrate the threshold."""

    question: str
    expected_sections: list[str]
    returned_sections: list[str]
    best_dense_score: float
    passed: bool


class EvalReport(BaseModel):
    """Scores over the whole eval set."""

    hit_at_k: float
    not_found_accuracy: float
    results: list[CaseResult]


def load_eval_set(path: Path) -> list[EvalCase]:
    """Read one JSON case per line."""
    content = path.read_text(encoding=TEXT_ENCODING)
    return [EvalCase.model_validate_json(line) for line in content.splitlines() if line.strip()]


def run_case(searcher: Searcher, case: EvalCase, k: int) -> CaseResult:
    """Search the whole filing for one question and judge the top k ranked passages."""
    result = searcher.search(case.question, None, k)
    best_dense_score = searcher.best_dense_score(case.question, None)
    if isinstance(result, NotFound):
        returned_sections: list[str] = []
    else:
        # Cross-referenced passages come after the k ranked ones and don't count toward hit@k.
        ranked = result[:k]
        returned_sections = list(dict.fromkeys(chunk.section_id for chunk in ranked))
    if case.is_off_topic:
        passed = isinstance(result, NotFound)
    else:
        passed = any(section in case.expected_sections for section in returned_sections)
    return CaseResult(
        question=case.question,
        expected_sections=case.expected_sections,
        returned_sections=returned_sections,
        best_dense_score=best_dense_score,
        passed=passed,
    )


def pass_rate(results: list[CaseResult]) -> float:
    """Return the share of results that passed, or 0 when there are none."""
    if not results:
        return NO_CASES_SCORE
    passed_count = sum(1 for result in results if result.passed)
    return passed_count / len(results)


def evaluate(searcher: Searcher, cases: list[EvalCase], k: int = DEFAULT_EVAL_K) -> EvalReport:
    """Run every case and score on-topic hits and off-topic rejections separately."""
    results = [run_case(searcher, case, k) for case in cases]
    on_topic = [result for result in results if result.expected_sections]
    off_topic = [result for result in results if not result.expected_sections]
    return EvalReport(hit_at_k=pass_rate(on_topic), not_found_accuracy=pass_rate(off_topic), results=results)
