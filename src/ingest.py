"""Build the local 10-K index: python src/ingest.py

Wiring only: loads Settings and the embedding models, then runs the ingestion pipeline. No API keys are needed.
"""

from contextlib import closing

from research_agent.config import Settings
from research_agent.ingestion.embeddings import EmbeddingTokenCounter, FastEmbedDense, FastEmbedSparse
from research_agent.ingestion.indexer import Indexer, open_qdrant
from research_agent.ingestion.pipeline import run_ingestion


def main() -> None:
    """Rebuild data/index from the configured filing."""
    settings = Settings()
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    with closing(open_qdrant(settings.index_dir)) as client:
        dense_embedder = FastEmbedDense(settings.dense_model)
        sparse_embedder = FastEmbedSparse(settings.sparse_model)
        token_counter = EmbeddingTokenCounter(settings.dense_model)
        indexer = Indexer(client, dense_embedder, sparse_embedder)
        run_ingestion(
            source_path=settings.source_html,
            index_dir=settings.index_dir,
            page_footer_pattern=settings.page_footer_pattern,
            chunk_max_tokens=settings.chunk_max_tokens,
            indexer=indexer,
            count_tokens=token_counter,
        )


if __name__ == "__main__":
    main()
