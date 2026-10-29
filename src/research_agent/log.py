"""Logging (LLD section 11): JSON lines to a file, secret redaction, and a decorator for every node and tool call.

The decorator sits under @tool, so a tool's ToolException is logged as a failure before LangChain turns it into an
error ToolMessage; a failure is never logged as ok. run_id and thread_id come from structlog's contextvars, which the
CLI binds per question.
"""

import functools
import inspect
import logging
import re
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final, Literal, ParamSpec, TextIO, TypeVar, cast

import structlog
from langchain_core.messages import AIMessage
from structlog.typing import EventDict, WrappedLogger

P = ParamSpec("P")
R = TypeVar("R")
CallKind = Literal["node", "tool"]
NODE_KIND: CallKind = "node"
TOOL_KIND: CallKind = "tool"

REDACTED = "[REDACTED]"
# A credential word standing alone: api_key, x-api-key, access_token, Authorization; not input_tokens or monkey.
SECRET_KEY_PATTERN = re.compile(r"(?<![a-z])(key|token|authorization)(?![a-z])", re.IGNORECASE)
LOG_FILE_ENCODING = "utf-8"
LINE_END = "\n"
MILLISECONDS_PER_SECOND = 1_000
LATENCY_DECIMALS = 1

CALL_FINISHED = "call_finished"
CALL_FAILED = "call_failed"
OK_OUTCOME = "ok"
ERROR_OUTCOME = "error"
MESSAGES_KEY = "messages"
INPUT_TOKENS: Final = "input_tokens"
OUTPUT_TOKENS: Final = "output_tokens"
EVIDENCE_COUNT = "evidence_count"
TOOL_RESULT_PARTS = 2


class JsonLinesLogger:
    """Appends each rendered event as one line to the log file and, with --verbose, to the console.

    The file is opened per line, so a line survives a crash and no handle outlives a reconfiguration.
    """

    def __init__(self, log_path: Path, console: TextIO | None) -> None:
        """Keep the log file path and the optional console stream."""
        self.log_path = log_path
        self.console = console

    def msg(self, message: str) -> None:
        """Write one line to the log file and the console."""
        line = message + LINE_END
        with self.log_path.open("a", encoding=LOG_FILE_ENCODING) as log_file:
            log_file.write(line)
        if self.console is not None:
            self.console.write(line)
            self.console.flush()

    debug = info = warning = error = critical = exception = msg


def redact_secrets(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """Mask the values of keys that name a credential, in nested dicts too."""
    return redact_mapping(event_dict)


def redact_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of mapping with credential values masked."""
    redacted: dict[str, Any] = {}
    for key, value in mapping.items():
        if SECRET_KEY_PATTERN.search(str(key)):
            redacted[key] = REDACTED
        elif isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        else:
            redacted[key] = value
    return redacted


def configure_logging(log_path: Path, verbose: bool) -> None:
    """Send JSON log lines to log_path; with verbose, also send them, debug included, to stderr."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    console = sys.stderr if verbose else None
    level = logging.DEBUG if verbose else logging.INFO
    json_lines_logger = JsonLinesLogger(log_path, console)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=lambda *arguments: json_lines_logger,
        cache_logger_on_first_use=False,
    )


def usage_fields(result: object) -> dict[str, int]:
    """Sum the token usage of the model replies in a node's result; empty when there are none."""
    if isinstance(result, AIMessage):
        replies = [result]
    elif isinstance(result, Mapping):
        replies = [message for message in result.get(MESSAGES_KEY, []) if isinstance(message, AIMessage)]
    else:
        return {}
    usages = [reply.usage_metadata for reply in replies if reply.usage_metadata]
    if not usages:
        return {}
    return {
        INPUT_TOKENS: sum(usage[INPUT_TOKENS] for usage in usages),
        OUTPUT_TOKENS: sum(usage[OUTPUT_TOKENS] for usage in usages),
    }


def evidence_fields(result: object) -> dict[str, int]:
    """Count the Evidence of a tool's (content, artifact) result; empty for anything else."""
    if isinstance(result, tuple) and len(result) == TOOL_RESULT_PARTS and isinstance(result[1], list):
        return {EVIDENCE_COUNT: len(result[1])}
    return {}


def elapsed_ms(started: float) -> float:
    """Return the milliseconds since started, from time.perf_counter."""
    return round((time.perf_counter() - started) * MILLISECONDS_PER_SECOND, LATENCY_DECIMALS)


def log_success(kind: CallKind, name: str, started: float, result: object) -> None:
    """Log a finished call with its latency, token usage and Evidence count."""
    logger = structlog.get_logger()
    logger.info(
        CALL_FINISHED,
        kind=kind,
        name=name,
        latency_ms=elapsed_ms(started),
        outcome=OK_OUTCOME,
        **usage_fields(result),
        **evidence_fields(result),
    )


def log_failure(kind: CallKind, name: str, started: float, exception: Exception) -> None:
    """Log a failed call with the exception's type and message."""
    logger = structlog.get_logger()
    logger.error(
        CALL_FAILED,
        kind=kind,
        name=name,
        latency_ms=elapsed_ms(started),
        outcome=ERROR_OUTCOME,
        error_type=type(exception).__name__,
        error=str(exception),
    )


def log_call(kind: CallKind, name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a sync or async node or tool function so every call is logged; exceptions still propagate."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        """Wrap function, keeping it async if it was."""
        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                """Await the call and log its outcome."""
                started = time.perf_counter()
                try:
                    result = await function(*args, **kwargs)
                except Exception as exception:
                    log_failure(kind, name, started, exception)
                    raise
                log_success(kind, name, started, result)
                return result

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(function)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Run the call and log its outcome."""
            started = time.perf_counter()
            try:
                result = function(*args, **kwargs)
            except Exception as exception:
                log_failure(kind, name, started, exception)
                raise
            log_success(kind, name, started, result)
            return result

        return sync_wrapper

    return decorate
