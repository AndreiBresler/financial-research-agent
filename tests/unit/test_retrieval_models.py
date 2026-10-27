"""Opt-in retrieval tests with the real models on the real filing: the eval targets and search_10k end to end.

Run with: pytest -m embedding_models
These are the calibration targets: with the configured min_dense_score and rrf_k, the eval must pass.
"""

from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from qdrant_client import QdrantClient

from filing_support import PAGE_FOOTER_PATTERN, PROJECT_ROOT, REAL_FILING_PATH
from research_agent.config import Settings
from research_agent.ingestion.embeddings import EmbeddingTokenCounter, FastEmbedDense, FastEmbedSparse
from research_agent.ingestion.indexer import Indexer
from research_agent.ingestion.pipeline import run_ingestion
from research_agent.models import Evidence
from research_agent.retrieval.evaluation import EvalReport, evaluate, load_eval_set
from research_agent.retrieval.index import Index
from research_agent.retrieval.search import SearchConfig, Searcher
from research_agent.retrieval.store import ChunkStore
from research_agent.tools.search_10k import TOOL_NAME, make_search_10k

pytestmark = [
    pytest.mark.embedding_models,
    pytest.mark.skipif(not REAL_FILING_PATH.exists(), reason=f"{REAL_FILING_PATH} not downloaded"),
]

EVAL_SET_PATH = PROJECT_ROOT / "eval" / "retrieval_set.jsonl"
EVAL_K = 5
MIN_HIT_AT_K = 0.8
FIRST_RISK_FACTOR_PREFIX = "The Company’s operations and performance depend significantly on global and regional"


@pytest.fixture(scope="module")
def settings() -> Settings:
    """Return the configured defaults, which hold the calibrated thresholds."""
    return Settings(_env_file=None)


@pytest.fixture(scope="module")
def searcher_and_store(tmp_path_factory: pytest.TempPathFactory, settings: Settings) -> tuple[Searcher, ChunkStore]:
    """Ingest the real filing into a temporary index and return a searcher and store over it."""
    index_dir: Path = tmp_path_factory.mktemp("index")
    client = QdrantClient(path=str(index_dir / "qdrant"))
    dense_embedder = FastEmbedDense(settings.dense_model)
    sparse_embedder = FastEmbedSparse(settings.sparse_model)
    run_ingestion(
        source_path=REAL_FILING_PATH,
        index_dir=index_dir,
        page_footer_pattern=PAGE_FOOTER_PATTERN,
        chunk_max_tokens=settings.chunk_max_tokens,
        indexer=Indexer(client, dense_embedder, sparse_embedder),
        count_tokens=EmbeddingTokenCounter(settings.dense_model),
    )
    store = ChunkStore.load(index_dir)
    index = Index(client, dense_embedder, sparse_embedder)
    searcher = Searcher(store, index, SearchConfig.from_settings(settings))
    return searcher, store


@pytest.fixture(scope="module")
def report(searcher_and_store: tuple[Searcher, ChunkStore]) -> EvalReport:
    """Run the committed eval set once."""
    searcher, _ = searcher_and_store
    cases = load_eval_set(EVAL_SET_PATH)
    return evaluate(searcher, cases, k=EVAL_K)


@pytest.fixture(scope="module")
def tool(searcher_and_store: tuple[Searcher, ChunkStore], settings: Settings) -> BaseTool:
    """Return search_10k over the real index."""
    searcher, store = searcher_and_store
    return make_search_10k(
        store=store,
        searcher=searcher,
        top_k=settings.top_k,
        tool_output_max_chars=settings.tool_output_max_chars,
        filing_label=settings.filing_label,
    )


async def call(tool: BaseTool, **arguments: object) -> ToolMessage:
    """Invoke the tool with a tool call and return its message."""
    tool_call = {"type": "tool_call", "id": "call-1", "name": TOOL_NAME, "args": arguments}
    message = await tool.ainvoke(tool_call)
    assert isinstance(message, ToolMessage)
    return message


def test_eval_hit_rate(report: EvalReport) -> None:
    """At least 80% of on-topic questions find an expected section in the top 5."""
    misses = [result.question for result in report.results if result.expected_sections and not result.passed]
    assert report.hit_at_k >= MIN_HIT_AT_K, f"misses: {misses}"


def test_eval_rejects_every_off_topic_question(report: EvalReport) -> None:
    """Every off-topic question returns not found."""
    assert report.not_found_accuracy == pytest.approx(1.0)


def test_no_on_topic_question_falls_below_the_threshold(report: EvalReport, settings: Settings) -> None:
    """The threshold never turns a real question into 'not found'."""
    low_scores = {
        result.question: result.best_dense_score
        for result in report.results
        if result.expected_sections and result.best_dense_score < settings.min_dense_score
    }
    assert low_scores == {}


async def test_top_risk_factors_by_position(tool: BaseTool) -> None:
    """The first three risk factors come back in document order, starting with the macroeconomic one."""
    message = await call(tool, query="top risk factors", section="item:1A", order_by="position", k=3)
    evidence: list[Evidence] = message.artifact
    content = str(message.content)
    assert FIRST_RISK_FACTOR_PREFIX in content
    assert all("Item 1A" in item.source for item in evidence)
    assert len(evidence) >= 3


async def test_gross_margin_question_finds_the_table(tool: BaseTool) -> None:
    """Required query 2's Apple figure is retrievable by a plain question."""
    message = await call(tool, query="What was Apple's total gross margin percentage?")
    assert "46.9%" in str(message.content)


async def test_item_8_search_reaches_the_income_tax_note(tool: BaseTool) -> None:
    """An Item 8 search for the tax rate reaches Note 7, which an exact section filter would miss."""
    message = await call(tool, query="effective tax rate and provision for income taxes", section="item:8")
    evidence: list[Evidence] = message.artifact
    assert any("Note 7" in item.source for item in evidence)
