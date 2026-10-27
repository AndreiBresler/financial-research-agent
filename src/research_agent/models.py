"""Data that crosses module boundaries (LLD section 5)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Chunk(BaseModel):
    """One retrievable unit of the filing: a risk factor, a subsection part or a table."""

    seq: int  # global document order, from 1; citation ID is f"D{seq}"
    kind: Literal["text", "risk_factor", "table"]
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
