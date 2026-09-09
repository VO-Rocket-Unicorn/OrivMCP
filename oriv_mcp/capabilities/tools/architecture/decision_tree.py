from typing import Annotated

from mcp.server.mcpserver import Context
from pydantic import Field

from oriv_mcp.capabilities.tools.tags import ARCHITECTURE_TAG, tags_meta
from oriv_mcp.clients import architecture_selection_client
from oriv_mcp.clients.odas import ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT
from oriv_mcp.schemas.architecture_selection import (
    ArchitectureDetail,
    DecisionNode,
    DecisionTree,
)
from oriv_mcp.server.app import mcp_app
from oriv_mcp.utils.request_headers import require_secret_header

DEVICE_CLASS_KEY_DESCRIPTION = "Device class key identifying the decision tree / taxonomy (e.g. 'adc.sar')."
ARCHITECTURE_META = tags_meta(ARCHITECTURE_TAG)
ROOT_NODE_ID = "root"


@mcp_app.tool(
    name="get_decision_tree",
    description=(
        "Fetch the FULL AI decision tree for a device class in one call — every question "
        "node keyed by id, plus root_question_id to start from. Walk it YOURSELF in memory, "
        "one question at a time: start at nodes[root_question_id], ask its `question`, "
        "match the reply to one answer's `value`, then move to nodes[that answer's `next`] "
        "and repeat. When an answer's `next` is null, you've reached a leaf — call "
        "resolve_architecture with that answer's `resolves_toward` to get the final "
        "architecture. Prefer get_decision_tree_node instead if you'd rather fetch one "
        "question at a time than hold the whole tree yourself."
    ),
    meta=ARCHITECTURE_META,
)
async def get_decision_tree(
    ctx: Context,
    device_class_key: Annotated[str, Field(description=DEVICE_CLASS_KEY_DESCRIPTION)],
) -> DecisionTree:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    return await architecture_selection_client.get_decision_tree(token, device_class_key)


@mcp_app.tool(
    name="get_decision_tree_node",
    description=(
        "Fetch ONE question node of a device class's AI decision tree — call-per-question, "
        "instead of the whole tree. Call with node_id='root' to get the first question; "
        "answer it, then call again with that answer's `next` as node_id to get the "
        "following question, and repeat. When an answer's `next` is null, you've reached a "
        "leaf — call resolve_architecture with that answer's `resolves_toward` to get the "
        "final architecture. Do NOT call get_decision_tree first; this walks the tree on "
        "its own, one node per call."
    ),
    meta=ARCHITECTURE_META,
)
async def get_decision_tree_node(
    ctx: Context,
    device_class_key: Annotated[str, Field(description=DEVICE_CLASS_KEY_DESCRIPTION)],
    node_id: Annotated[
        str,
        Field(
            description=(
                "'root' to start the walk, or a previous answer's `next` value to continue it."
            )
        ),
    ] = ROOT_NODE_ID,
) -> DecisionNode:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    return await architecture_selection_client.get_decision_tree_node(
        token, device_class_key, node_id
    )


@mcp_app.tool(
    name="resolve_architecture",
    description=(
        "Resolve a decision-tree leaf's `resolves_toward` value to its full architecture "
        "record. Call this once get_decision_tree's walk reaches a leaf (an answer whose "
        "`next` is null) — architecture_name is that answer's `resolves_toward`."
    ),
    meta=ARCHITECTURE_META,
)
async def resolve_architecture(
    ctx: Context,
    device_class_key: Annotated[str, Field(description=DEVICE_CLASS_KEY_DESCRIPTION)],
    architecture_name: Annotated[
        str,
        Field(
            description="The `resolves_toward` value from the leaf answer reached while walking the decision tree."
        ),
    ],
) -> ArchitectureDetail:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    return await architecture_selection_client.resolve_architecture(
        token, device_class_key, architecture_name
    )
