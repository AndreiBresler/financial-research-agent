"""Unit tests for the CLI (LLD section 10): arguments, startup checks, streamed output, the REPL and one-shot mode.

The CLI drives the real graph with a scripted model and writes to an in-memory rich console, so no API keys are
needed.
"""

import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import structlog
from langchain_core.messages import ToolCall, ToolMessage
from rich.console import Console

from graph_fakes import (
    SEARCH_TOOL_NAME,
    ScriptedChatModel,
    make_fake_search,
    plan_reply,
    scripted_model,
    tool_calls_reply,
)
from graph_support import build_test_graph
from research_agent.cli import (
    INGEST_COMMAND,
    INTERRUPTED_EXIT_CODE,
    RUNTIME_ERROR_EXIT_CODE,
    SUCCESS_EXIT_CODE,
    AgentCli,
    CliArguments,
    format_tool_call,
    format_tool_result,
    parse_arguments,
    startup_problems,
)
from research_agent.config import Settings
from research_agent.ingestion.manifest import MISSING_INDEX_REASON, document_sha256, write_manifest
from research_agent.ingestion.parser import PARSER_VERSION
from research_agent.log import configure_logging
from research_agent.models import Evidence, Manifest

FILE_ENCODING = "utf-8"
CONSOLE_WIDTH = 200
FAKE_ANTHROPIC_KEY = "sk-ant-test-not-a-real-key"
FAKE_TAVILY_KEY = "tvly-test-not-a-real-key"
FILING_HTML = "<html><body><p>Apple Inc. | 2025 Form 10-K | 1</p></body></html>"

TAX_QUESTION = "How can tax rates affect Apple?"
TAX_GOAL = "Find the tax risk factor in Item 1A"
TAX_ANSWER = "Changes in tax rates can raise Apple's tax expense [D4]."
FOLLOW_UP_QUESTION = "Which section was that in?"
FOLLOW_UP_ANSWER = "Item 1A, Financial Risks [D4]."
PASSAGE_HEADER = "Part I › Item 1A › Financial Risks (p. 12)"
SOURCE_LINE = "[D4] Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12"
MODEL_FAILURE = "rate limited after 3 retries"

D3 = Evidence(id="D3", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Competition, p. 11")
D4 = Evidence(id="D4", kind="doc", source="Form 10-K FY2025 › Part I › Item 1A › Financial Risks, p. 12")


class ScriptedInput:
    """Stands in for input(): returns scripted lines, raises a scripted exception, then EOFError like Ctrl+D."""

    def __init__(self, lines: list[str | BaseException]) -> None:
        """Keep the lines to return, in order."""
        self.lines = list(lines)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        """Return the next line, or raise what the script says."""
        self.prompts.append(prompt)
        if not self.lines:
            raise EOFError
        line = self.lines.pop(0)
        if isinstance(line, BaseException):
            raise line
        return line


def tax_turn() -> list[Any]:
    """Script one question answered after a single search."""
    return [
        plan_reply((TAX_GOAL, SEARCH_TOOL_NAME)),
        tool_calls_reply((SEARCH_TOOL_NAME, {"query": "tax rates"})),
        TAX_ANSWER,
    ]


def follow_up_turn() -> list[Any]:
    """Script a follow-up answered without tools."""
    return [plan_reply(("Answer from the conversation", None)), FOLLOW_UP_ANSWER]


def cli_settings(question_max_chars: int = 2_000) -> Settings:
    """Return Settings that ignore the developer's .env."""
    return Settings(_env_file=None, question_max_chars=question_max_chars)


def build_cli(
    model: ScriptedChatModel,
    prompts_dir: Path,
    lines: list[str | BaseException] | None = None,
    settings: Settings | None = None,
    verbose: bool = False,
) -> tuple[AgentCli, io.StringIO]:
    """Build a CLI over the real graph and an in-memory console; return it with the console's buffer."""
    buffer = io.StringIO()
    console = Console(file=buffer, width=CONSOLE_WIDTH, color_system=None, force_terminal=False)
    graph = build_test_graph(model, [make_fake_search()], prompts_dir)
    cli = AgentCli(
        graph=graph,
        console=console,
        settings=settings or cli_settings(),
        verbose=verbose,
        read_line=ScriptedInput(lines or []),
    )
    return cli, buffer


class TestArguments:
    """python src/main.py starts the REPL; with a question it answers once."""

    def test_no_arguments_starts_the_repl(self) -> None:
        """No question means interactive mode."""
        assert parse_arguments([]) == CliArguments(question=None, verbose=False)

    def test_quoted_question(self) -> None:
        """A quoted question is answered once."""
        assert parse_arguments(["What is Apple's gross margin?"]).question == "What is Apple's gross margin?"

    def test_unquoted_words_and_verbose(self) -> None:
        """Unquoted words are joined into one question; --verbose can come first."""
        arguments = parse_arguments(["--verbose", "What", "is", "R&D?"])
        assert arguments == CliArguments(question="What is R&D?", verbose=True)


class TestStartup:
    """The CLI refuses to start, with exit code 2, when the index isn't ready or a key is missing."""

    def settings_with_filing(self, tmp_path: Path, with_keys: bool = True) -> Settings:
        """Return Settings over a temporary filing and index folder."""
        filing_path = tmp_path / "filing.htm"
        filing_path.write_text(FILING_HTML, encoding=FILE_ENCODING)
        return Settings(
            _env_file=None,
            source_html=filing_path,
            index_dir=tmp_path / "index",
            anthropic_api_key=FAKE_ANTHROPIC_KEY if with_keys else None,
            tavily_api_key=FAKE_TAVILY_KEY if with_keys else None,
        )

    def write_index_manifest(self, settings: Settings, parser_version: str = PARSER_VERSION) -> None:
        """Write the manifest an ingest of the temporary filing would write."""
        filing_bytes = settings.source_html.read_bytes()
        manifest = Manifest(
            doc_sha256=document_sha256(filing_bytes),
            parser_version=parser_version,
            dense_model=settings.dense_model,
            sparse_model=settings.sparse_model,
            chunk_count=1,
            built_at=datetime.now(UTC),
        )
        write_manifest(manifest, settings.index_dir)

    def test_ready(self, tmp_path: Path) -> None:
        """A current index and both keys: nothing to report."""
        settings = self.settings_with_filing(tmp_path)
        self.write_index_manifest(settings)
        assert startup_problems(settings) == []

    def test_missing_index_points_to_ingest(self, tmp_path: Path) -> None:
        """No manifest: say so and give the command that builds the index."""
        problems = " ".join(startup_problems(self.settings_with_filing(tmp_path)))
        assert MISSING_INDEX_REASON in problems
        assert INGEST_COMMAND in problems

    def test_stale_index_names_the_mismatch(self, tmp_path: Path) -> None:
        """An index built by another parser version is stale and must be rebuilt."""
        settings = self.settings_with_filing(tmp_path)
        self.write_index_manifest(settings, parser_version="0")
        problems = " ".join(startup_problems(settings))
        assert "parser_version" in problems
        assert INGEST_COMMAND in problems

    def test_missing_keys_are_named(self, tmp_path: Path) -> None:
        """A missing key names its environment variable; the index is fine, so no ingest advice."""
        settings = self.settings_with_filing(tmp_path, with_keys=False)
        self.write_index_manifest(settings)
        problems = " ".join(startup_problems(settings))
        assert "ANTHROPIC_API_KEY" in problems
        assert "TAVILY_API_KEY" in problems
        assert INGEST_COMMAND not in problems

    def test_missing_filing_is_reported(self, tmp_path: Path) -> None:
        """Without the source filing the index can't be checked; the path is named."""
        settings = Settings(
            _env_file=None,
            source_html=tmp_path / "missing.htm",
            index_dir=tmp_path / "index",
            anthropic_api_key=FAKE_ANTHROPIC_KEY,
            tavily_api_key=FAKE_TAVILY_KEY,
        )
        problems = " ".join(startup_problems(settings))
        assert "missing.htm" in problems


class TestToolLines:
    """Each tool call and result gets one line: the call's arguments, then the result's markers or error code."""

    def test_tool_call(self) -> None:
        """Arguments appear in the order the model gave them, with strings quoted."""
        tool_call = ToolCall(
            name="search_10k", args={"section": "item:1A", "order_by": "position", "k": 3}, id="call-1"
        )
        assert format_tool_call(tool_call) == '→ search_10k(section="item:1A", order_by="position", k=3)'

    def test_result_with_evidence_lists_its_markers(self) -> None:
        """A successful result shows the IDs the answer may cite."""
        message = ToolMessage("passages", tool_call_id="call-1", name="search_10k", artifact=[D3, D4])
        assert format_tool_result(message) == "← search_10k: D3, D4"

    def test_not_found_shows_its_code(self) -> None:
        """A result without Evidence shows its code, not the whole message."""
        message = ToolMessage(
            "NO_RELEVANT_CONTENT in item:1: retry without the section filter",
            tool_call_id="call-1",
            name="search_10k",
            artifact=[],
        )
        assert format_tool_result(message) == "← search_10k: NO_RELEVANT_CONTENT"

    def test_tool_error_shows_its_code(self) -> None:
        """An error result shows its ERROR code."""
        message = ToolMessage(
            "ERROR web_unavailable: timed out after 10s. Answer from the 10-K and list this under Data gaps.",
            tool_call_id="call-1",
            name="web_search",
            status="error",
        )
        assert format_tool_result(message) == "← web_search: ERROR web_unavailable"

    def test_unexpected_error_is_still_an_error(self) -> None:
        """ToolNode's message for a tool bug has no ERROR code, but is shown as an error."""
        message = ToolMessage(
            "Error: RuntimeError('bug')\n Please fix your mistakes.",
            tool_call_id="call-1",
            name="web_search",
            status="error",
        )
        assert format_tool_result(message).startswith("← web_search: ERROR")


class TestAsk:
    """One question: the plan, each tool call and result, then the answer, streamed as they happen."""

    async def test_streams_plan_calls_results_and_answer_in_order(self, tmp_path: Path) -> None:
        """The user sees the plan before any tool runs, and the answer with its Sources last."""
        cli, buffer = build_cli(scripted_model(*tax_turn()), tmp_path)
        assert await cli.ask(TAX_QUESTION, thread_id="thread-1")
        output = buffer.getvalue()
        positions = [
            output.index(f"1. {TAX_GOAL} (search_10k)"),
            output.index('→ search_10k(query="tax rates")'),
            output.index("← search_10k: D4"),
            output.index("Changes in tax rates can raise Apple's tax expense"),
            output.index(SOURCE_LINE),
        ]
        assert positions == sorted(positions)

    async def test_verbose_adds_full_tool_output(self, tmp_path: Path) -> None:
        """--verbose prints each tool's full output, which is hidden otherwise."""
        quiet_dir = tmp_path / "quiet"
        verbose_dir = tmp_path / "verbose"
        quiet_dir.mkdir()
        verbose_dir.mkdir()
        quiet_cli, quiet_buffer = build_cli(scripted_model(*tax_turn()), quiet_dir)
        verbose_cli, verbose_buffer = build_cli(scripted_model(*tax_turn()), verbose_dir, verbose=True)
        await quiet_cli.ask(TAX_QUESTION, thread_id="thread-1")
        await verbose_cli.ask(TAX_QUESTION, thread_id="thread-1")
        assert PASSAGE_HEADER not in quiet_buffer.getvalue()
        assert PASSAGE_HEADER in verbose_buffer.getvalue()

    async def test_too_long_question_is_refused(self, tmp_path: Path) -> None:
        """A question over question_max_chars never reaches the model."""
        model = scripted_model(*tax_turn())
        cli, buffer = build_cli(model, tmp_path, settings=cli_settings(question_max_chars=10))
        assert not await cli.ask(TAX_QUESTION, thread_id="thread-1")
        assert "10" in buffer.getvalue()
        assert model.calls == []

    async def test_model_failure_is_reported(self, tmp_path: Path) -> None:
        """A model call that fails after its retries prints a clear message instead of a traceback."""
        cli, buffer = build_cli(scripted_model(RuntimeError(MODEL_FAILURE)), tmp_path)
        assert not await cli.ask(TAX_QUESTION, thread_id="thread-1")
        assert MODEL_FAILURE in buffer.getvalue()
        assert "Traceback" not in buffer.getvalue()


class TestLogContext:
    """Every log line of a question carries its run_id and the thread_id."""

    @pytest.fixture(autouse=True)
    def reset_structlog(self) -> Iterator[None]:
        """Undo global logging configuration and bound context after each test."""
        yield
        structlog.reset_defaults()
        structlog.contextvars.clear_contextvars()

    async def test_each_question_gets_its_own_run_id(self, tmp_path: Path) -> None:
        """Two questions on one thread share the thread_id and have different run_ids."""
        log_path = tmp_path / "logs" / "agent.jsonl"
        configure_logging(log_path, verbose=False)
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        cli, _ = build_cli(scripted_model(*tax_turn(), *follow_up_turn()), prompts_dir)
        await cli.ask(TAX_QUESTION, thread_id="thread-7")
        await cli.ask(FOLLOW_UP_QUESTION, thread_id="thread-7")
        lines = log_path.read_text(encoding=FILE_ENCODING).splitlines()
        entries = [json.loads(line) for line in lines]
        plan_entries = [entry for entry in entries if entry.get("name") == "plan"]
        assert {entry["thread_id"] for entry in plan_entries} == {"thread-7"}
        assert len({entry["run_id"] for entry in plan_entries}) == 2


class TestRepl:
    """The REPL keeps one thread until /new, and exits on /quit, end of input or Ctrl+C."""

    async def test_new_starts_a_fresh_thread(self, tmp_path: Path) -> None:
        """After /new the model sees none of the earlier conversation."""
        model = scripted_model(*tax_turn(), *follow_up_turn())
        cli, _ = build_cli(model, tmp_path, lines=[TAX_QUESTION, "/new", FOLLOW_UP_QUESTION, "/quit"])
        assert await cli.run_repl() == SUCCESS_EXIT_CODE
        follow_up_agent_input = model.calls[-1]
        assert [message.type for message in follow_up_agent_input] == ["system", "human"]

    async def test_questions_share_a_thread_until_new(self, tmp_path: Path) -> None:
        """Without /new the follow-up sees the earlier question and answer."""
        model = scripted_model(*tax_turn(), *follow_up_turn())
        cli, _ = build_cli(model, tmp_path, lines=[TAX_QUESTION, FOLLOW_UP_QUESTION, "/quit"])
        await cli.run_repl()
        follow_up_agent_input = model.calls[-1]
        assert [message.type for message in follow_up_agent_input] == ["system", "human", "ai", "human"]

    async def test_end_of_input_exits_cleanly(self, tmp_path: Path) -> None:
        """Ctrl+D ends the session like /quit."""
        cli, _ = build_cli(scripted_model(*tax_turn()), tmp_path, lines=[TAX_QUESTION])
        assert await cli.run_repl() == SUCCESS_EXIT_CODE

    async def test_blank_lines_are_ignored(self, tmp_path: Path) -> None:
        """Pressing Enter on an empty line asks nothing."""
        model = scripted_model()
        cli, _ = build_cli(model, tmp_path, lines=["", "   ", "/quit"])
        assert await cli.run_repl() == SUCCESS_EXIT_CODE
        assert model.calls == []

    async def test_model_failure_keeps_the_session(self, tmp_path: Path) -> None:
        """After a failed question the REPL carries on and answers the next one."""
        model = scripted_model(RuntimeError(MODEL_FAILURE), *tax_turn())
        cli, buffer = build_cli(model, tmp_path, lines=[TAX_QUESTION, TAX_QUESTION, "/quit"])
        assert await cli.run_repl() == SUCCESS_EXIT_CODE
        output = buffer.getvalue()
        assert MODEL_FAILURE in output
        assert SOURCE_LINE in output

    async def test_ctrl_c_exits_with_130(self, tmp_path: Path) -> None:
        """Ctrl+C at the prompt ends the session with the conventional exit code."""
        cli, _ = build_cli(scripted_model(), tmp_path, lines=[KeyboardInterrupt()])
        assert await cli.run_repl() == INTERRUPTED_EXIT_CODE


class TestRunOnce:
    """One-shot mode answers and exits: 0 when an answer was shown, 1 when the question failed."""

    async def test_success(self, tmp_path: Path) -> None:
        """An answered question exits 0."""
        cli, buffer = build_cli(scripted_model(*tax_turn()), tmp_path)
        assert await cli.run_once(TAX_QUESTION) == SUCCESS_EXIT_CODE
        assert SOURCE_LINE in buffer.getvalue()

    async def test_model_failure(self, tmp_path: Path) -> None:
        """A failed model call exits 1."""
        cli, _ = build_cli(scripted_model(RuntimeError(MODEL_FAILURE)), tmp_path)
        assert await cli.run_once(TAX_QUESTION) == RUNTIME_ERROR_EXIT_CODE

    async def test_too_long_question(self, tmp_path: Path) -> None:
        """A refused question exits 1."""
        cli, _ = build_cli(scripted_model(), tmp_path, settings=cli_settings(question_max_chars=10))
        assert await cli.run_once(TAX_QUESTION) == RUNTIME_ERROR_EXIT_CODE
