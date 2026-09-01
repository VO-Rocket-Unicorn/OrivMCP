from typing import Annotated

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from oriv_mcp.schemas.device_class import (
    DeviceClassNode,
    GetDeviceClassOutput,
    ListDeviceClassesOutput,
    SearchDeviceClassesOutput,
)
from oriv_mcp.server.app import mcp_app
from oriv_mcp.taxonomy import IndexEntry, UnknownDeviceClassError, taxonomy

MIN_LIST_DEPTH = 1
DEFAULT_LIST_DEPTH = 1
MAX_LIST_DEPTH = 3

MIN_SEARCH_LIMIT = 1
DEFAULT_SEARCH_LIMIT = 10

# Lower sorts first.
RANK_EXACT_NAME = 0
RANK_NAME_CONTAINS = 1
RANK_DESCRIPTION_CONTAINS = 2

UNKNOWN_ID_HINT = (
    "Call list_device_classes with no parent_id to see the top-level classes, "
    "or search_device_classes to find one by keyword."
)


def _to_node(entry: IndexEntry) -> DeviceClassNode:
    return DeviceClassNode(
        id=entry.id,
        name=entry.name,
        description=entry.description,
        child_count=entry.child_count,
        path=list(entry.path),
    )


def _to_nodes(entries: list[IndexEntry]) -> list[DeviceClassNode]:
    return [_to_node(entry) for entry in entries]


def _require_known(class_id: str, parameter: str) -> None:
    """Reject an unknown id.

    `ToolError` rather than a bare exception: the SDK puts its message in the
    is_error result for the model to read and recover from, instead of
    withholding it as an unexpected crash.
    """
    try:
        taxonomy.entry(class_id)
    except UnknownDeviceClassError:
        raise ToolError(
            f"Unknown device class {parameter}: {class_id!r}. {UNKNOWN_ID_HINT}"
        ) from None


def _match_rank(entry: IndexEntry, query: str) -> int | None:
    """Rank a node against a lowercased query, or None if it does not match."""
    name = entry.name.lower()
    if name == query:
        return RANK_EXACT_NAME
    if query in name:
        return RANK_NAME_CONTAINS
    if query in entry.description.lower():
        return RANK_DESCRIPTION_CONTAINS
    return None


@mcp_app.tool(
    name="list_device_classes",
    description=(
        "Browse one level of the device-class tree. Call with no parent_id to "
        "see the top-level classes, then call again with a chosen id to go deeper."
    ),
)
def list_device_classes(
    parent_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Class to list beneath. Omit for the top-level classes.",
        ),
    ] = None,
    depth: Annotated[
        int,
        Field(
            default=DEFAULT_LIST_DEPTH,
            ge=MIN_LIST_DEPTH,
            le=MAX_LIST_DEPTH,
            description="How many levels below parent_id to return. 1 is direct children only.",
        ),
    ] = DEFAULT_LIST_DEPTH,
    cursor: Annotated[
        str | None,
        Field(
            default=None,
            description="Reserved for pagination. Always returns nextCursor null today.",
        ),
    ] = None,
) -> ListDeviceClassesOutput:
    if parent_id is not None:
        _require_known(parent_id, "parent_id")
    return ListDeviceClassesOutput(
        nodes=_to_nodes(taxonomy.descendants_of(parent_id, depth)),
        next_cursor=None,
    )


@mcp_app.tool(
    name="search_device_classes",
    description=(
        "Find device classes by keyword when a term from the datasheet is "
        "already known. Faster than browsing."
    ),
)
def search_device_classes(
    query: Annotated[
        str,
        Field(description="Case-insensitive substring matched against name and description."),
    ],
    limit: Annotated[
        int,
        Field(
            default=DEFAULT_SEARCH_LIMIT,
            ge=MIN_SEARCH_LIMIT,
            description="Maximum number of matches to return.",
        ),
    ] = DEFAULT_SEARCH_LIMIT,
) -> SearchDeviceClassesOutput:
    normalized = query.strip().lower()
    if not normalized:
        return SearchDeviceClassesOutput(nodes=[])

    ranked: list[tuple[int, str, IndexEntry]] = []
    for entry in taxonomy.entries():
        rank = _match_rank(entry, normalized)
        if rank is not None:
            # Name breaks ties so equal-rank results come back in a stable order.
            ranked.append((rank, entry.name, entry))
    ranked.sort(key=lambda scored: (scored[0], scored[1]))

    return SearchDeviceClassesOutput(
        nodes=_to_nodes([entry for _, _, entry in ranked[:limit]])
    )


@mcp_app.tool(
    name="get_device_class",
    description=(
        "Show one class with its parent, children, and siblings. Use to confirm "
        "a class before committing to it — the siblings are the classes most "
        "likely to be confused with it."
    ),
)
def get_device_class(
    id: Annotated[str, Field(description="Id of the device class to inspect.")],
) -> GetDeviceClassOutput:
    _require_known(id, "id")
    return GetDeviceClassOutput(
        node=_to_node(taxonomy.entry(id)),
        ancestors=_to_nodes(taxonomy.ancestors_of(id)),
        children=_to_nodes(taxonomy.children_of(id)),
        siblings=_to_nodes(taxonomy.siblings_of(id)),
    )
