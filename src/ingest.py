"""Build the local 10-K index: python src/ingest.py

Wiring only: loads Settings and the embedding models, then runs the ingestion pipeline. No API keys are needed.
"""

import sys

from qdrant_client import QdrantClient

from research_agent.config import Settings
from research_agent.ingestion.embeddings import EmbeddingTokenCounter, FastEmbedDense, FastEmbedSparse
from research_agent.ingestion.indexer import Indexer
from research_agent.ingestion.pipeline import QDRANT_DIRECTORY_NAME, run_ingestion

SUCCESS_EXIT_CODE = 0


def main() -> int:
    """Rebuild data/index from the configured filing."""
    settings = Settings()
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    qdrant_path = settings.index_dir / QDRANT_DIRECTORY_NAME
    client = QdrantClient(path=str(qdrant_path))
    try:
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
    finally:
        client.close()
    return SUCCESS_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
