"""Run the research agent: python src/main.py ["question"] [--verbose]

Wiring only: loads Settings, configures logging and checks the index and API keys, then builds the agent once
and hands it to the CLI. Without a question it starts a session.
"""

import asyncio
import sys
from contextlib import closing

from rich.console import Console

from research_agent.cli import (
    INDEX_NOT_READY_EXIT_CODE,
    INTERRUPTED_EXIT_CODE,
    LOADING_MESSAGE,
    AgentCli,
    parse_arguments,
    ready_to_start,
)
from research_agent.composition import build_agent
from research_agent.config import Settings
from research_agent.ingestion.indexer import open_qdrant
from research_agent.log import configure_logging


def main(argv: list[str] | None = None) -> int:
    """Check the setup, build the agent and answer one question or run a session; return the exit code."""
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    settings = Settings()
    configure_logging(settings.log_path, arguments.verbose)
    console = Console()
    if not ready_to_start(settings, console):
        return INDEX_NOT_READY_EXIT_CODE
    try:
        with closing(open_qdrant(settings.index_dir)) as qdrant_client:
            with console.status(LOADING_MESSAGE):
                graph = build_agent(settings, qdrant_client)
            cli = AgentCli(graph=graph, console=console, settings=settings, verbose=arguments.verbose)
            return asyncio.run(cli.run(arguments.question))
    except KeyboardInterrupt:
        return INTERRUPTED_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
