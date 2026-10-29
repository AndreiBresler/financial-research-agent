"""Builds the real agent from Settings: the model, the tools and the graph. Used by main.py and the e2e tests.

The entry scripts open and close the Qdrant client and pass it in; everything else is created here, once.
"""

from datetime import date

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from pydantic import SecretStr
from qdrant_client import QdrantClient
from tavily import AsyncTavilyClient

from research_agent.agent.graph import AgentGraph, build_checkpointer, build_graph
from research_agent.config import Settings
from research_agent.ingestion.embeddings import FastEmbedDense, FastEmbedSparse
from research_agent.prompts import Prompts
from research_agent.retrieval.index import Index
from research_agent.retrieval.search import Searcher
from research_agent.retrieval.store import ChunkStore
from research_agent.tools.calculator import make_calculator
from research_agent.tools.search_10k import make_search_10k
from research_agent.tools.web_search import make_web_search

LLM_MAX_RETRIES = 3


def secret_value(secret: SecretStr | None) -> str:
    """Return a credential's value; startup_problems has already checked that it is set."""
    if secret is None:
        raise ValueError("a required API key is missing")
    return secret.get_secret_value()


def build_model(settings: Settings) -> BaseChatModel:
    """Create the chat model named in Settings, with retries; current Claude models take no sampling settings."""
    return init_chat_model(
        settings.llm_model,
        max_retries=LLM_MAX_RETRIES,
        timeout=settings.llm_timeout_s,
        api_key=secret_value(settings.anthropic_api_key),
    )


def build_tools(settings: Settings, store: ChunkStore, searcher: Searcher) -> list[BaseTool]:
    """Create the three tools over the shared store, searcher and web client."""
    web_client = AsyncTavilyClient(api_key=secret_value(settings.tavily_api_key))
    search_10k = make_search_10k(
        store=store,
        searcher=searcher,
        top_k=settings.top_k,
        tool_output_max_chars=settings.tool_output_max_chars,
        filing_label=settings.filing_label,
    )
    web_search = make_web_search(
        client=web_client,
        web_max_results=settings.web_max_results,
        web_timeout_s=settings.web_timeout_s,
        tool_output_max_chars=settings.tool_output_max_chars,
        today=date.today,
    )
    return [search_10k, web_search, make_calculator()]


def build_agent(settings: Settings, qdrant_client: QdrantClient) -> AgentGraph:
    """Load the index and embedding models once and build the agent graph over the real model and tools."""
    store = ChunkStore.load(settings.index_dir)
    dense_embedder = FastEmbedDense(settings.dense_model)
    sparse_embedder = FastEmbedSparse(settings.sparse_model)
    index = Index(qdrant_client, dense_embedder, sparse_embedder)
    searcher = Searcher(store, index, settings)
    return build_graph(
        llm=build_model(settings),
        tools=build_tools(settings, store, searcher),
        store=store,
        prompts=Prompts(settings.prompts_dir),
        settings=settings,
        checkpointer=build_checkpointer(),
    )
