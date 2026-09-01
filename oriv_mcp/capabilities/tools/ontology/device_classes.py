from typing import Annotated

from pydantic import Field

from oriv_mcp.clients import device_class_client
from oriv_mcp.schemas.device_class import (
    GetDeviceClassOutput,
    ListDeviceClassesOutput,
    SearchDeviceClassesOutput,
)
from oriv_mcp.server.app import mcp_app

MIN_LIST_DEPTH = 1
DEFAULT_LIST_DEPTH = 1
MAX_LIST_DEPTH = 3

MIN_SEARCH_LIMIT = 1
DEFAULT_SEARCH_LIMIT = 10


@mcp_app.tool(
    name="list_device_classes",
    description=(
        "Browse one level of the device-class tree. Call with no parent_id to "
        "see the top-level classes, then call again with a chosen id to go deeper."
    ),
)
async def list_device_classes(
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
            description="Opaque pagination cursor from a previous nextCursor.",
        ),
    ] = None,
) -> ListDeviceClassesOutput:
    return await device_class_client.list_device_classes(parent_id, depth, cursor)


@mcp_app.tool(
    name="search_device_classes",
    description=(
        "Find device classes by keyword when a term from the datasheet is "
        "already known. Faster than browsing."
    ),
)
async def search_device_classes(
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
    return await device_class_client.search_device_classes(query, limit)


@mcp_app.tool(
    name="get_device_class",
    description=(
        "Show one class with its parent, children, and siblings. Use to confirm "
        "a class before committing to it — the siblings are the classes most "
        "likely to be confused with it."
    ),
)
async def get_device_class(
    id: Annotated[str, Field(description="Id of the device class to inspect.")],
) -> GetDeviceClassOutput:
    return await device_class_client.get_device_class(id)
