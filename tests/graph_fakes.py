"""A scripted chat model and fake tools, so graph tests run the real graph with no API keys.

ScriptedChatModel replays prepared replies in order and records every input it gets. Its bind_tools returns the
model itself, so tool-bound calls replay the same script, and with_structured_output works through LangChain's
generic tool-call implementation: the plan is scripted as an AIMessage calling a "Plan" tool. A scripted exception
is raised instead of replied, to stand in for a model call that fails after its retries.
"""

import asyncio
import itertools
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from research_agent.models import Evidence
from research_agent.prompts import Prompts

FILE_ENCODING = "utf-8"
PLAN_TOOL_NAME = "Plan"
SEARCH_TOOL_NAME = "search_10k"
FAILING_TOOL_NAME = "web_search"

SYSTEM_TEMPLATE = "SYSTEM sections=$sections max_rounds=$max_tool_rounds\nplan:\n$plan"
EXAMPLES_TEMPLATE = "EXAMPLES"
PLANNER_TEMPLATE = "PLANNER sections=$sections"
FINAL_TEMPLATE = "FINAL question=$question\nresults:\n$tool_results"

TAX_PASSAGE = "[D4] Part I › Item 1A › Financial Risks (p. 12)\nChanges in tax rates can raise tax expense."
TAX_EVIDENCE = Evidence(id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12")

_call_ids = itertools.count(1)


class ScriptedChatModel(GenericFakeChatModel):
    """A chat model that replays scripted replies and records each input, honouring BaseChatModel's contract."""

    # Any, not AIMessage | str: the script may hold an exception to raise, which validation would reject.
    messages: Iterator[Any]
    calls: list[list[BaseMessage]] = Field(default_factory=list)
    structured_output_methods: list[str | None] = Field(default_factory=list)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Return the model itself: the script, not the tools, decides the replies."""
        return self

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        method: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        """Record the requested method, then parse the scripted Plan tool call through LangChain's generic path."""
        self.structured_output_methods.append(method)
        return super().with_structured_output(schema, include_raw=include_raw, **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Record the input, then return the next scripted reply, or raise it if it is an exception."""
        self.calls.append(list(messages))
        reply = next(self.messages)
        if isinstance(reply, Exception):
            raise reply
        message = AIMessage(content=reply) if isinstance(reply, str) else reply
        return ChatResult(generations=[ChatGeneration(message=message)])


def scripted_model(*replies: AIMessage | str | Exception) -> ScriptedChatModel:
    """Return a model that answers with these replies, in order."""
    return ScriptedChatModel(messages=iter(replies))


def plan_reply(*steps: tuple[str, str | None]) -> AIMessage:
    """Return the structured-output reply for a plan of (goal, tool) steps."""
    plan_steps = [{"goal": goal, "tool": tool_name} for goal, tool_name in steps]
    tool_call = {"type": "tool_call", "id": "plan-call", "name": PLAN_TOOL_NAME, "args": {"steps": plan_steps}}
    return AIMessage(content="", tool_calls=[tool_call])


def tool_calls_reply(*calls: tuple[str, dict[str, Any]], thinking: str | None = None) -> AIMessage:
    """Return a model reply requesting these (tool name, arguments) calls, each with a unique call ID."""
    tool_calls = [
        {"type": "tool_call", "id": f"call-{next(_call_ids)}", "name": name, "args": arguments}
        for name, arguments in calls
    ]
    content: str | list[str | dict[str, Any]] = [thinking_block(thinking)] if thinking else ""
    return AIMessage(content=content, tool_calls=tool_calls)


def thinking_block(thinking: str) -> dict[str, Any]:
    """Return a Claude thinking content block, as langchain-anthropic represents it."""
    return {"type": "thinking", "thinking": thinking, "signature": "signature-bound-to-this-history"}


def answer_with_thinking(answer: str, thinking: str) -> AIMessage:
    """Return a final answer whose content starts with a thinking block, as Claude's adaptive thinking produces."""
    return AIMessage(content=[thinking_block(thinking), {"type": "text", "text": answer}])


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
