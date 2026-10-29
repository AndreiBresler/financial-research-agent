"""Each real tool logs its calls (LLD section 11): outcome, error type and evidence_count, never ok for a failure."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from research_agent.log import configure_logging
from research_agent.tools.calculator import make_calculator
from research_agent.tools.web_search import make_web_search
from retrieval_fakes import build_search_10k
from tool_support import tool_call
from web_fakes import ScriptedTavilyClient

FILE_ENCODING = "utf-8"
OUTPUT_LIMIT = 12_000
WEB_RESULT = {
    "title": "Microsoft Q1 FY2026 results",
    "url": "https://example.com/microsoft-q1-fy2026",
    "content": "Gross margin was 69.8% of revenue.",
}


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    """Configure logging to a temporary file and return its path."""
    path = tmp_path / "logs" / "agent.jsonl"
    configure_logging(path, verbose=False)
    return path


def build_web_search(client: ScriptedTavilyClient) -> BaseTool:
    """Build web_search over a scripted client."""
    return make_web_search(
        client=client,
        web_max_results=5,
        web_timeout_s=10.0,
        tool_output_max_chars=OUTPUT_LIMIT,
        today=lambda: date(2026, 10, 26),
    )


async def call_and_read_log(tool: BaseTool, arguments: dict[str, Any], log_path: Path) -> dict[str, Any]:
    """Call the tool as ToolNode does and return the last log entry."""
    message = await tool.ainvoke(tool_call(tool, arguments))
    assert isinstance(message, ToolMessage)
    lines = log_path.read_text(encoding=FILE_ENCODING).splitlines()
    entry: dict[str, Any] = json.loads(lines[-1])
    assert entry["kind"] == "tool"
    assert entry["name"] == tool.name
    return entry


class TestSuccess:
    """A call with results logs ok and how many sources it produced."""

    async def test_search_10k(self, log_path: Path) -> None:
        """A cited search logs its passage count."""
        arguments = {"query": "tax rates", "section": "item:1A", "k": 1}
        entry = await call_and_read_log(build_search_10k(), arguments, log_path)
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 3

    async def test_web_search(self, log_path: Path) -> None:
        """A web search logs its result count."""
        tool = build_web_search(ScriptedTavilyClient([WEB_RESULT]))
        entry = await call_and_read_log(tool, {"query": "msft"}, log_path)
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 1

    async def test_calculator(self, log_path: Path) -> None:
        """A calculation logs its single source."""
        entry = await call_and_read_log(make_calculator(), {"expression": "34550 / 416161 * 100"}, log_path)
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 1


class TestNotFound:
    """Not found is a finding: ok, with evidence_count 0 so empty results stay visible."""

    async def test_search_10k(self, log_path: Path) -> None:
        """A search the filing can't answer."""
        entry = await call_and_read_log(build_search_10k(), {"query": "weather forecast"}, log_path)
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 0

    async def test_web_search(self, log_path: Path) -> None:
        """A web search with no results."""
        entry = await call_and_read_log(build_web_search(ScriptedTavilyClient([])), {"query": "msft"}, log_path)
        assert entry["outcome"] == "ok"
        assert entry["evidence_count"] == 0


class TestErrors:
    """Every ERROR the model sees is logged as an error, with the ToolException type and the message."""

    async def test_search_10k_unknown_section(self, log_path: Path) -> None:
        """An invalid section ID."""
        entry = await call_and_read_log(build_search_10k(), {"query": "tax", "section": "item:99"}, log_path)
        assert entry["outcome"] == "error"
        assert entry["error_type"] == "ToolException"
        assert entry["error"].startswith("ERROR unknown_section")

    async def test_web_search_unavailable(self, log_path: Path) -> None:
        """Tavily failing."""
        client = ScriptedTavilyClient(error=RuntimeError("HTTP 503 from Tavily"))
        entry = await call_and_read_log(build_web_search(client), {"query": "msft"}, log_path)
        assert entry["outcome"] == "error"
        assert entry["error_type"] == "ToolException"
        assert entry["error"].startswith("ERROR web_unavailable")

    async def test_calculator_invalid_expression(self, log_path: Path) -> None:
        """An expression with a name in it."""
        entry = await call_and_read_log(make_calculator(), {"expression": "net_sales * 0.1"}, log_path)
        assert entry["outcome"] == "error"
        assert entry["error_type"] == "ToolException"
        assert entry["error"].startswith("ERROR invalid_expression")
