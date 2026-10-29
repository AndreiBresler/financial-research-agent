"""Graph tests (LLD sections 8 and 12): the real graph, driven by a scripted model, with no API keys.

Covered paths: a normal answer, a tool error followed by recovery, budget exhaustion, concurrent tool calls, the
per-question state reset on a thread, verification (a cited answer gets Sources, an uncited one a warning), and
node and tool logging.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from graph_fakes import (
    EXAMPLES_TEMPLATE,
    FAILING_TOOL_NAME,
    SEARCH_TOOL_NAME,
    TAX_EVIDENCE,
    TAX_PASSAGE,
    CallTimes,
    ScriptedChatModel,
    answer_with_thinking,
    make_failing_tool,
    make_fake_search,
    plan_reply,
    scripted_model,
    tool_calls_reply,
)
from graph_support import build_test_graph
from research_agent.agent.render import SOURCES_HEADING, WARNING_PREFIX
from research_agent.agent.state import question_input
from research_agent.log import configure_logging
from research_agent.models import Plan, PlanStep
from research_agent.tools.calculator import TOOL_NAME as CALCULATOR_NAME
from research_agent.tools.calculator import make_calculator

FILE_ENCODING = "utf-8"
MAX_TOOL_ROUNDS = 6
SMALL_TOOL_BUDGET = 2
RECURSION_LIMIT = 25
THREAD_ID = "thread-1"
OTHER_THREAD_ID = "thread-2"
TOOL_DELAY_S = 0.2
MAX_PARALLEL_SPREAD_S = 0.3

TAX_QUESTION = "How can tax rates affect Apple?"
TAX_GOAL = "Find the tax risk factor in Item 1A"
TAX_ANSWER = "Changes in tax rates can raise Apple's tax expense [D4]."
R_AND_D_QUESTION = "What share of net sales went to R&D?"
R_AND_D_GOAL = "Divide R&D by net sales"
R_AND_D_ANSWER = "R&D was 8.3% of net sales [C3bd255]."
FOLLOW_UP_QUESTION = "Thanks. Which section was that in?"
FOLLOW_UP_ANSWER = "Item 1A, Financial Risks [D4]."
INVALID_EXPRESSION = "net_sales * 0.1"
VALID_EXPRESSION = "34550 / 416161 * 100"


def build(
    model: ScriptedChatModel,
    tools: list[BaseTool],
    prompts_dir: Path,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the real graph over the scripted model, the given tools and the small test corpus."""
    return build_test_graph(model, tools, prompts_dir, max_tool_rounds)


async def ask(
    graph: CompiledStateGraph[Any, Any, Any, Any], question: str, thread_id: str = THREAD_ID
) -> dict[str, Any]:
    """Ask one question on a thread, as the CLI does, and return the final state."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    result = await graph.ainvoke(question_input(question), config)
    assert isinstance(result, dict)
    return result


def message_kinds(messages: list[BaseMessage]) -> list[str]:
    """Name each message's role, telling tool-call requests apart from answers."""
    kinds = []
    for message in messages:
        if isinstance(message, AIMessage):
            kinds.append("ai_tool_calls" if message.tool_calls else "ai")
        elif isinstance(message, ToolMessage):
            kinds.append("tool")
        elif isinstance(message, HumanMessage):
            kinds.append("human")
        else:
            kinds.append(type(message).__name__)
    return kinds


def system_text(model_input: list[BaseMessage]) -> str:
    """Return the system prompt of one model call."""
    first_message = model_input[0]
    assert isinstance(first_message, SystemMessage)
    return str(first_message.content)


def is_question(message: BaseMessage, question: str) -> bool:
    """Check a message is the user's question; stored messages get IDs, so compare type and content."""
    return isinstance(message, HumanMessage) and message.content == question


def tool_messages(messages: list[BaseMessage]) -> list[ToolMessage]:
    """Return the tool results in a message list."""
    return [message for message in messages if isinstance(message, ToolMessage)]


class TestNormalAnswer:
    """plan → agent ⇄ tools → verify, with the plan kept out of the conversation."""

    async def test_plan_tools_and_answer(self, tmp_path: Path) -> None:
        """One tool round, then an answer: the state holds the plan, one round and the final answer."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
        )
        result = await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        assert result["plan"] == Plan(steps=[PlanStep(goal=TAX_GOAL, tool=SEARCH_TOOL_NAME)])
        assert result["tool_rounds"] == 1
        assert TAX_ANSWER in result["final"]

    async def test_conversation_has_no_dangling_tool_calls(self, tmp_path: Path) -> None:
        """The plan's structured-output call stays out of messages; every tool call has its result."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
        )
        result = await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        assert message_kinds(result["messages"]) == ["human", "ai_tool_calls", "tool", "ai"]
        assert tool_messages(result["messages"])[0].content == TAX_PASSAGE

    async def test_plan_uses_native_structured_output(self, tmp_path: Path) -> None:
        """The plan is requested as JSON-schema output, not a forced tool call, which Claude Sonnet 5.5 rejects."""
        model = scripted_model(plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)), TAX_ANSWER)
        await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        assert model.structured_output_methods == ["json_schema"]

    async def test_answer_without_tools(self, tmp_path: Path) -> None:
        """A question the model answers directly uses no tool rounds."""
        model = scripted_model(plan_reply(("Answer from the conversation", None)), TAX_ANSWER)
        result = await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        assert result["tool_rounds"] == 0
        assert message_kinds(result["messages"]) == ["human", "ai"]

    async def test_planner_sees_the_sections_and_the_question(self, tmp_path: Path) -> None:
        """The plan node fills planner.txt with the store's section IDs and passes the question."""
        model = scripted_model(plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)), TAX_ANSWER)
        await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        planner_input = model.calls[0]
        planner_prompt = system_text(planner_input)
        assert planner_prompt.startswith("PLANNER sections=")
        assert "item:1A" in planner_prompt
        assert "note:7" in planner_prompt
        assert is_question(planner_input[-1], TAX_QUESTION)

    async def test_agent_prompt_is_identical_on_every_round(self, tmp_path: Path) -> None:
        """system.txt plus examples.txt, filled with the plan and the fixed tool budget: Claude binds thinking blocks
        to the system prompt, so it must not change between rounds."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
        )
        await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        first_agent_prompt = system_text(model.calls[1])
        second_agent_prompt = system_text(model.calls[2])
        assert first_agent_prompt == second_agent_prompt
        assert f"max_rounds={MAX_TOOL_ROUNDS}" in first_agent_prompt
        assert TAX_GOAL in first_agent_prompt
        assert "item:1A" in first_agent_prompt
        assert first_agent_prompt.endswith(EXAMPLES_TEMPLATE)

    async def test_current_turn_is_resent_whole(self, tmp_path: Path) -> None:
        """Within a question, the model sees its own tool calls and their results."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
        )
        await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        second_agent_input = model.calls[2]
        assert message_kinds(second_agent_input[1:]) == ["human", "ai_tool_calls", "tool"]


class TestToolErrors:
    """A failed tool call becomes an error message the model reads and recovers from."""

    async def test_tool_error_then_recovery(self, tmp_path: Path) -> None:
        """The real calculator rejects a name; the model sees the error, retries with numbers and answers."""
        model = scripted_model(
            plan_reply((R_AND_D_GOAL, CALCULATOR_NAME)),
            tool_calls_reply((CALCULATOR_NAME, {"expression": INVALID_EXPRESSION})),
            tool_calls_reply((CALCULATOR_NAME, {"expression": VALID_EXPRESSION})),
            R_AND_D_ANSWER,
        )
        result = await ask(build(model, [make_calculator()], tmp_path), R_AND_D_QUESTION)
        results = tool_messages(result["messages"])
        assert [message.status for message in results] == ["error", "success"]
        assert results[1].content == f"[C3bd255] {VALID_EXPRESSION} = 8.302075"
        assert result["tool_rounds"] == 2
        assert R_AND_D_ANSWER in result["final"]
        retry_input = tool_messages(model.calls[2])
        assert retry_input[0].status == "error"

    async def test_unexpected_exception_becomes_an_error_message(self, tmp_path: Path) -> None:
        """A tool bug doesn't crash the question: ToolNode reports it to the model, which answers anyway."""
        model = scripted_model(
            plan_reply(("Search the web", FAILING_TOOL_NAME)),
            tool_calls_reply((FAILING_TOOL_NAME, {"query": "Microsoft gross margin"})),
            TAX_ANSWER,
        )
        result = await ask(build(model, [make_failing_tool()], tmp_path), TAX_QUESTION)
        results = tool_messages(result["messages"])
        assert results[0].status == "error"
        assert TAX_ANSWER in result["final"]


class TestBudget:
    """At max_tool_rounds the model must answer without tools, from a flattened input."""

    async def test_budget_forces_an_answer_without_tools(self, tmp_path: Path) -> None:
        """After two rounds with a budget of two, tools stop and the model answers from what it gathered."""
        call_times = CallTimes()
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax expense"})),
            TAX_ANSWER,
        )
        graph = build(model, [make_fake_search(call_times)], tmp_path, max_tool_rounds=SMALL_TOOL_BUDGET)
        result = await ask(graph, TAX_QUESTION)
        assert len(call_times.intervals) == SMALL_TOOL_BUDGET
        assert result["tool_rounds"] == SMALL_TOOL_BUDGET
        assert TAX_ANSWER in result["final"]

    async def test_final_input_is_flattened(self, tmp_path: Path) -> None:
        """The forced call carries no tool-call blocks: final.txt holds the question and the tool output as text."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax expense"})),
            TAX_ANSWER,
        )
        graph = build(model, [make_fake_search()], tmp_path, max_tool_rounds=SMALL_TOOL_BUDGET)
        await ask(graph, TAX_QUESTION)
        final_input = model.calls[-1]
        assert system_text(final_input) == system_text(model.calls[1])
        assert "tool" not in message_kinds(final_input)
        assert "ai_tool_calls" not in message_kinds(final_input)
        final_request = final_input[-1]
        assert isinstance(final_request, HumanMessage)
        final_text = str(final_request.content)
        assert final_text.startswith(f"FINAL question={TAX_QUESTION}")
        assert TAX_PASSAGE in final_text


class TestConcurrency:
    """ToolNode runs one step's tool calls concurrently."""

    async def test_two_calls_in_one_step_overlap(self, tmp_path: Path) -> None:
        """Two 0.2 s searches requested together finish within 0.3 s of the first starting."""
        call_times = CallTimes()
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply(
                (SEARCH_TOOL_NAME, {"query": "tax rates"}),
                (SEARCH_TOOL_NAME, {"query": "gross margin"}),
            ),
            TAX_ANSWER,
        )
        graph = build(model, [make_fake_search(call_times, delay_s=TOOL_DELAY_S)], tmp_path)
        result = await ask(graph, TAX_QUESTION)
        assert len(call_times.intervals) == 2
        assert call_times.spread_s() < MAX_PARALLEL_SPREAD_S
        assert result["tool_rounds"] == 1


class TestThread:
    """messages accumulate on a thread; plan, tool_rounds and final reset per question."""

    def tax_turn_then_follow_up(self) -> ScriptedChatModel:
        """Script a question with one tool round, then a follow-up answered directly."""
        return scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
            plan_reply(("Answer from the conversation", None)),
            FOLLOW_UP_ANSWER,
        )

    async def test_second_question_resets_per_question_state(self, tmp_path: Path) -> None:
        """The follow-up starts with a fresh plan and tool budget, and its own final answer."""
        graph = build(self.tax_turn_then_follow_up(), [make_fake_search()], tmp_path)
        await ask(graph, TAX_QUESTION)
        result = await ask(graph, FOLLOW_UP_QUESTION)
        assert result["plan"] == Plan(steps=[PlanStep(goal="Answer from the conversation", tool=None)])
        assert result["tool_rounds"] == 0
        assert FOLLOW_UP_ANSWER in result["final"]
        assert TAX_ANSWER not in result["final"]
        assert message_kinds(result["messages"]) == ["human", "ai_tool_calls", "tool", "ai", "human", "ai"]

    async def test_earlier_turns_resend_only_question_and_answer(self, tmp_path: Path) -> None:
        """Old tool output stays in state for citations but isn't resent to the model."""
        model = self.tax_turn_then_follow_up()
        graph = build(model, [make_fake_search()], tmp_path)
        await ask(graph, TAX_QUESTION)
        await ask(graph, FOLLOW_UP_QUESTION)
        follow_up_input = model.calls[-1]
        assert message_kinds(follow_up_input[1:]) == ["human", "ai", "human"]
        assert is_question(follow_up_input[1], TAX_QUESTION)
        assert follow_up_input[2].content == TAX_ANSWER
        assert is_question(follow_up_input[3], FOLLOW_UP_QUESTION)

    async def test_state_survives_the_checkpoint_round_trip(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A follow-up restores the plan and Evidence from the checkpoint, with no unregistered-type warning."""
        graph = build(self.tax_turn_then_follow_up(), [make_fake_search()], tmp_path)
        await ask(graph, TAX_QUESTION)
        await ask(graph, FOLLOW_UP_QUESTION)
        assert "unregistered type" not in caplog.text

    async def test_current_turn_keeps_thinking_blocks(self, tmp_path: Path) -> None:
        """Within a question the history is append-only, so the model's thinking is resent unchanged."""
        tool_request = tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"}), thinking="Search Item 1A first.")
        model = scripted_model(plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)), tool_request, TAX_ANSWER)
        await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        resent_request = model.calls[2][2]
        assert resent_request.content == tool_request.content

    async def test_earlier_turns_drop_thinking_blocks(self, tmp_path: Path) -> None:
        """Earlier turns are resent without their tool calls, so their thinking blocks, bound to the full history,
        are dropped; dropping thinking from the start of the history is allowed. The answer text stays."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            answer_with_thinking(TAX_ANSWER, "The tax risk factor answers this."),
            plan_reply(("Answer from the conversation", None)),
            FOLLOW_UP_ANSWER,
        )
        graph = build(model, [make_fake_search()], tmp_path)
        await ask(graph, TAX_QUESTION)
        await ask(graph, FOLLOW_UP_QUESTION)
        earlier_answer = model.calls[-1][2]
        assert isinstance(earlier_answer, AIMessage)
        assert earlier_answer.content == [{"type": "text", "text": TAX_ANSWER}]

    async def test_threads_are_isolated(self, tmp_path: Path) -> None:
        """/new starts a new thread, which carries nothing from the previous one."""
        graph = build(self.tax_turn_then_follow_up(), [make_fake_search()], tmp_path)
        await ask(graph, TAX_QUESTION)
        result = await ask(graph, FOLLOW_UP_QUESTION, thread_id=OTHER_THREAD_ID)
        assert message_kinds(result["messages"]) == ["human", "ai"]


class TestVerification:
    """verify checks the answer in code and render appends Sources, or a warning when a check fails."""

    async def test_cited_answer_gets_sources_and_no_warning(self, tmp_path: Path) -> None:
        """Every marker resolves, so the answer is followed by its Sources and carries no warning."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
        )
        result = await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        final = result["final"]
        assert final.startswith(TAX_ANSWER)
        assert SOURCES_HEADING in final
        assert f"[D4] {TAX_EVIDENCE.source}" in final
        assert WARNING_PREFIX not in final

    async def test_uncited_answer_gets_a_warning(self, tmp_path: Path) -> None:
        """An answer with an uncited figure and an unknown marker is delivered, with a warning on top."""
        uncited_answer = "Net sales were $416 billion in fiscal 2025. Margins rose [D999]."
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "net sales"})),
            uncited_answer,
        )
        result = await ask(build(model, [make_fake_search()], tmp_path), TAX_QUESTION)
        final = result["final"]
        assert final.startswith(WARNING_PREFIX)
        assert "D999" in final.split(uncited_answer)[0]
        assert uncited_answer in final

    async def test_follow_up_may_cite_evidence_from_an_earlier_question(self, tmp_path: Path) -> None:
        """IDs are stable and the registry spans the thread, so a follow-up citing [D4] still verifies."""
        model = scripted_model(
            plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
            tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
            TAX_ANSWER,
            plan_reply(("Answer from the conversation", None)),
            FOLLOW_UP_ANSWER,
        )
        graph = build(model, [make_fake_search()], tmp_path)
        await ask(graph, TAX_QUESTION)
        result = await ask(graph, FOLLOW_UP_QUESTION)
        final = result["final"]
        assert WARNING_PREFIX not in final
        assert f"[D4] {TAX_EVIDENCE.source}" in final


class TestLogging:
    """Every node and tool call is logged (LLD section 11)."""

    async def test_nodes_and_tools_are_logged(self, tmp_path: Path) -> None:
        """A run with the real calculator logs the plan, agent and verify nodes and the calculator call."""
        log_path = tmp_path / "logs" / "agent.jsonl"
        configure_logging(log_path, verbose=False)
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        model = scripted_model(
            plan_reply((R_AND_D_GOAL, CALCULATOR_NAME)),
            tool_calls_reply((CALCULATOR_NAME, {"expression": VALID_EXPRESSION})),
            R_AND_D_ANSWER,
        )
        await ask(build(model, [make_calculator()], prompts_dir), R_AND_D_QUESTION)
        lines = log_path.read_text(encoding=FILE_ENCODING).splitlines()
        entries = [json.loads(line) for line in lines]
        logged = {(entry.get("kind"), entry.get("name")) for entry in entries}
        assert {("node", "plan"), ("node", "agent"), ("node", "verify"), ("tool", CALCULATOR_NAME)} <= logged
