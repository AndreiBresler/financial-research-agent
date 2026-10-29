"""A small indexed corpus and a topic-keyword embedder, so retrieval tests control every similarity score.

TopicDenseEmbedder counts topic keywords: texts sharing a topic have cosine 1.0, texts without one score 0
against everything. That makes the relevance threshold, the section filters and the cross-reference hop
deterministic, which the letter-frequency fake from step 2 can't do.
"""

import math
import re

from langchain_core.tools import BaseTool
from qdrant_client import QdrantClient

from ingestion_fakes import FakeSparseEmbedder
from research_agent.config import Settings
from research_agent.ingestion.indexer import Indexer
from research_agent.models import Chunk
from research_agent.retrieval.index import Index
from research_agent.retrieval.search import Searcher
from research_agent.retrieval.store import ChunkStore
from research_agent.tools.search_10k import make_search_10k

TOPICS = ("margin", "tax", "revenue", "iphone", "debt", "lease")
UNMATCHED_DOCUMENT_DIMENSION = len(TOPICS)
UNMATCHED_QUERY_DIMENSION = len(TOPICS) + 1
WORD_PATTERN = re.compile(r"[a-z]+")
FAKE_TOPIC_MODEL = "fake/topics"
# Topic-keyword cosines are 0 or near 1, so any floor in between separates relevant from irrelevant.
TEST_MIN_DENSE_SCORE = 0.5
TEST_TOP_K = 2
TEST_FILING_LABEL = "Form 10-K FY2025"
TEST_OUTPUT_LIMIT = 12_000

PART_I = "Part I"
PART_II = "Part II"
ITEM_1_HEADING = "Item 1. Business"
ITEM_1A_HEADING = "Item 1A. Risk Factors"
ITEM_7_HEADING = "Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations"
ITEM_8_HEADING = "Item 8. Financial Statements and Supplementary Data"
COMPETITION_RISK = "Competition can put pressure on the Company’s margin."
TAX_RISK = "Changes in tax rates can raise the Company’s tax expense."


def topic_vector(text: str, unmatched_dimension: int) -> list[float]:
    """Count topic keywords (prefix match, so 'taxes' counts as 'tax'); no topic means one unmatched dimension."""
    words = WORD_PATTERN.findall(text.lower())
    counts = [float(sum(1 for word in words if word.startswith(topic))) for topic in TOPICS]
    vector = [*counts, 0.0, 0.0]
    if not any(counts):
        vector[unmatched_dimension] = 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector]


class TopicDenseEmbedder:
    """Dense embedder over topic keywords; topic-free documents and queries never match each other."""

    model_name = FAKE_TOPIC_MODEL
    dimension = len(TOPICS) + 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages."""
        return [topic_vector(text, UNMATCHED_DOCUMENT_DIMENSION) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a query."""
        return topic_vector(text, UNMATCHED_QUERY_DIMENSION)


def corpus_chunk(
    seq: int,
    section_id: str,
    section_path: list[str],
    text: str,
    *,
    kind: str = "text",
    unit: str | None = None,
    position: int = 1,
    pages: tuple[int, int],
    cross_refs: list[str] | None = None,
) -> Chunk:
    """Build one corpus chunk; the unit defaults to the last path element."""
    return Chunk(
        seq=seq,
        kind=kind,
        section_id=section_id,
        section_path=section_path,
        unit=unit or section_path[-1],
        position=position,
        page_start=pages[0],
        page_end=pages[1],
        cross_refs=cross_refs or [],
        text=text,
    )


def build_corpus() -> list[Chunk]:
    """Return twelve chunks in document order across Items 1, 1A, 7, 8 and four notes."""
    item_8_path = [PART_II, ITEM_8_HEADING]
    return [
        corpus_chunk(
            1, "item:1", [PART_I, ITEM_1_HEADING, "Products"], "iPhone is the main product line.", pages=(1, 1)
        ),
        corpus_chunk(
            2,
            "item:1A",
            [PART_I, ITEM_1A_HEADING],
            "Read this section with Part II, Item 7.",
            pages=(5, 5),
            cross_refs=["item:7"],
        ),
        corpus_chunk(
            3,
            "item:1A",
            [PART_I, ITEM_1A_HEADING, "Business Risks"],
            COMPETITION_RISK,
            kind="risk_factor",
            unit=COMPETITION_RISK,
            position=2,
            pages=(6, 6),
        ),
        corpus_chunk(
            4,
            "item:1A",
            [PART_I, ITEM_1A_HEADING, "Financial Risks"],
            TAX_RISK,
            kind="risk_factor",
            unit=TAX_RISK,
            position=3,
            pages=(12, 12),
            cross_refs=["note:7", "note:3"],
        ),
        corpus_chunk(
            5,
            "item:1A",
            [PART_I, ITEM_1A_HEADING, "Financial Risks"],
            "Tax audits can also add debt and lease liabilities.",
            kind="risk_factor",
            unit=TAX_RISK,
            position=3,
            pages=(13, 14),
        ),
        corpus_chunk(
            6,
            "item:7",
            [PART_II, ITEM_7_HEADING, "Profitability"],
            "Gross margin rose on a richer services margin mix.",
            pages=(23, 23),
            cross_refs=["item:1"],
        ),
        corpus_chunk(
            7,
            "item:7",
            [PART_II, ITEM_7_HEADING, "Profitability"],
            "| Gross profit | 2025 |\n|---|---|\n| Total | $195,201 |",
            kind="table",
            position=2,
            pages=(23, 23),
        ),
        corpus_chunk(
            8,
            "item:8",
            [*item_8_path, "CONSOLIDATED STATEMENTS OF OPERATIONS"],
            "| Line | 2025 |\n|---|---|\n| Total revenue | $416,161 |",
            kind="table",
            pages=(28, 28),
        ),
        corpus_chunk(
            9,
            "note:2",
            [*item_8_path, "Note 2 – Sales"],
            "Revenue is recognized when control transfers.",
            pages=(37, 37),
        ),
        corpus_chunk(
            10,
            "note:3",
            [*item_8_path, "Note 3 – Earnings Per Share"],
            "Tax effects on iPhone earnings per share are small.",
            pages=(38, 38),
        ),
        corpus_chunk(
            11,
            "note:4",
            [*item_8_path, "Note 4 – Financial Instruments"],
            "Tax credits on debt investments were recorded.",
            pages=(39, 39),
        ),
        corpus_chunk(
            12,
            "note:7",
            [*item_8_path, "Note 7 – Provision"],
            "The effective tax rate on lease income was 17 percent.",
            pages=(42, 42),
            cross_refs=["note:4"],
        ),
    ]


def index_corpus(chunks: list[Chunk]) -> tuple[QdrantClient, TopicDenseEmbedder, FakeSparseEmbedder]:
    """Index the chunks into a fresh in-memory Qdrant and return the client and the embedders used."""
    client = QdrantClient(":memory:")
    dense_embedder = TopicDenseEmbedder()
    sparse_embedder = FakeSparseEmbedder()
    indexer = Indexer(client, dense_embedder, sparse_embedder)
    indexer.build(chunks)
    return client, dense_embedder, sparse_embedder


def build_searcher(xref_max_extra: int = 3) -> Searcher:
    """Index the corpus and return a searcher over it."""
    corpus = build_corpus()
    client, dense_embedder, sparse_embedder = index_corpus(corpus)
    settings = Settings(_env_file=None, min_dense_score=TEST_MIN_DENSE_SCORE, xref_max_extra=xref_max_extra)
    return Searcher(ChunkStore(corpus), Index(client, dense_embedder, sparse_embedder), settings)


def build_search_10k(tool_output_max_chars: int = TEST_OUTPUT_LIMIT) -> BaseTool:
    """Build search_10k over the indexed corpus."""
    searcher = build_searcher()
    return make_search_10k(
        store=searcher.store,
        searcher=searcher,
        top_k=TEST_TOP_K,
        tool_output_max_chars=tool_output_max_chars,
        filing_label=TEST_FILING_LABEL,
    )
