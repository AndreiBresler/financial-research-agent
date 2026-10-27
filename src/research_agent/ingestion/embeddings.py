"""Embedding model adapters: FastEmbed dense and sparse models, and the dense model's tokenizer for chunk sizing.

Ingestion uses them to embed passages; retrieval reuses them to embed queries.
"""

from typing import Protocol

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import models
from tokenizers import Tokenizer

EMBED_BATCH_SIZE = 64


class DenseEmbedder(Protocol):
    """Turns texts into dense vectors of a fixed dimension."""

    model_name: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query."""
        ...


class SparseEmbedder(Protocol):
    """Turns texts into sparse term vectors."""

    model_name: str

    def embed_documents(self, texts: list[str]) -> list[models.SparseVector]:
        """Embed passages for indexing."""
        ...

    def embed_query(self, text: str) -> models.SparseVector:
        """Embed a search query."""
        ...


class FastEmbedDense:
    """Dense embeddings from a local FastEmbed ONNX model, such as bge-small."""

    def __init__(self, model_name: str) -> None:
        """Load the model, downloading it on first use."""
        self.model_name = model_name
        self.dimension = TextEmbedding.get_embedding_size(model_name)
        self.model = TextEmbedding(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing."""
        vectors = self.model.passage_embed(texts, batch_size=EMBED_BATCH_SIZE)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query; bge models prefix queries differently from passages."""
        vectors = list(self.model.query_embed(text))
        first_vector = vectors[0]
        return list(first_vector.tolist())


class FastEmbedSparse:
    """Sparse BM25 vectors from FastEmbed; the index applies IDF at query time."""

    def __init__(self, model_name: str) -> None:
        """Load the model, downloading it on first use."""
        self.model_name = model_name
        self.model = SparseTextEmbedding(model_name)

    def embed_documents(self, texts: list[str]) -> list[models.SparseVector]:
        """Embed passages for indexing."""
        embeddings = self.model.embed(texts, batch_size=EMBED_BATCH_SIZE)
        return [
            models.SparseVector(indices=embedding.indices.tolist(), values=embedding.values.tolist())
            for embedding in embeddings
        ]

    def embed_query(self, text: str) -> models.SparseVector:
        """Embed a search query."""
        embeddings = list(self.model.query_embed(text))
        first_embedding = embeddings[0]
        indices = first_embedding.indices.tolist()
        values = first_embedding.values.tolist()
        return models.SparseVector(indices=indices, values=values)


class EmbeddingTokenCounter:
    """Counts tokens exactly as the dense model sees them, special tokens included, without truncation."""

    def __init__(self, model_name: str) -> None:
        """Load the model's tokenizer from the Hugging Face hub."""
        self.tokenizer = Tokenizer.from_pretrained(model_name)
        # A counter must see the whole text; truncation would cap every count at the model's limit.
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

    def __call__(self, text: str) -> int:
        """Return the number of model tokens in the text."""
        encoding = self.tokenizer.encode(text)
        return len(encoding.ids)
