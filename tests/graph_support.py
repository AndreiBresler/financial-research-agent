"""Builds the real agent graph around the fakes in graph_fakes.py, for the graph and CLI tests."""

from pathlib import Path

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from graph_fakes import ScriptedChatModel, write_test_prompts
from research_agent.agent.graph import build_checkpointer, build_graph
from research_agent.agent.state import AgentState
from research_agent.config import Settings
from research_agent.retrieval.store import ChunkStore
from retrieval_fakes import build_corpus

MAX_TOOL_ROUNDS = 6


def build_test_graph(
    model: ScriptedChatModel,
    tools: list[BaseTool],
    prompts_dir: Path,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    """Build the real graph over the scripted model, the given tools, the small test corpus and a fresh checkpointer."""
    # No .env file: the developer's real keys and overrides must not reach the tests.
    settings = Settings(_env_file=None, max_tool_rounds=max_tool_rounds)
    return build_graph(
        llm=model,
        tools=tools,
        store=ChunkStore(build_corpus()),
        prompts=write_test_prompts(prompts_dir),
        settings=settings,
        checkpointer=build_checkpointer(),
    )
