"""Unit tests for logging (LLD section 11): JSON lines to a file, secret redaction, and the node and tool decorator."""

import asyncio
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import structlog
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from pydantic import BaseModel

from research_agent.log import REDACTED, configure_logging, log_call, redact_secrets
from research_agent.models import Evidence

FILE_ENCODING = "utf-8"
FAKE_API_KEY = "sk-ant-test-not-a-real-key"
SLEEP_S = 0.02
MIN_LATENCY_MS = 20
USAGE = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
SECOND_USAGE = {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250}

WEB_UNAVAILABLE_TEXT = "ERROR web_unavailable: timed out after 10s. Answer from the 10-K and list this under Data gaps."
NOT_FOUND_TEXT = "NO_RELEVANT_CONTENT: the 10-K has no passage relevant to this query; list it under Data gaps"
DOC_EVIDENCE = [
    Evidence(id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12"),
    Evidence(id="D12", kind="doc", source="Form 10-K FY2025 › Part II › Item 8 › Note 7 – Provision, p. 42"),
]

LogReader = Callable[[], list[dict[str, Any]]]


class EchoArguments(BaseModel):
    """Arguments of the test tools."""

    text: str


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    """Return a log file path whose directory doesn't exist yet."""
    return tmp_path / "logs" / "agent.jsonl"


@pytest.fixture
def read_log(log_path: Path) -> LogReader:
    """Configure logging to a temporary file and return a reader for its JSON lines."""
    configure_logging(log_path, verbose=False)

    def read() -> list[dict[str, Any]]:
        """Parse every line written so far."""
        lines = log_path.read_text(encoding=FILE_ENCODING).splitlines()
        return [json.loads(line) for line in lines]

    return read


def ai_reply(usage: dict[str, int]) -> AIMessage:
    """Return a model reply carrying token usage, as ChatAnthropic does."""
    return AIMessage(content="reply", usage_metadata=usage)


class TestConfigure:
    """configure_logging writes JSON lines to a file, and to the console only with --verbose."""

    def test_writes_json_lines_with_level_and_timestamp(self, read_log: LogReader) -> None:
        """Each event is one JSON object per line, written as it happens, with its level and a timestamp."""
        logger = structlog.get_logger()
        logger.info("question_received", question_chars=42)
        entries = read_log()
        assert len(entries) == 1
        entry = entries[0]
        assert entry["event"] == "question_received"
        assert entry["question_chars"] == 42
        assert entry["level"] == "info"
        assert "timestamp" in entry

    def test_creates_the_log_directory(self, log_path: Path) -> None:
        """logs/ is generated, so configure_logging creates it."""
        configure_logging(log_path, verbose=False)
        structlog.get_logger().info("started")
        assert log_path.exists()

    def test_reconfiguring_does_not_duplicate_lines(self, log_path: Path, read_log: LogReader) -> None:
        """Calling configure_logging again, as tests and a restarted REPL may, writes each event once."""
        configure_logging(log_path, verbose=False)
        structlog.get_logger().info("started")
        assert len(read_log()) == 1

    def test_secrets_are_redacted_in_the_file(self, log_path: Path, read_log: LogReader) -> None:
        """The redaction processor is part of the pipeline: a key never reaches the log file."""
        structlog.get_logger().info("client_created", api_key=FAKE_API_KEY)
        assert FAKE_API_KEY not in log_path.read_text(encoding=FILE_ENCODING)
        assert read_log()[0]["api_key"] == REDACTED

    def test_quiet_by_default(self, read_log: LogReader, capsys: pytest.CaptureFixture[str]) -> None:
        """Without --verbose the console stays clean for the answer; logs go only to the file."""
        structlog.get_logger().info("started")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_verbose_adds_debug_logs_on_stderr(self, log_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """--verbose shows debug logs on stderr, keeping stdout for the answer."""
        configure_logging(log_path, verbose=True)
        structlog.get_logger().debug("tool_output", content="passage text")
        captured = capsys.readouterr()
        assert "tool_output" in captured.err
        assert captured.out == ""


class TestRedaction:
    """Values of keys that name a key, token or authorization are masked; token counts are not."""

    @pytest.mark.parametrize("key", ["api_key", "ANTHROPIC_API_KEY", "tavily_api_key", "Authorization", "token"])
    def test_secret_keys_are_masked(self, key: str) -> None:
        """Any key naming a credential has its value replaced."""
        event_dict = {"event": "request", key: FAKE_API_KEY}
        redacted = redact_secrets(None, "info", event_dict)
        assert redacted[key] == REDACTED
        assert redacted["event"] == "request"

    def test_nested_secrets_are_masked(self) -> None:
        """Secrets inside nested dicts, such as request headers, are masked too."""
        event_dict = {"event": "request", "headers": {"x-api-key": FAKE_API_KEY, "accept": "json"}}
        redacted = redact_secrets(None, "info", event_dict)
        assert redacted["headers"] == {"x-api-key": REDACTED, "accept": "json"}

    def test_token_counts_are_kept(self) -> None:
        """Token usage is the point of the log, so input_tokens and friends are not secrets."""
        event_dict = {"event": "call_finished", **USAGE}
        redacted = redact_secrets(None, "info", event_dict)
        assert redacted == {"event": "call_finished", **USAGE}


class TestLogCall:
    """log_call wraps nodes and tools, sync or async, and logs name, latency, token usage and outcome."""

    async def test_async_node_logs_latency_usage_and_outcome(self, read_log: LogReader) -> None:
        """A node's returned messages give its token usage, summed over every model reply."""

        @log_call("node", "agent")
        async def agent_node(state: dict[str, Any]) -> dict[str, Any]:
            """Return two model replies after a short wait."""
            await asyncio.sleep(SLEEP_S)
            return {"messages": [ai_reply(USAGE), ai_reply(SECOND_USAGE)]}

        await agent_node({})
        entry = read_log()[-1]
        assert entry["kind"] == "node"
        assert entry["name"] == "agent"
        assert entry["outcome"] == "ok"
        assert entry["latency_ms"] >= MIN_LATENCY_MS
        assert entry["input_tokens"] == 320
        assert entry["output_tokens"] == 80

    async def test_messages_without_usage_log_no_token_counts(self, read_log: LogReader) -> None:
        """Human and tool messages carry no usage, so no token fields are invented."""

        @log_call("node", "tools")
        async def tools_node(state: dict[str, Any]) -> dict[str, Any]:
            """Return a tool result."""
            return {"messages": [HumanMessage("q"), ToolMessage("result", tool_call_id="call-1")]}

        await tools_node({})
        entry = read_log()[-1]
        assert entry["outcome"] == "ok"
        assert "input_tokens" not in entry

    def test_sync_function(self, read_log: LogReader) -> None:
        """Sync functions, such as the calculator, are wrapped without becoming coroutines."""

        @log_call("tool", "calculator")
        def calculator(expression: str) -> str:
            """Return a fixed result."""
            return "[C3bd255] 34550 / 416161 * 100 = 8.302075"

        result = calculator("34550 / 416161 * 100")
        assert result.endswith("8.302075")
        assert not inspect.iscoroutinefunction(calculator)
        assert read_log()[-1]["name"] == "calculator"

    async def test_wrapper_keeps_identity(self) -> None:
        """Async stays async and the docstring survives, because @tool reads both to build the tool."""

        @log_call("tool", "web_search")
        async def web_search(query: str) -> str:
            """Search the web."""
            return query

        assert inspect.iscoroutinefunction(web_search)
        assert web_search.__name__ == "web_search"
        assert web_search.__doc__ == "Search the web."

    async def test_exception_is_logged_and_reraised(self, read_log: LogReader) -> None:
        """A failure is logged with its type at error level, then propagates for ToolNode to handle."""

        @log_call("tool", "web_search")
        async def web_search(query: str) -> str:
            """Fail like a broken dependency."""
            raise RuntimeError("connection reset")

        with pytest.raises(RuntimeError, match="connection reset"):
            await web_search("Microsoft gross margin")
        entry = read_log()[-1]
        assert entry["outcome"] == "error"
        assert entry["error_type"] == "RuntimeError"
        assert entry["error"] == "connection reset"
        assert entry["level"] == "error"

    async def test_run_and_thread_ids_come_from_the_bound_context(self, read_log: LogReader) -> None:
        """The CLI binds run_id and thread_id per question; every node and tool line carries them."""
        structlog.contextvars.bind_contextvars(run_id="run-1", thread_id="thread-1")

        @log_call("node", "plan")
        async def plan_node(state: dict[str, Any]) -> dict[str, Any]:
            """Return an empty update."""
            return {}

        await plan_node({})
        entry = read_log()[-1]
        assert entry["run_id"] == "run-1"
        assert entry["thread_id"] == "thread-1"

    async def test_callable_class_node(self, read_log: LogReader) -> None:
        """Nodes are callable classes, so the decorator works on an async __call__ method."""

        class PlanNode:
            """A minimal node with injected state."""

            def __init__(self, reply: AIMessage) -> None:
                """Keep the reply to return."""
                self.reply = reply

            @log_call("node", "plan")
            async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
                """Return the prepared reply."""
                return {"messages": [self.reply]}

        await PlanNode(ai_reply(USAGE))({})
        entry = read_log()[-1]
        assert entry["name"] == "plan"
        assert entry["input_tokens"] == USAGE["input_tokens"]

    async def test_composes_with_the_tool_decorator(self, read_log: LogReader) -> None:
        """Under @tool, the wrapped function still builds a working async tool that logs each call."""

        @tool("echo", args_schema=EchoArguments)
        @log_call("tool", "echo")
        async def echo(text: str) -> str:
            """Repeat the text."""
            return text

        result = await echo.ainvoke({"text": "hello"})
        assert result == "hello"
        assert read_log()[-1]["name"] == "echo"


class TestToolOutcomes:
    """A tool failure is never logged as ok: tools raise ToolException, and the log and the message both say error."""

    async def test_tool_error_is_logged_and_becomes_an_error_message(self, read_log: LogReader) -> None:
        """The decorator logs the ToolException; @tool then turns it into a status-error ToolMessage the model reads."""

        @tool("probe", args_schema=EchoArguments, response_format="content_and_artifact")
        @log_call("tool", "probe")
        async def probe(text: str) -> tuple[str, list[Evidence]]:
            """Fail the way web_search does when Tavily times out."""
            raise ToolException(WEB_UNAVAILABLE_TEXT)

        probe.handle_tool_error = True
        tool_call = {"type": "tool_call", "id": "call-1", "name": "probe", "args": {"text": "x"}}
        message = await probe.ainvoke(tool_call)
        assert isinstance(message, ToolMessage)
        assert message.status == "error"
        assert message.content == WEB_UNAVAILABLE_TEXT
        entry = read_log()[-1]
        assert entry["outcome"] == "error"
        assert entry["error_type"] == "ToolException"
        assert entry["error"] == WEB_UNAVAILABLE_TEXT

    async def test_evidence_count_is_logged(self, read_log: LogReader) -> None:
        """A tool returning content and Evidence logs how many sources it produced."""

        @log_call("tool", "search_10k")
        async def search_10k(text: str) -> tuple[str, list[Evidence]]:
            """Return two cited passages."""
            return "[D4] …\n\n[D12] …", DOC_EVIDENCE

        await search_10k("tax rates")
        entry = read_log()[-1]
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 2

    async def test_not_found_is_ok_with_no_evidence(self, read_log: LogReader) -> None:
        """Not found is a finding, not a failure; evidence_count 0 keeps empty results visible in the log."""

        @log_call("tool", "search_10k")
        async def search_10k(text: str) -> tuple[str, list[Evidence]]:
            """Return the not-found message."""
            return NOT_FOUND_TEXT, []

        await search_10k("weather forecast")
        entry = read_log()[-1]
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 0
