from pydantic import BaseModel, ConfigDict, Field


class DeviceClassNode(BaseModel):
    """The shape every device-class tool returns for a node.

    `children` is deliberately never inlined — children arrive from the next
    `list_device_classes` call or from `get_device_class`.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique id of the device class.")
    name: str = Field(description="Human-readable name of the device class.")
    description: str = Field(description="What this device class covers.")
    child_count: int = Field(
        alias="childCount",
        description=(
            "Number of direct children. 0 means leaf — use this to tell a leaf "
            "from a branch that simply has not been expanded yet."
        ),
    )
    path: list[str] = Field(
        description="Ids from the root of the taxonomy down to this node, inclusive."
    )


class ListDeviceClassesOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nodes: list[DeviceClassNode] = Field(
        description=(
            "Nodes within the requested depth, breadth-first. Flat, not nested: "
            "rebuild the hierarchy from each node's `path`."
        )
    )
    next_cursor: str | None = Field(
        default=None,
        alias="nextCursor",
        description=(
            "Always null today — the tree is small enough to return whole. "
            "Reserved so the contract survives a larger taxonomy."
        ),
    )


class SearchDeviceClassesOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nodes: list[DeviceClassNode] = Field(
        description=(
            "Matches ordered by relevance: exact name, then name substring, "
            "then description substring. Empty when nothing matches."
        )
    )


class GetDeviceClassOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    node: DeviceClassNode = Field(description="The requested device class.")
    ancestors: list[DeviceClassNode] = Field(
        description="Chain from the root down to the parent, root first. Empty for a top-level class."
    )
    children: list[DeviceClassNode] = Field(
        description="Direct children. Empty for a leaf."
    )
    siblings: list[DeviceClassNode] = Field(
        description=(
            "Classes sharing the same parent, excluding this one — the classes "
            "most likely to be confused with it."
        )
    )
