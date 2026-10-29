"""Fixtures and hooks shared by every test."""

from collections.abc import Iterator

import pytest
import structlog

from e2e_support import RESULTS_KEY, summary_lines


@pytest.fixture(autouse=True)
def reset_structlog() -> Iterator[None]:
    """Undo a test's global logging configuration and bound log context, so no test leaks into the next."""
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    """After an e2e run, print each question and the agent's answer, so the run shows what the agent said."""
    for result in config.stash.get(RESULTS_KEY, []):
        terminalreporter.section(result.name)
        for line in summary_lines(result):
            terminalreporter.write_line(line)
