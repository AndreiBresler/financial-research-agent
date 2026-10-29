"""Run the retrieval eval against the built index: python src/evaluate.py

Wiring only: loads Settings, the index and the models, runs eval/retrieval_set.jsonl, and logs per-case results,
hit@5, not-found accuracy, and the score gap used to calibrate min_dense_score. No API keys are needed.
"""

from contextlib import closing
from pathlib import Path

import structlog

from research_agent.config import Settings
from research_agent.ingestion.embeddings import FastEmbedDense, FastEmbedSparse
from research_agent.ingestion.indexer import open_qdrant
from research_agent.retrieval.evaluation import DEFAULT_EVAL_K, evaluate, load_eval_set
from research_agent.retrieval.index import Index
from research_agent.retrieval.search import Searcher
from research_agent.retrieval.store import ChunkStore

EVAL_SET_PATH = Path("eval/retrieval_set.jsonl")
SCORE_DECIMALS = 3

logger = structlog.get_logger(__name__)


def main() -> None:
    """Evaluate retrieval on the committed eval set and log the results."""
    settings = Settings()
    with closing(open_qdrant(settings.index_dir)) as client:
        dense_embedder = FastEmbedDense(settings.dense_model)
        sparse_embedder = FastEmbedSparse(settings.sparse_model)
        index = Index(client, dense_embedder, sparse_embedder)
        store = ChunkStore.load(settings.index_dir)
        searcher = Searcher(store, index, settings)
        cases = load_eval_set(EVAL_SET_PATH)
        report = evaluate(searcher, cases, k=DEFAULT_EVAL_K)
    for result in report.results:
        logger.info(
            "case",
            passed=result.passed,
            best_dense_score=round(result.best_dense_score, SCORE_DECIMALS),
            expected=result.expected_sections,
            returned=result.returned_sections,
            question=result.question,
        )
    on_topic_scores = [result.best_dense_score for result in report.results if result.expected_sections]
    off_topic_scores = [result.best_dense_score for result in report.results if not result.expected_sections]
    logger.info(
        "eval",
        hit_at_5=round(report.hit_at_k, SCORE_DECIMALS),
        not_found_accuracy=round(report.not_found_accuracy, SCORE_DECIMALS),
        min_dense_score=settings.min_dense_score,
        lowest_on_topic_score=round(min(on_topic_scores, default=0.0), SCORE_DECIMALS),
        highest_off_topic_score=round(max(off_topic_scores, default=0.0), SCORE_DECIMALS),
    )


if __name__ == "__main__":
    main()
