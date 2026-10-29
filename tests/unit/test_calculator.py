"""Unit tests for the calculator tool (LLD section 7): arithmetic only, stable C IDs, errors returned to the model."""

import hashlib
import re

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from research_agent.models import Evidence
from research_agent.tools.calculator import (
    INVALID_EXPRESSION,
    TOOL_NAME,
    CalculatorArguments,
    make_calculator,
)

EXPRESSION_ENCODING = "utf-8"
CALC_ID_PREFIX = "C"
CALC_ID_HEX_CHARS = 6
MARKER_PATTERN = re.compile(r"^\[(C[0-9a-f]{6})\] ", re.MULTILINE)
R_AND_D_SHARE = "34550 / 416161 * 100"


@pytest.fixture
def tool() -> BaseTool:
    """Return the calculator tool."""
    return make_calculator()


def call(tool: BaseTool, expression: str) -> ToolMessage:
    """Invoke the tool the way the graph's ToolNode does, with a tool call, and return its message."""
    tool_call = {"type": "tool_call", "id": "call-1", "name": TOOL_NAME, "args": {"expression": expression}}
    message = tool.invoke(tool_call)
    assert isinstance(message, ToolMessage)
    return message


def evidence_of(message: ToolMessage) -> list[Evidence]:
    """Return the Evidence artifact attached to a tool message."""
    artifact = message.artifact
    assert isinstance(artifact, list)
    return artifact


def expected_id(expression: str) -> str:
    """Return the C ID the LLD specifies: C plus 6 hex characters of the SHA-1 of the whitespace-free expression."""
    compact_expression = "".join(expression.split())
    digest = hashlib.sha1(compact_expression.encode(EXPRESSION_ENCODING)).hexdigest()
    return f"{CALC_ID_PREFIX}{digest[:CALC_ID_HEX_CHARS]}"


class TestDefinition:
    """What the model is told about the tool."""

    def test_name_schema_and_sync(self, tool: BaseTool) -> None:
        """The tool is called calculator, takes only an expression, and runs synchronously since it does no I/O."""
        schema_fields = set(CalculatorArguments.model_fields)
        assert tool.name == TOOL_NAME
        assert schema_fields == {"expression"}
        assert tool.description
        assert tool.coroutine is None

    @pytest.mark.parametrize("expression", ["", "1" * 201])
    def test_schema_rejects_bad_lengths(self, expression: str) -> None:
        """Expressions are 1-200 characters."""
        with pytest.raises(ValidationError):
            CalculatorArguments.model_validate({"expression": expression})


class TestResults:
    """Results come back with the expression and a stable citation marker."""

    def test_output_repeats_the_expression_with_its_marker(self, tool: BaseTool) -> None:
        """R&D as a share of net sales: the model sees the marker, the expression and the result."""
        message = call(tool, R_AND_D_SHARE)
        assert str(message.content) == f"[{expected_id(R_AND_D_SHARE)}] {R_AND_D_SHARE} = 8.302075"

    def test_evidence_matches_the_marker(self, tool: BaseTool) -> None:
        """One Evidence, kind calc, whose source line is the expression and its result."""
        message = call(tool, R_AND_D_SHARE)
        evidence = evidence_of(message)
        assert MARKER_PATTERN.findall(str(message.content)) == [expected_id(R_AND_D_SHARE)]
        assert evidence == [Evidence(id=expected_id(R_AND_D_SHARE), kind="calc", source=f"{R_AND_D_SHARE} = 8.302075")]

    def test_same_expression_keeps_its_id(self, tool: BaseTool) -> None:
        """IDs are stable, not counters: the same expression computed twice cites the same marker."""
        first = evidence_of(call(tool, R_AND_D_SHARE))
        second = evidence_of(call(tool, R_AND_D_SHARE))
        other = evidence_of(call(tool, "46.9 - 44.1"))
        assert first[0].id == second[0].id
        assert first[0].id != other[0].id

    @pytest.mark.parametrize("spacing", ["34550/416161*100", "34550 /416161 *  100", " 34550\t/ 416161 * 100 "])
    def test_whitespace_does_not_change_the_id(self, tool: BaseTool, spacing: str) -> None:
        """The ID hashes the expression without whitespace, so differently spaced copies cite one marker."""
        spaced = evidence_of(call(tool, spacing))
        canonical = evidence_of(call(tool, R_AND_D_SHARE))
        assert spaced[0].id == canonical[0].id

    def test_output_keeps_the_expression_as_written(self, tool: BaseTool) -> None:
        """Only the hash input is normalised; the model and the Sources line see the expression unchanged."""
        compact = "34550/416161*100"
        message = call(tool, compact)
        evidence = evidence_of(message)
        assert str(message.content) == f"[{expected_id(compact)}] {compact} = 8.302075"
        assert evidence[0].source == f"{compact} = 8.302075"

    @pytest.mark.parametrize(
        ("expression", "result"),
        [
            ("2 + 3", "5"),
            ("1 / 3", "0.333333"),
            ("46.9 - 69.8", "-22.9"),
            ("(416161 - 391035) / 391035 * 100", "6.425512"),
            ("2 ** 10", "1024"),
            ("round(8.30207, 2)", "8.3"),
            ("abs(-46.9)", "46.9"),
        ],
    )
    def test_arithmetic_rounded_to_six_decimals(self, tool: BaseTool, expression: str, result: str) -> None:
        """Arithmetic, round and abs work; results are rounded to 6 decimals, which also removes float noise."""
        message = call(tool, expression)
        assert str(message.content).endswith(f" = {result}")


class TestErrors:
    """Anything beyond arithmetic comes back as invalid_expression, never as an exception or a result."""

    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os').system('ls')",
            "(1).real",
            "().__class__.__bases__",
            "net_sales * 0.1",
            "sqrt(4)",
            "open('x')",
            "lambda: 1",
            "[1, 2, 3]",
            "'a' + 'b'",
            "1 < 2",
            "1 / 0",
            "9 ** 9 ** 9",
            "1e308 * 10",
            "2 +",
        ],
    )
    def test_rejected_expressions(self, tool: BaseTool, expression: str) -> None:
        """Imports, attributes, names, other functions, non-numeric or non-finite results, division by zero, huge
        powers and syntax errors are all rejected with an error the model can act on, and no Evidence."""
        message = call(tool, expression)
        assert str(message.content).startswith(f"{INVALID_EXPRESSION}: ")
        assert evidence_of(message) == []
