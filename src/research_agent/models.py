"""Data that crosses module boundaries (LLD section 5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ChunkKind = Literal["text", "risk_factor", "table"]
ToolName = Literal["search_10k", "web_search", "calculator"]
MAX_PLAN_STEPS = 6


class Chunk(BaseModel):
    """One retrievable unit of the filing: a risk factor, a subsection part or a table."""

    seq: int  # global document order, from 1; citation ID is f"D{seq}"
    kind: ChunkKind
    section_id: str  # stable section key: "item:1A", "item:7", "note:5"
    section_path: list[str]  # breadcrumb: ["Part II", "Item 7. ...", "Gross Margin"]
    unit: str  # risk-factor title or subsection heading
    position: int  # 1-based order of the unit within its section
    page_start: int  # printed page numbers, taken from the page footers
    page_end: int
    cross_refs: list[str]  # section_ids this chunk refers to
    text: str  # body text; tables as Markdown


class Manifest(BaseModel):
    """What built the index; the CLI refuses to start when it is missing or doesn't match the configuration."""

    doc_sha256: str
    parser_version: str
    dense_model: str
    sparse_model: str
    chunk_count: int
    built_at: datetime


class Evidence(BaseModel):
    """A citable source produced by a tool call; the renderer prints its source line under Sources."""

    id: str  # "D137", "W3f9a1c", "C7b2e04"
    kind: Literal["doc", "web", "calc"]
    source: str  # the line rendered under Sources, without the [ID] marker


class PlanStep(BaseModel):
    """One step of the plan: what it establishes and which tool it uses."""

    goal: str = Field(description="What this step establishes.")
    tool: ToolName | None = Field(description="The tool this step uses, or null for reasoning over earlier results.")


class Plan(BaseModel):
    """Plan from the plan node, shown to the user before any tool runs."""

    steps: list[PlanStep] = Field(min_length=1, max_length=MAX_PLAN_STEPS)
