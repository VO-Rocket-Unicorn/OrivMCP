"""Client for ODAS's requirement-tree reads. Contract: temp/requirements-tools.md.

Read-only by construction: there is no method here that writes. A parent is
confirmed by a human through `PATCH …/requirements/{id}/parent`, and these
tools must not offer a path around that.

Two domain rules are resolved here rather than asked of the caller — the
legal-parent altitude bound, and excluding a requirement's own subtree. A rule
enforced in the tool cannot be violated by the model, and a candidate that
never arrives costs nothing.
"""

from urllib.parse import quote

import anyio
import httpx
from pydantic import SecretStr

from oriv_mcp.clients.base import ApiClient
from oriv_mcp.clients.odas import BASE_URL_ENV_VAR, CREDENTIAL_HINT
from oriv_mcp.schemas.requirement import (
    LEGAL_PARENT_ALTITUDES,
    ChildAltitude,
    OdasAncestors,
    OdasRequirementDetail,
    OdasRequirementPage,
    OdasRequirementRow,
    RequirementDetail,
    RequirementListing,
    RequirementNode,
    RequirementType,
)

SERVICE_LABEL = "requirements API"

# ---- query params on GET …/requirements ----
PARENT_ID_PARAM = "parentId"
ALTITUDE_PARAM = "altitude"
QUERY_PARAM = "q"
EXCLUDE_SUBTREE_PARAM = "excludeSubtreeOf"
IN_SUBTREE_PARAM = "inSubtreeOf"
SORT_PARAM = "sort"
VIEW_PARAM = "view"
TYPE_PARAM = "type"
PAGE_PARAM = "page"
LIMIT_PARAM = "limit"

COMPACT_VIEW = "compact"
ALTITUDE_SEPARATOR = ","

# Sorting is opt-in at ODAS, and left off the order is explicitly unspecified —
# which over more than one page means silently skipped and repeated rows. Every
# read here asks for it; there is no case where the unordered default is wanted.
SORT_BY_NAME = "name"

# The literal ODAS wants for "requirements with no parent". `parentId=` is
# indistinguishable from a caller that built the query string wrong, and
# returning the whole project in that case is the kind of bug nobody notices
# until a model has been shown every requirement there is.
NO_PARENT = "none"

# Ids go in a path segment whole — none of them may be read as a separator.
ID_SAFE_CHARACTERS = ""


def _first_failure(group: BaseExceptionGroup) -> BaseException:
    """Unwrap a task group's `ExceptionGroup` back to a single exception.

    The fan-out raises `ToolError`s, whose whole point is that the model reads
    the message; delivered inside a group they would reach the SDK as an
    unexpected crash instead.
    """
    failure: BaseException = group
    while isinstance(failure, BaseExceptionGroup):
        failure = failure.exceptions[0]
    return failure


class RequirementClient(ApiClient):
    """Read-only access to one project's requirement tree."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        projects_url: str,
        requirements_path: str,
        ancestors_path: str,
    ) -> None:
        super().__init__(
            http_client=http_client,
            service_label=SERVICE_LABEL,
            base_url_env_var=BASE_URL_ENV_VAR,
            credential_hint=CREDENTIAL_HINT,
        )
        self._projects_url = projects_url
        self._requirements_path = requirements_path
        self._ancestors_path = ancestors_path

    # ---- urls ----
    def _collection_url(self, project_id: str) -> str:
        project = quote(project_id, safe=ID_SAFE_CHARACTERS)
        return f"{self._projects_url}/{project}{self._requirements_path}"

    def _item_url(self, project_id: str, requirement_id: str) -> str:
        requirement = quote(requirement_id, safe=ID_SAFE_CHARACTERS)
        return f"{self._collection_url(project_id)}/{requirement}"

    def _ancestors_url(self, project_id: str, requirement_id: str) -> str:
        return f"{self._item_url(project_id, requirement_id)}{self._ancestors_path}"

    # ---- translation ----
    @staticmethod
    def _altitudes(child_altitude: ChildAltitude | None) -> str | None:
        """The altitudes that may legally parent a child at this altitude.

        None when the caller states no child altitude — that, and only that,
        is when an `unknown`-altitude requirement is offered as a candidate.
        """
        if child_altitude is None:
            return None
        legal = LEGAL_PARENT_ALTITUDES[child_altitude]
        return ALTITUDE_SEPARATOR.join(altitude.value for altitude in legal)

    @staticmethod
    def _to_node(row: OdasRequirementRow, with_path: bool) -> RequirementNode:
        """Trim one ODAS row to the node the tools return.

        The path is dropped unless asked for: every compact row carries it, but
        it is only worth its tokens on a search hit, whose position the caller
        has not walked to.
        """
        return RequirementNode(
            id=row.id,
            name=row.name,
            label=row.label,
            statement=row.statement,
            truncated=row.truncated,
            level=row.level,
            type=row.type,
            is_atomic=row.is_atomic,
            altitude=row.altitude,
            child_count=row.child_count,
            path=row.path if with_path else None,
        )

    @classmethod
    def _to_listing(
        cls,
        odas_page: OdasRequirementPage,
        page: int,
        limit: int,
        with_paths: bool = False,
    ) -> RequirementListing:
        """Wrap ODAS's rows in the envelope the traversal tools return.

        `hasMore` is redundant against `page * limit < total` and computed here
        anyway: it takes the arithmetic off the model's path, and with it one
        way for the model to stop paging early by mistake.
        """
        # The window ODAS says it applied, falling back to the one asked for.
        applied_page = odas_page.page or page
        applied_limit = odas_page.limit or limit
        return RequirementListing(
            items=[cls._to_node(row, with_paths) for row in odas_page.items],
            page=applied_page,
            limit=applied_limit,
            total=odas_page.total,
            has_more=applied_page * applied_limit < odas_page.total,
        )

    # ---- reads ----
    async def _list(
        self,
        token: SecretStr,
        project_id: str,
        page: int,
        limit: int,
        *,
        parent_id: str | None = None,
        query: str | None = None,
        child_altitude: ChildAltitude | None = None,
        requirement_type: RequirementType | None = None,
        exclude_id: str | None = None,
        in_subtree_of: str | None = None,
    ) -> OdasRequirementPage:
        return await self.get(
            self._collection_url(project_id),
            OdasRequirementPage,
            token,
            {
                PARENT_ID_PARAM: parent_id,
                QUERY_PARAM: query,
                ALTITUDE_PARAM: self._altitudes(child_altitude),
                TYPE_PARAM: requirement_type.value if requirement_type else None,
                EXCLUDE_SUBTREE_PARAM: exclude_id,
                IN_SUBTREE_PARAM: in_subtree_of,
                SORT_PARAM: SORT_BY_NAME,
                VIEW_PARAM: COMPACT_VIEW,
                PAGE_PARAM: page,
                LIMIT_PARAM: limit,
            },
        )

    async def _ancestor_ids(
        self, token: SecretStr, project_id: str, requirement_id: str
    ) -> list[str]:
        """The ancestor path as ids, root first — the same spelling the compact
        row uses, so a path means one thing whichever tool produced it."""
        ancestors = await self.get(
            self._ancestors_url(project_id, requirement_id), OdasAncestors, token
        )
        return [ancestor.id for ancestor in ancestors.items]

    # ---- what the tools call ----
    async def roots(
        self,
        token: SecretStr,
        project_id: str,
        child_altitude: ChildAltitude | None,
        exclude_id: str | None,
        page: int,
        limit: int,
    ) -> RequirementListing:
        odas_page = await self._list(
            token,
            project_id,
            page,
            limit,
            parent_id=NO_PARENT,
            child_altitude=child_altitude,
            exclude_id=exclude_id,
        )
        return self._to_listing(odas_page, page, limit)

    async def children(
        self,
        token: SecretStr,
        project_id: str,
        requirement_id: str,
        child_altitude: ChildAltitude | None,
        exclude_id: str | None,
        page: int,
        limit: int,
    ) -> RequirementListing:
        odas_page = await self._list(
            token,
            project_id,
            page,
            limit,
            parent_id=requirement_id,
            child_altitude=child_altitude,
            exclude_id=exclude_id,
        )
        return self._to_listing(odas_page, page, limit)

    async def search(
        self,
        token: SecretStr,
        project_id: str,
        query: str,
        child_altitude: ChildAltitude | None,
        requirement_type: RequirementType | None,
        exclude_id: str | None,
        in_subtree_of: str | None,
        page: int,
        limit: int,
    ) -> RequirementListing:
        odas_page = await self._list(
            token,
            project_id,
            page,
            limit,
            query=query,
            child_altitude=child_altitude,
            requirement_type=requirement_type,
            exclude_id=exclude_id,
            in_subtree_of=in_subtree_of,
        )
        return self._to_listing(odas_page, page, limit, with_paths=True)

    async def node(
        self, token: SecretStr, project_id: str, requirement_id: str
    ) -> RequirementDetail:
        """One requirement in full, with its path.

        The record and the ancestor chain are independent reads, so they go out
        together. Show carries everything else, path included once these two
        land.
        """
        detail: OdasRequirementDetail | None = None
        path: list[str] = []

        async def read_detail() -> None:
            nonlocal detail
            detail = await self.get(
                self._item_url(project_id, requirement_id),
                OdasRequirementDetail,
                token,
            )

        async def read_path() -> None:
            nonlocal path
            path = await self._ancestor_ids(token, project_id, requirement_id)

        try:
            async with anyio.create_task_group() as reads:
                reads.start_soon(read_detail)
                reads.start_soon(read_path)
        except BaseExceptionGroup as group:
            raise _first_failure(group) from None

        record: OdasRequirementDetail = detail  # type: ignore[assignment]

        return RequirementDetail(
            id=record.id,
            name=record.name,
            label=record.label,
            statement=record.statement,
            rationale=record.rationale,
            level=record.level,
            type=record.type,
            is_atomic=record.is_atomic,
            altitude=record.altitude,
            parent_id=record.confirmed_parent_id,
            child_count=record.child_count,
            path=path,
        )
