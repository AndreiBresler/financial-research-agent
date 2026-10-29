"""The command-line interface (LLD section 10): startup checks, the REPL, one-shot mode and streamed output.

main.py builds everything and hands AgentCli the compiled graph; this module runs the conversation and prints it:
the plan, each tool call and result as it happens, then the answer rendered as Markdown.
"""

import argparse
import asyncio
import json
import re
import uuid
from collections.abc import Callable
from typing import Any, Final

import structlog
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown

from research_agent.agent.nodes import AGENT_NODE, PLAN_NODE, TOOLS_NODE, VERIFY_NODE, format_plan
from research_agent.agent.state import AgentState, question_input
from research_agent.config import Settings
from research_agent.ingestion.manifest import IndexIdentity, document_sha256, read_manifest, stale_reasons
from research_agent.ingestion.parser import PARSER_VERSION
from research_agent.models import Evidence, Plan

SUCCESS_EXIT_CODE = 0
RUNTIME_ERROR_EXIT_CODE = 1
INDEX_NOT_READY_EXIT_CODE = 2
INTERRUPTED_EXIT_CODE = 130

PROGRAM_NAME = "python src/main.py"
INGEST_COMMAND = "python src/ingest.py"
PROMPT = "> "
NEW_THREAD_COMMAND = "/new"
QUIT_COMMAND = "/quit"
BANNER = "Ask about Apple's fiscal 2025 Form 10-K. /new starts a new conversation, /quit exits."
NEW_THREAD_NOTICE = "Started a new conversation."
RECURSION_LIMIT = 25  # backstop only: max_tool_rounds ends the loop first (2 × rounds + 3 steps)
STREAM_MODE: Final = "updates"

PLAN_HEADING = "Plan:"
PLAN_INDENT = "  "
CALL_ARROW = "→"
RESULT_ARROW = "←"
LIST_SEPARATOR = ", "
WORD_SEPARATOR = " "
# A tool result's code: "ERROR web_unavailable" or "NO_RELEVANT_CONTENT".
RESULT_CODE_PATTERN = re.compile(r"^(ERROR \w+|[A-Z][A-Z_]+)")
UNEXPECTED_ERROR = "ERROR unexpected"
NO_SOURCES = "no sources"
ERROR_STYLE = "red"
DETAIL_STYLE = "dim"

logger = structlog.get_logger(__name__)


class CliArguments(BaseModel):
    """What the user asked for on the command line."""

    question: str | None
    verbose: bool


def parse_arguments(argv: list[str]) -> CliArguments:
    """Parse the command line: an optional question, quoted or not, and --verbose."""
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME, description=BANNER)
    parser.add_argument("question", nargs="*", help="answer this question and exit; omit it for a session")
    parser.add_argument("--verbose", action="store_true", help="also print full tool outputs and debug logs")
    parsed = parser.parse_args(argv)
    question = WORD_SEPARATOR.join(parsed.question) or None
    return CliArguments(question=question, verbose=parsed.verbose)


def index_problems(settings: Settings) -> list[str]:
    """Explain why the index can't be used, with the command that rebuilds it; empty when it is current."""
    if not settings.source_html.exists():
        return [f"The filing {settings.source_html} is missing."]
    expected = IndexIdentity(
        doc_sha256=document_sha256(settings.source_html.read_bytes()),
        parser_version=PARSER_VERSION,
        dense_model=settings.dense_model,
        sparse_model=settings.sparse_model,
    )
    reasons = stale_reasons(read_manifest(settings.index_dir), expected)
    if not reasons:
        return []
    return [*(f"Index not ready: {reason}." for reason in reasons), f"Build it with: {INGEST_COMMAND}"]


def startup_problems(settings: Settings) -> list[str]:
    """List everything that stops the agent from starting: the index, then the API keys."""
    problems = index_problems(settings)
    missing_keys = settings.missing_credentials()
    problems.extend(f"Missing {name}: set it in .env or the environment." for name in missing_keys)
    return problems


def format_tool_call(tool_call: ToolCall) -> str:
    """Show a tool call as the model made it: → search_10k(section="item:1A", k=3)."""
    arguments = LIST_SEPARATOR.join(
        f"{name}={json.dumps(value, ensure_ascii=False)}" for name, value in tool_call["args"].items()
    )
    return f"{CALL_ARROW} {tool_call['name']}({arguments})"


def result_code(text: str) -> str | None:
    """Return a tool result's code, such as ERROR web_unavailable or NO_RELEVANT_CONTENT, if it starts with one."""
    code_match = RESULT_CODE_PATTERN.match(text)
    return code_match.group(1) if code_match else None


def result_summary(message: ToolMessage) -> str:
    """Summarise a tool result: its citation IDs, or its error or not-found code."""
    if message.status == "error":
        return result_code(message.text) or UNEXPECTED_ERROR
    if isinstance(message.artifact, list) and message.artifact:
        citation_ids = [Evidence.model_validate(item).id for item in message.artifact]
        return LIST_SEPARATOR.join(citation_ids)
    return result_code(message.text) or NO_SOURCES


def format_tool_result(message: ToolMessage) -> str:
    """Show one line per tool result: ← search_10k: D3, D4."""
    return f"{RESULT_ARROW} {message.name}: {result_summary(message)}"


def new_thread_id() -> str:
    """Return a fresh conversation ID."""
    return uuid.uuid4().hex


class AgentCli:
    """Runs questions through the graph and prints each step as it streams in."""

    def __init__(
        self,
        graph: CompiledStateGraph[AgentState, None, AgentState, AgentState],
        console: Console,
        settings: Settings,
        verbose: bool,
        read_line: Callable[[str], str] = input,
    ) -> None:
        """Keep the graph, the console and the input function; map each node to what it prints."""
        self.graph = graph
        self.console = console
        self.settings = settings
        self.verbose = verbose
        self.read_line = read_line
        self.update_printers: dict[str, Callable[[dict[str, Any]], None]] = {
            PLAN_NODE: self.print_plan,
            AGENT_NODE: self.print_tool_calls,
            TOOLS_NODE: self.print_tool_results,
            VERIFY_NODE: self.print_answer,
        }

    def print_line(self, text: str, style: str | None = None) -> None:
        """Print text as is: tool output and markers must never be read as rich markup."""
        self.console.print(text, style=style, markup=False, highlight=False)

    def print_plan(self, update: dict[str, Any]) -> None:
        """Print the numbered plan before any tool runs."""
        plan: Plan = update["plan"]
        self.print_line(PLAN_HEADING)
        for line in format_plan(plan).splitlines():
            self.print_line(f"{PLAN_INDENT}{line}")

    def print_tool_calls(self, update: dict[str, Any]) -> None:
        """Print each tool call the model requested; an answer is printed later, after verification."""
        reply = update["messages"][-1]
        if isinstance(reply, AIMessage):
            for tool_call in reply.tool_calls:
                self.print_line(format_tool_call(tool_call))

    def print_tool_results(self, update: dict[str, Any]) -> None:
        """Print one line per tool result and, with --verbose, the full output."""
        for message in update["messages"]:
            if not isinstance(message, ToolMessage):
                continue
            self.print_line(format_tool_result(message))
            if self.verbose:
                self.print_line(message.text, style=DETAIL_STYLE)

    def print_answer(self, update: dict[str, Any]) -> None:
        """Render the verified answer, with its Sources, as Markdown."""
        self.console.print()
        self.console.print(Markdown(update["final"]))

    def print_update(self, update: dict[str, Any]) -> None:
        """Print what each node produced, in the order the nodes finish."""
        for node_name, node_update in update.items():
            printer = self.update_printers.get(node_name)
            if printer is not None and node_update:
                printer(node_update)

    async def ask(self, question: str, thread_id: str) -> bool:
        """Answer one question on a thread, streaming each step; return False if it was refused or failed."""
        max_chars = self.settings.question_max_chars
        if len(question) > max_chars:
            self.print_line(f"The question is {len(question)} characters; the limit is {max_chars}.", ERROR_STYLE)
            return False
        structlog.contextvars.bind_contextvars(run_id=new_thread_id(), thread_id=thread_id)
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
        try:
            async for update in self.graph.astream(question_input(question), config, stream_mode=STREAM_MODE):
                self.print_update(update)
        # The model call failed after its retries, or a node broke: report it and keep the session.
        except Exception as exception:
            logger.error("question_failed", error_type=type(exception).__name__, error=str(exception))
            self.print_line(f"The question failed: {exception}", ERROR_STYLE)
            return False
        return True

    async def run_once(self, question: str) -> int:
        """Answer one question on a new thread and return the exit code."""
        answered = await self.ask(question, new_thread_id())
        return SUCCESS_EXIT_CODE if answered else RUNTIME_ERROR_EXIT_CODE

    async def run_repl(self) -> int:
        """Read questions until /quit, end of input or Ctrl+C; /new starts a new thread."""
        self.print_line(BANNER)
        thread_id = new_thread_id()
        while True:
            try:
                line = await asyncio.to_thread(self.read_line, PROMPT)
            except EOFError:
                return SUCCESS_EXIT_CODE
            except KeyboardInterrupt:
                return INTERRUPTED_EXIT_CODE
            question = line.strip()
            if question == QUIT_COMMAND:
                return SUCCESS_EXIT_CODE
            if question == NEW_THREAD_COMMAND:
                thread_id = new_thread_id()
                self.print_line(NEW_THREAD_NOTICE)
            elif question:
                await self.ask(question, thread_id)

    async def run(self, question: str | None) -> int:
        """Answer the question once, or start a session when there is none."""
        if question is None:
            return await self.run_repl()
        return await self.run_once(question)
