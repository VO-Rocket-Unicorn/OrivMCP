"""Requirement-tree traversal. Contract: temp/requirements-tools.md.

Four read-only tools that let a model walk a project's requirement tree
instead of being handed the whole thing: fetch one level, score it, descend
only where a score justifies it. A run then costs the branches it explored
rather than the field.

Argument names are the contract's own (`forChildAltitude`, `excludeId`), not
this codebase's casing — the sidecar binds against them. The project is the
exception: it is fixed for a session, so it arrives on the
`X-Project-Id` header beside the credential rather than as an argument
the model has to carry through every call.
"""

from typing import Annotated

from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from oriv_mcp.capabilities.tools.tags import REQUIREMENTS_TAG, tags_meta
from oriv_mcp.clients import requirement_client
from oriv_mcp.clients.odas import ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT
from oriv_mcp.schemas.requirement import (
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    MAX_LIMIT,
    MIN_LIMIT,
    MIN_PAGE,
    ChildAltitude,
    RequirementDetail,
    RequirementListing,
    RequirementType,
)
from oriv_mcp.server.app import mcp_app
from oriv_mcp.utils.request_headers import (
    PROJECT_ID_HEADER,
    PROJECT_ID_HINT,
    require_header,
    require_secret_header,
)

# Nothing here writes. Declared so a client that gates side effects — conduit's
# plan mode among them — can permit these without asking.
READ_ONLY = ToolAnnotations(readOnlyHint=True)
REQUIREMENT_META = tags_meta(REQUIREMENTS_TAG)

# ---- arguments shared by the listing tools ----
RequirementId = Annotated[
    str, Field(min_length=1, description="Id of the requirement to read.")
]
ForChildAltitude = Annotated[
    ChildAltitude | None,
    Field(
        default=None,
        description=(
            "Altitude of the requirement being PLACED. Only requirements that "
            "may legally parent it are returned: a parent must sit at the same "
            "altitude or coarser. Omit it and everything comes back, including "
            "requirements whose altitude is still unknown."
        ),
    ),
]
ExcludeId = Annotated[
    str | None,
    Field(
        default=None,
        description=(
            "A requirement to omit together with its entire subtree. Pass the "
            "requirement being placed: it cannot parent itself, and a descendant "
            "of it cannot parent it either — that closes a cycle, which ODAS "
            "refuses, so such a candidate is one no human could ever accept."
        ),
    ),
]
InSubtreeOf = Annotated[
    str | None,
    Field(
        default=None,
        description=(
            "Restrict the search to one branch: only requirements beneath this "
            "id, at any depth. Use it to search inside a subtree that already "
            "looks right, instead of across the whole project."
        ),
    ),
]
Page = Annotated[
    int,
    Field(default=DEFAULT_PAGE, ge=MIN_PAGE, description="Which page to read, 1-based."),
]
Limit = Annotated[
    int,
    Field(
        default=DEFAULT_LIMIT,
        ge=MIN_LIMIT,
        le=MAX_LIMIT,
        description="Page size.",
    ),
]


@mcp_app.tool(
    name="requirement_tree_roots",
    description=(
        "Start here. The top of the project's requirement tree: requirements "
        "with no parent. When every result has childCount 0 and total covers "
        "the whole project, the project has no hierarchy yet — use "
        "requirement_tree_search instead of descending."
    ),
    annotations=READ_ONLY,
    meta=REQUIREMENT_META,
)
async def requirement_tree_roots(
    ctx: Context,
    forChildAltitude: ForChildAltitude = None,
    excludeId: ExcludeId = None,
    page: Page = DEFAULT_PAGE,
    limit: Limit = DEFAULT_LIMIT,
) -> RequirementListing:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    project_id = require_header(ctx, PROJECT_ID_HEADER, PROJECT_ID_HINT)
    return await requirement_client.roots(
        token, project_id, forChildAltitude, excludeId, page, limit
    )


@mcp_app.tool(
    name="requirement_tree_children",
    description=(
        "Descend one level. The direct children of one requirement. Call it on "
        "a candidate that scored well and whose childCount is above zero. One "
        "level only — depth is your decision, made from the scores you have "
        "just seen. A leaf returns an empty list, not an error."
    ),
    annotations=READ_ONLY,
    meta=REQUIREMENT_META,
)
async def requirement_tree_children(
    ctx: Context,
    requirementId: RequirementId,
    forChildAltitude: ForChildAltitude = None,
    excludeId: ExcludeId = None,
    page: Page = DEFAULT_PAGE,
    limit: Limit = DEFAULT_LIMIT,
) -> RequirementListing:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    project_id = require_header(ctx, PROJECT_ID_HEADER, PROJECT_ID_HINT)
    return await requirement_client.children(
        token, project_id, requirementId, forChildAltitude, excludeId, page, limit
    )


@mcp_app.tool(
    name="requirement_tree_search",
    description=(
        "Find candidates by keyword, with each hit's ancestor path from the "
        "root. Use it when the tree is flat, or to jump into a deep branch "
        "without walking every level above it; pass inSubtreeOf to search "
        "within one branch instead of the whole project. Every word given must "
        "match, so send two or three distinctive words rather than the whole "
        "statement, and drop words if nothing comes back. Results are unranked, "
        "in match order, so page further before concluding nothing fits. No "
        "match is an empty list, not an error."
    ),
    annotations=READ_ONLY,
    meta=REQUIREMENT_META,
)
async def requirement_tree_search(
    ctx: Context,
    query: Annotated[
        str,
        Field(
            min_length=1,
            description="Free text matched against each requirement's statement and label.",
        ),
    ],
    forChildAltitude: ForChildAltitude = None,
    type: Annotated[
        RequirementType | None,
        Field(
            default=None,
            description="Keep only requirements of this type. Omit to search both.",
        ),
    ] = None,
    excludeId: ExcludeId = None,
    inSubtreeOf: InSubtreeOf = None,
    page: Page = DEFAULT_PAGE,
    limit: Limit = DEFAULT_LIMIT,
) -> RequirementListing:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    project_id = require_header(ctx, PROJECT_ID_HEADER, PROJECT_ID_HINT)
    return await requirement_client.search(
        token,
        project_id,
        query,
        forChildAltitude,
        type,
        excludeId,
        inSubtreeOf,
        page,
        limit,
    )


@mcp_app.tool(
    name="requirement_tree_node",
    description=(
        "The full, untruncated statement and rationale for one requirement, "
        "with its path from the root. Call it before committing to a candidate "
        "whose listed statement came back truncated."
    ),
    annotations=READ_ONLY,
    meta=REQUIREMENT_META,
)
async def requirement_tree_node(
    ctx: Context,
    requirementId: RequirementId,
) -> RequirementDetail:
    token = require_secret_header(ctx, ODAS_TOKEN_HEADER, ODAS_TOKEN_HINT)
    project_id = require_header(ctx, PROJECT_ID_HEADER, PROJECT_ID_HINT)
    return await requirement_client.node(token, project_id, requirementId)
