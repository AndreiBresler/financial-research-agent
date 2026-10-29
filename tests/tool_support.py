"""Helpers for the tool tests: call a tool the way the graph's ToolNode does and read its result."""

import re

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from research_agent.models import Evidence

# The citation marker that heads each passage of a tool's output.
PASSAGE_MARKER_PATTERN = re.compile(r"^\[([DWC][0-9a-f]+)\] ", re.MULTILINE)
TOOL_CALL_ID = "call-1"


def tool_call(tool: BaseTool, arguments: dict[str, object]) -> dict[str, object]:
    """Build a tool call as the model requests it and ToolNode passes it on."""
    return {"type": "tool_call", "id": TOOL_CALL_ID, "name": tool.name, "args": arguments}


async def call_tool(tool: BaseTool, **arguments: object) -> ToolMessage:
    """Invoke the tool with a tool call, as ToolNode does, and return its message."""
    message = await tool.ainvoke(tool_call(tool, arguments))
    assert isinstance(message, ToolMessage)
    return message


def evidence_of(message: ToolMessage) -> list[Evidence]:
    """Return the Evidence artifact attached to a successful tool message."""
    artifact = message.artifact
    assert isinstance(artifact, list)
    return artifact


def markers(message: ToolMessage) -> list[str]:
    """Return the citation IDs heading the passages the model sees, in order."""
    content = str(message.content)
    return PASSAGE_MARKER_PATTERN.findall(content)
