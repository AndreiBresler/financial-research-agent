"""The plan and agent nodes (LLD section 8): async callables with their model, store and prompts injected.

The model sees the whole current question, its own tool calls and their results, but only the questions and final
answers of earlier ones: old tool output stays in state for citations without being resent.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from research_agent.agent.state import AgentState
from research_agent.config import Settings
from research_agent.log import NODE_KIND, log_call
from research_agent.models import Plan
from research_agent.prompts import Prompts
from research_agent.retrieval.store import ChunkStore

PLAN_NODE = "plan"
AGENT_NODE = "agent"
TOOLS_NODE = "tools"
VERIFY_NODE = "verify"

SECTION_SEPARATOR = ", "
PLAN_LINE_SEPARATOR = "\n"
TOOL_RESULT_SEPARATOR = "\n\n"
NO_PLAN = "No plan."
NO_ROUNDS_LEFT = 0


def format_sections(store: ChunkStore) -> str:
    """List the filing's section IDs in document order, for the prompts."""
    return SECTION_SEPARATOR.join(store.section_ids())


def format_plan(plan: Plan | None) -> str:
    """Number the plan's steps, naming each step's tool."""
    if plan is None:
        return NO_PLAN
    lines = []
    for number, step in enumerate(plan.steps, start=1):
        tool_note = f" ({step.tool})" if step.tool else ""
        lines.append(f"{number}. {step.goal}{tool_note}")
    return PLAN_LINE_SEPARATOR.join(lines)


def current_turn_start(messages: list[AnyMessage]) -> int:
    """Return the index of the current question: the last human message."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return index
    return 0


def is_question_or_answer(message: BaseMessage) -> bool:
    """Tell a question or a final answer apart from tool calls and tool results."""
    if isinstance(message, HumanMessage):
        return True
    return isinstance(message, AIMessage) and not message.tool_calls


def earlier_turns(messages: list[AnyMessage]) -> list[BaseMessage]:
    """Return the questions and final answers before the current question."""
    start = current_turn_start(messages)
    return [message for message in messages[:start] if is_question_or_answer(message)]


def conversation_view(messages: list[AnyMessage]) -> list[BaseMessage]:
    """Return what the model sees: earlier questions and answers, then the whole current turn."""
    start = current_turn_start(messages)
    return [*earlier_turns(messages), *messages[start:]]


def tool_results_text(messages: list[AnyMessage]) -> str:
    """Join the current turn's tool results as plain text, markers included."""
    start = current_turn_start(messages)
    results = [message.text for message in messages[start:] if isinstance(message, ToolMessage)]
    return TOOL_RESULT_SEPARATOR.join(results)


class PlanNode:
    """Asks the model for a structured plan before any tool runs."""

    def __init__(self, llm: BaseChatModel, store: ChunkStore, prompts: Prompts) -> None:
        """Prepare the structured-output model and the section list."""
        self.planner = llm.with_structured_output(Plan)
        self.sections = format_sections(store)
        self.prompts = prompts

    @log_call(NODE_KIND, PLAN_NODE)
    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Plan the current question; the plan goes to state, not into the conversation."""
        planner_prompt = self.prompts.planner_prompt(self.sections)
        conversation = conversation_view(state["messages"])
        result = await self.planner.ainvoke([SystemMessage(planner_prompt), *conversation])
        plan = Plan.model_validate(result)
        return {"plan": plan}


class AgentNode:
    """Calls the model with tools until it answers, or without tools once the tool budget is used up."""

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        store: ChunkStore,
        prompts: Prompts,
        settings: Settings,
    ) -> None:
        """Bind the tools once and prepare the section list."""
        self.llm = llm
        self.tool_model = llm.bind_tools(tools)
        self.sections = format_sections(store)
        self.prompts = prompts
        self.max_tool_rounds = settings.max_tool_rounds

    @log_call(NODE_KIND, AGENT_NODE)
    async def __call__(self, state: AgentState) -> dict[str, Any]:
        """Take one agent step: request tools or answer, counting tool rounds."""
        rounds_left = self.max_tool_rounds - state["tool_rounds"]
        if rounds_left <= NO_ROUNDS_LEFT:
            return await self.answer_without_tools(state)
        system_prompt = self.prompts.system_prompt(self.sections, format_plan(state["plan"]), rounds_left)
        conversation = conversation_view(state["messages"])
        reply = await self.tool_model.ainvoke([SystemMessage(system_prompt), *conversation])
        if reply.tool_calls:
            return {"messages": [reply], "tool_rounds": state["tool_rounds"] + 1}
        return {"messages": [reply]}

    async def answer_without_tools(self, state: AgentState) -> dict[str, Any]:
        """Force an answer from a flattened input, so the request carries no tool-call blocks."""
        messages = state["messages"]
        question = messages[current_turn_start(messages)].text
        system_prompt = self.prompts.system_prompt(self.sections, format_plan(state["plan"]), NO_ROUNDS_LEFT)
        final_prompt = self.prompts.final_prompt(question, tool_results_text(messages))
        model_input = [SystemMessage(system_prompt), *earlier_turns(messages), HumanMessage(final_prompt)]
        reply = await self.llm.ainvoke(model_input)
        return {"messages": [reply]}
