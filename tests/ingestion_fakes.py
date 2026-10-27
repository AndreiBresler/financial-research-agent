"""Deterministic stand-ins for the embedding models and tokenizer, so ingestion tests need no downloads."""

import math
import string
import zlib
from collections import Counter

from qdrant_client import models

FAKE_DENSE_MODEL = "fake/dense-letters"
FAKE_SPARSE_MODEL = "fake/sparse-words"
LETTERS = string.ascii_lowercase
SPARSE_INDEX_SPACE = 100_000


def count_words(text: str) -> int:
    """Count whitespace-separated words; stands in for the embedding model's tokenizer."""
    words = text.split()
    return len(words)


def letter_vector(text: str) -> list[float]:
    """Return a unit-length vector of letter frequencies, so identical texts have cosine similarity 1."""
    lowered = text.lower()
    counts = [float(lowered.count(letter)) for letter in LETTERS]
    norm = math.sqrt(sum(count * count for count in counts)) or 1.0
    return [count / norm for count in counts]


def word_index(word: str) -> int:
    """Map a word to a stable sparse index."""
    encoded = word.encode("utf-8")
    return zlib.crc32(encoded) % SPARSE_INDEX_SPACE


class FakeDenseEmbedder:
    """Dense embedder over letter frequencies that records every batch it is asked to embed."""

    model_name = FAKE_DENSE_MODEL
    dimension = len(LETTERS)

    def __init__(self) -> None:
        """Start with no recorded batches."""
        self.batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of passages and record it."""
        self.batches.append(list(texts))
        return [letter_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a query the same way as a passage."""
        return letter_vector(text)


class FakeSparseEmbedder:
    """Sparse embedder over word counts that records every batch it is asked to embed."""

    model_name = FAKE_SPARSE_MODEL

    def __init__(self) -> None:
        """Start with no recorded batches."""
        self.batches: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[models.SparseVector]:
        """Embed a batch of passages and record it."""
        self.batches.append(list(texts))
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> models.SparseVector:
        """Return word counts keyed by stable word indices."""
        lowered = text.lower()
        words = lowered.split()
        counts = Counter(word_index(word) for word in words)
        indices = sorted(counts)
        values = [float(counts[index]) for index in indices]
        return models.SparseVector(indices=indices, values=values)
