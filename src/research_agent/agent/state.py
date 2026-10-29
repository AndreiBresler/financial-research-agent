"""The graph state (LLD section 5) and the input that starts each question."""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph.message import add_messages

from research_agent.models import Plan


class AgentState(TypedDict):
    """State of one thread: messages accumulate across questions; the other fields belong to the current question."""

    messages: Annotated[list[AnyMessage], add_messages]
    plan: Plan | None
    tool_rounds: int
    final: str | None


def question_input(question: str) -> AgentState:
    """Return the input for a new question: its message, plus a reset of every per-question field."""
    return {"messages": [HumanMessage(question)], "plan": None, "tool_rounds": 0, "final": None}
