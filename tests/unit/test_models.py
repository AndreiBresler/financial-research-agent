"""Unit tests for the data models (LLD section 5): the plan's step limit."""

import pytest
from pydantic import ValidationError

from research_agent.models import MAX_PLAN_STEPS, Plan, PlanStep


def plan_steps(count: int) -> list[PlanStep]:
    """Build count numbered search steps."""
    return [PlanStep(goal=f"Step {number}", tool="search_10k") for number in range(1, count + 1)]


def test_a_longer_plan_keeps_its_first_steps() -> None:
    """The API doesn't enforce the step limit, so a longer plan is cut instead of failing the question."""
    steps = plan_steps(MAX_PLAN_STEPS + 1)
    plan = Plan(steps=steps)
    assert plan.steps == steps[:MAX_PLAN_STEPS]


def test_a_plan_within_the_limit_is_kept_whole() -> None:
    """A plan at the limit loses nothing."""
    steps = plan_steps(MAX_PLAN_STEPS)
    assert Plan(steps=steps).steps == steps


def test_an_empty_plan_is_rejected() -> None:
    """A plan needs at least one step."""
    with pytest.raises(ValidationError):
        Plan(steps=[])
