"""Run the end-to-end queries against the real agent: python src/run_e2e.py [--only NAME] [--output FILE]

Wiring only: checks the setup, builds the agent like main.py and runs eval/agent_queries.jsonl, printing each
answer and a pass/fail line. Needs API keys and costs tokens. --output writes the answers as Markdown.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from research_agent.agent.graph import AgentGraph
from research_agent.cli import INDEX_NOT_READY_EXIT_CODE, startup_problems
from research_agent.composition import build_agent, open_qdrant
from research_agent.config import Settings
from research_agent.e2e import AgentQuery, QueryResult, format_report, load_agent_queries, run_query
from research_agent.log import configure_logging

QUERIES_PATH = Path("eval/agent_queries.jsonl")
FILE_ENCODING = "utf-8"
SUCCESS_EXIT_CODE = 0
FAILURE_EXIT_CODE = 1
LOADING_MESSAGE = "Loading the index and models…"


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse --only and --output."""
    parser = argparse.ArgumentParser(prog="python src/run_e2e.py", description="Run the end-to-end agent queries.")
    parser.add_argument("--only", action="append", default=[], help="run only this query name; repeatable")
    parser.add_argument("--output", type=Path, help="write the answers to this Markdown file")
    return parser.parse_args(argv)


def print_result(console: Console, result: QueryResult) -> None:
    """Print one query's answer and outcome."""
    console.rule(result.name)
    console.print(f"Q: {result.question}", markup=False, highlight=False)
    console.print(f"Tools: {', '.join(result.tools_used) or 'none'}", markup=False, highlight=False)
    console.print(Markdown(result.answer))
    if result.passed:
        console.print("PASSED", style="green")
    else:
        console.print(f"FAILED: {'; '.join(result.failures)}", style="red", markup=False)


async def run_all(graph: AgentGraph, queries: list[AgentQuery], console: Console) -> list[QueryResult]:
    """Run the queries one after another, printing each result as it arrives."""
    results = []
    for query in queries:
        with console.status(f"Running {query.name}…"):
            result = await run_query(graph, query)
        print_result(console, result)
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the selected queries and return 0 when all passed."""
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    settings = Settings()
    configure_logging(settings.log_path, verbose=False)
    console = Console()
    problems = startup_problems(settings)
    if problems:
        for problem in problems:
            console.print(problem, markup=False, highlight=False)
        return INDEX_NOT_READY_EXIT_CODE
    all_queries = load_agent_queries(QUERIES_PATH)
    queries = [query for query in all_queries if not arguments.only or query.name in arguments.only]
    qdrant_client = open_qdrant(settings)
    try:
        with console.status(LOADING_MESSAGE):
            graph = build_agent(settings, qdrant_client)
        results = asyncio.run(run_all(graph, queries, console))
    finally:
        qdrant_client.close()
    if arguments.output is not None:
        arguments.output.write_text(format_report(results), encoding=FILE_ENCODING)
    passed_count = sum(result.passed for result in results)
    console.rule(f"{passed_count}/{len(results)} passed")
    return SUCCESS_EXIT_CODE if passed_count == len(results) else FAILURE_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
