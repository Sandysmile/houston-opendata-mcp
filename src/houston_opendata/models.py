"""Pydantic models and validated types for tool inputs.

Two layers of validation, on purpose:

- Pydantic (here) enforces shape and size: lengths, ranges, list and dict sizes.
  Input that fails is rejected before any tool code runs.
- portal.py, gis.py and conditions.py enforce format (UUIDs, slugs, street
  addresses, City ZIP codes) and return an `error` with a fix-it `hint`, so the
  agent can correct itself instead of stopping.

Both the MCP tools and the Streamlit chat agent use these models.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

# ── Shared input types ────────────────────────────────────────────────────────

SearchText = Annotated[
    str,
    Field(
        max_length=200,
        description="Keywords, such as 'council district'. Empty lists everything.",
    ),
]

CatalogName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        description="A department or topic `name` from houston_browse_catalog.",
    ),
]

DatasetRef = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        description="Dataset `name` or `id` from houston_search_datasets.",
    ),
]

ResourceId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        description="Resource `id` (UUID) from houston_get_dataset.",
    ),
]

ColumnName = Annotated[str, Field(min_length=1, max_length=100)]

StreetAddress = Annotated[
    str,
    Field(
        min_length=3,
        max_length=200,
        description="Street address with a house number, such as 901 Bagby St.",
    ),
]

ZipCode = Annotated[
    str,
    Field(
        max_length=10,
        description="Houston ZIP code, such as 77002. Omit for downtown.",
    ),
]

RecordFilters = Annotated[
    dict[str, Any],
    Field(
        max_length=10,
        description='Exact matches by column, such as {"COUNCIL_DISTRICT": "K"}. '
        "Values must match exactly; check sample_rows in houston_describe_table.",
    ),
]

ColumnList = Annotated[
    list[ColumnName],
    Field(max_length=50, description="Columns to return. Omit to return all."),
]


# ── Structured parameters ─────────────────────────────────────────────────────


class PaginationParams(BaseModel):
    """Reusable pagination inputs for list-style tools."""

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return (1–100).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip from the start of the result set.",
    )


class SummaryParams(BaseModel):
    """Group matching rows by one column, counting them and optionally summing a
    numeric column. The server reads the rows itself, so the agent gets totals
    without paging through the table."""

    count_by: ColumnName = Field(
        description="Column to group by, such as DEPARTMENT or COUNCIL_DISTRICT.",
    )
    sum_of: ColumnName | None = Field(
        default=None,
        description="Optional numeric column to total and average per group, "
        "such as ANNUAL_SALARY.",
    )
    top: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Largest groups to return (1–100).",
    )
