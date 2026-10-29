"""A scripted chat model and fake tools, so graph tests run the real graph with no API keys.

ScriptedChatModel replays prepared replies in order and records every input it gets. Its bind_tools returns the
model itself, so tool-bound calls replay the same script, and with_structured_output works through LangChain's
generic tool-call implementation: the plan is scripted as an AIMessage calling a "Plan" tool.
"""

import asyncio
import itertools
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from research_agent.models import Evidence
from research_agent.prompts import Prompts

FILE_ENCODING = "utf-8"
PLAN_TOOL_NAME = "Plan"
SEARCH_TOOL_NAME = "search_10k"
FAILING_TOOL_NAME = "web_search"

SYSTEM_TEMPLATE = "SYSTEM sections=$sections rounds_left=$rounds_left\nplan:\n$plan"
EXAMPLES_TEMPLATE = "EXAMPLES"
PLANNER_TEMPLATE = "PLANNER sections=$sections"
FINAL_TEMPLATE = "FINAL question=$question\nresults:\n$tool_results"

TAX_PASSAGE = "[D4] Part I › Item 1A › Financial Risks (p. 12)\nChanges in tax rates can raise tax expense."
TAX_EVIDENCE = Evidence(id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12")

_call_ids = itertools.count(1)


class ScriptedChatModel(GenericFakeChatModel):
    """A chat model that replays scripted replies and records each input, honouring BaseChatModel's contract."""

    calls: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Return the model itself: the script, not the tools, decides the replies."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the input, then return the next scripted reply."""
        self.calls.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def scripted_model(*replies: AIMessage | str) -> ScriptedChatModel:
    """Return a model that answers with these replies, in order."""
    return ScriptedChatModel(messages=iter(replies))


def plan_reply(*steps: tuple[str, str | None]) -> AIMessage:
    """Return the structured-output reply for a plan of (goal, tool) steps."""
    plan_steps = [{"goal": goal, "tool": tool_name} for goal, tool_name in steps]
    tool_call = {"type": "tool_call", "id": "plan-call", "name": PLAN_TOOL_NAME, "args": {"steps": plan_steps}}
    return AIMessage(content="", tool_calls=[tool_call])


def tool_calls_reply(*calls: tuple[str, dict[str, Any]]) -> AIMessage:
    """Return a model reply requesting these (tool name, arguments) calls, each with a unique call ID."""
    tool_calls = [
        {"type": "tool_call", "id": f"call-{next(_call_ids)}", "name": name, "args": arguments}
        for name, arguments in calls
    ]
    return AIMessage(content="", tool_calls=tool_calls)


def write_test_prompts(directory: Path) -> Prompts:
    """Write minimal prompt files whose filled values are easy to find, and load them."""
    templates = {
        "system.txt": SYSTEM_TEMPLATE,
        "examples.txt": EXAMPLES_TEMPLATE,
        "planner.txt": PLANNER_TEMPLATE,
        "final.txt": FINAL_TEMPLATE,
    }
    for file_name, template in templates.items():
        (directory / file_name).write_text(template, encoding=FILE_ENCODING)
    return Prompts(directory)


class QueryArguments(BaseModel):
    """Arguments of the fake tools."""

    query: str


class CallTimes:
    """Start and end times of each fake tool call, for checking concurrency."""

    def __init__(self) -> None:
        """Start with no calls."""
        self.intervals: list[tuple[float, float]] = []

    def spread_s(self) -> float:
        """Return the time from the first start to the last end."""
        first_start = min(start for start, _ in self.intervals)
        last_end = max(end for _, end in self.intervals)
        return last_end - first_start


def make_fake_search(call_times: CallTimes | None = None, delay_s: float = 0.0) -> BaseTool:
    """Build a search_10k stand-in that returns one cited passage, optionally after a delay."""
    recorded_times = call_times or CallTimes()

    @tool(SEARCH_TOOL_NAME, args_schema=QueryArguments, response_format="content_and_artifact")
    async def search_10k(query: str) -> tuple[str, list[Evidence]]:
        """Search the 10-K."""
        started = time.perf_counter()
        await asyncio.sleep(delay_s)
        recorded_times.intervals.append((started, time.perf_counter()))
        return TAX_PASSAGE, [TAX_EVIDENCE]

    return search_10k


def make_failing_tool() -> BaseTool:
    """Build a tool with a bug: it raises an unexpected exception, which ToolNode must turn into a message."""

    @tool(FAILING_TOOL_NAME, args_schema=QueryArguments, response_format="content_and_artifact")
    async def web_search(query: str) -> tuple[str, list[Evidence]]:
        """Search the web."""
        raise RuntimeError("unexpected failure")

    return web_search
