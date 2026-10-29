"""The calculator tool (LLD section 7): arithmetic in code, because models are unreliable at it and eval is unsafe.

simpleeval gets no names, no attribute access and only round and abs, so an expression can compute but never
reach Python objects. The result is cited like any other source, with a C marker.
"""

import math
from collections.abc import Callable
from typing import Literal

from langchain_core.tools import BaseTool, ToolException, tool
from pydantic import BaseModel, Field
from simpleeval import InvalidExpression, SimpleEval

from research_agent.log import TOOL_KIND, log_call
from research_agent.models import Evidence
from research_agent.tools.output import hashed_citation_id

TOOL_NAME = "calculator"
INVALID_EXPRESSION = "ERROR invalid_expression"

MAX_EXPRESSION_CHARS = 200
RESULT_DECIMALS = 6
ALLOWED_FUNCTIONS: dict[str, Callable[..., object]] = {"round": round, "abs": abs}
CALC_EVIDENCE_KIND: Literal["calc"] = "calc"
CALC_ID_PREFIX = "C"
NON_NUMERIC_RESULT = "the result is not a number; use arithmetic only"
NON_FINITE_RESULT = "the result is not a finite number"
EVALUATION_ERRORS = (InvalidExpression, SyntaxError, ArithmeticError, TypeError, ValueError)


class CalculatorArguments(BaseModel):
    """Arguments of calculator."""

    expression: str = Field(
        min_length=1,
        max_length=MAX_EXPRESSION_CHARS,
        description="Arithmetic on numbers taken from tool results, e.g. 34550 / 416161 * 100.",
    )


class InvalidResultError(ValueError):
    """The expression evaluated, but not to a finite number."""


def citation_id(expression: str) -> str:
    """Return the stable C ID: whitespace can't change an expression's meaning, so it is removed before hashing."""
    compact_expression = "".join(expression.split())
    return hashed_citation_id(CALC_ID_PREFIX, compact_expression)


def evaluate(expression: str) -> int | float:
    """Evaluate arithmetic with no names, no attributes and only round and abs; return a finite number."""
    evaluator = SimpleEval(names={}, functions=ALLOWED_FUNCTIONS, allowed_attrs={})
    result = evaluator.eval(expression)
    # bool is a subclass of int, so comparisons would otherwise pass as numbers.
    if isinstance(result, bool) or not isinstance(result, int | float):
        raise InvalidResultError(NON_NUMERIC_RESULT)
    if not math.isfinite(result):
        raise InvalidResultError(NON_FINITE_RESULT)
    return round(result, RESULT_DECIMALS)


def make_calculator() -> BaseTool:
    """Build the calculator tool."""

    @tool(TOOL_NAME, args_schema=CalculatorArguments, response_format="content_and_artifact")
    @log_call(TOOL_KIND, TOOL_NAME)
    def calculator(expression: str) -> tuple[str, list[Evidence]]:
        """Evaluate an arithmetic expression and return the result with a citation marker such as [C7b2e04].

        Use it for every derived number: ratios, percentages, differences and growth rates. Write the numbers
        from tool results directly into the expression; variables are not supported. Supports + - * / ** %,
        parentheses, round(x, n) and abs(x). Results are rounded to 6 decimals. Cite the result with its marker,
        and state the units and period of the inputs in your answer.
        """
        try:
            result = evaluate(expression)
        except EVALUATION_ERRORS as exception:
            raise ToolException(f"{INVALID_EXPRESSION}: {exception}") from exception
        calculation = f"{expression} = {result}"
        marker_id = citation_id(expression)
        return f"[{marker_id}] {calculation}", [Evidence(id=marker_id, kind=CALC_EVIDENCE_KIND, source=calculation)]

    # Raised ToolExceptions reach the model as error ToolMessages carrying the same text.
    calculator.handle_tool_error = True
    return calculator
