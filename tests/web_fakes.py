"""A scripted stand-in for AsyncTavilyClient, shared by the web_search and tool-logging tests."""

import asyncio
from typing import Any


class ScriptedTavilyClient:
    """Stands in for AsyncTavilyClient: records each search and replays a response, a delay or an exception."""

    def __init__(
        self,
        results: list[dict[str, Any]] | None = None,
        delay_s: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        """Script the response; an error is raised instead of returning results."""
        self.results = results or []
        self.delay_s = delay_s
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def search(self, query: str, **options: Any) -> dict[str, Any]:
        """Record the call, then wait, fail or return the scripted results in Tavily's response shape."""
        self.calls.append({"query": query, **options})
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return {"query": query, "results": self.results}
