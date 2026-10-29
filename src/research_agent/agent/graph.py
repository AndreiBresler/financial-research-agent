"""The agent graph (LLD section 8): plan → agent ⇄ tools → verify, with every dependency injected."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Checkpointer

from research_agent.agent.nodes import AGENT_NODE, PLAN_NODE, TOOLS_NODE, VERIFY_NODE, AgentNode, PlanNode
from research_agent.agent.state import AgentState
from research_agent.agent.verify import verify_node
from research_agent.config import Settings
from research_agent.models import Plan, PlanStep
from research_agent.prompts import Prompts
from research_agent.retrieval.store import ChunkStore

AgentGraph = CompiledStateGraph[AgentState, None, AgentState, AgentState]

# State models restored from checkpoints; LangGraph blocks unregistered types.
CHECKPOINT_MODELS = (Plan, PlanStep)


def build_checkpointer() -> InMemorySaver:
    """Return the in-memory thread store, allowed to restore our state models from its checkpoints."""
    allowed_models = [(model.__module__, model.__name__) for model in CHECKPOINT_MODELS]
    serializer = JsonPlusSerializer(allowed_msgpack_modules=allowed_models)
    return InMemorySaver(serde=serializer)


def route_after_agent(state: AgentState) -> str:
    """Route to tools while the model requests them; otherwise verify the answer."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return TOOLS_NODE
    return VERIFY_NODE


def build_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
    store: ChunkStore,
    prompts: Prompts,
    settings: Settings,
    checkpointer: Checkpointer = None,
) -> AgentGraph:
    """Assemble the agent graph: plan → agent ⇄ tools → verify (HLD section 4)."""
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node(PLAN_NODE, PlanNode(llm, store, prompts))
    graph_builder.add_node(AGENT_NODE, AgentNode(llm, tools, store, prompts, settings))
    # Runs one step's tool calls concurrently and turns unexpected tool exceptions into error ToolMessages.
    graph_builder.add_node(TOOLS_NODE, ToolNode(tools, handle_tool_errors=True))
    graph_builder.add_node(VERIFY_NODE, verify_node)

    graph_builder.add_edge(START, PLAN_NODE)
    graph_builder.add_edge(PLAN_NODE, AGENT_NODE)
    # The agent loops through tools until it answers; at the budget it answers without tools.
    graph_builder.add_conditional_edges(AGENT_NODE, route_after_agent, [TOOLS_NODE, VERIFY_NODE])
    graph_builder.add_edge(TOOLS_NODE, AGENT_NODE)
    graph_builder.add_edge(VERIFY_NODE, END)
    return graph_builder.compile(checkpointer=checkpointer)
