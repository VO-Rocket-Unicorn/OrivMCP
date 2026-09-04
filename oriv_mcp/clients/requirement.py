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
    Altitude,
    ChildAltitude,
    OdasAncestors,
    OdasRequirementDetail,
    OdasRequirementPage,
    OdasRequirementRow,
    RequirementDetail,
    RequirementListing,
    RequirementNode,
    RequirementType,
    altitude_of,
)

SERVICE_LABEL = "requirements API"

# ---- query params on GET …/requirements ----
PARENT_ID_PARAM = "parentId"
ALTITUDE_PARAM = "altitude"
QUERY_PARAM = "q"
EXCLUDE_SUBTREE_PARAM = "excludeSubtreeOf"
VIEW_PARAM = "view"
TYPE_PARAM = "type"
PAGE_PARAM = "page"
LIMIT_PARAM = "limit"

COMPACT_VIEW = "compact"
ALTITUDE_SEPARATOR = ","

# The literal ODAS wants for "requirements with no parent". `parentId=` is
# indistinguishable from a caller that built the query string wrong, and
# returning the whole project in that case is the kind of bug nobody notices
# until a model has been shown every requirement there is.
NO_PARENT = "none"

# Ids go in a path segment whole — none of them may be read as a separator.
ID_SAFE_CHARACTERS = ""

# A page of search hits costs one ancestors call each. Run them together, but
# not so many at once that a full page opens a hundred connections.
ANCESTOR_CONCURRENCY = 5

# Cheapest form of "how many children does this have": ask for one row and read
# the total off the envelope.
COUNT_ONLY_PAGE = 1
COUNT_ONLY_LIMIT = 1


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
    def _altitude_of(row: OdasRequirementRow | OdasRequirementDetail) -> Altitude:
        """ODAS's computed altitude, derived locally only if it sent none."""
        return row.altitude or altitude_of(row.level, row.is_atomic)

    @classmethod
    def _to_node(
        cls, row: OdasRequirementRow, path: list[str] | None = None
    ) -> RequirementNode:
        return RequirementNode(
            id=row.id,
            name=row.name,
            label=row.label,
            statement=row.statement,
            truncated=row.truncated,
            level=row.level,
            type=row.type,
            is_atomic=row.is_atomic,
            altitude=cls._altitude_of(row),
            child_count=row.child_count,
            path=path,
        )

    @classmethod
    def _to_listing(
        cls,
        odas_page: OdasRequirementPage,
        page: int,
        limit: int,
        paths: list[list[str]] | None = None,
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
            items=[
                cls._to_node(row, paths[index] if paths else None)
                for index, row in enumerate(odas_page.items)
            ],
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
                VIEW_PARAM: COMPACT_VIEW,
                PAGE_PARAM: page,
                LIMIT_PARAM: limit,
            },
        )

    async def _ancestor_names(
        self, token: SecretStr, project_id: str, requirement_id: str
    ) -> list[str]:
        ancestors = await self.get(
            self._ancestors_url(project_id, requirement_id), OdasAncestors, token
        )
        return [ancestor.name for ancestor in ancestors.items]

    async def _paths_for(
        self, token: SecretStr, project_id: str, rows: list[OdasRequirementRow]
    ) -> list[list[str]]:
        """Fetch each hit's ancestor names, several at a time.

        A search hit has no known position in the tree, and the compact row
        does not carry one. A failure here is left to propagate: a hit shown
        without its path, or with a stale one, would be placed against a tree
        that does not look the way the model was told it does.
        """
        paths: list[list[str]] = [[] for _ in rows]
        limiter = anyio.CapacityLimiter(ANCESTOR_CONCURRENCY)

        async def fill(index: int, requirement_id: str) -> None:
            async with limiter:
                paths[index] = await self._ancestor_names(
                    token, project_id, requirement_id
                )

        try:
            async with anyio.create_task_group() as fetches:
                for index, row in enumerate(rows):
                    fetches.start_soon(fill, index, row.id)
        except BaseExceptionGroup as group:
            raise _first_failure(group) from None
        return paths

    async def _child_count(
        self, token: SecretStr, project_id: str, requirement_id: str
    ) -> int:
        """Count one requirement's direct children off a listing's `total`."""
        counted = await self._list(
            token,
            project_id,
            COUNT_ONLY_PAGE,
            COUNT_ONLY_LIMIT,
            parent_id=requirement_id,
        )
        return counted.total

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
        )
        paths = await self._paths_for(token, project_id, odas_page.items)
        return self._to_listing(odas_page, page, limit, paths)

    async def node(
        self, token: SecretStr, project_id: str, requirement_id: str
    ) -> RequirementDetail:
        """One requirement in full, with its path.

        The record and the ancestor chain are independent reads, so they go out
        together; the child count is only asked for when the record arrives
        without one.
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
            path = await self._ancestor_names(token, project_id, requirement_id)

        try:
            async with anyio.create_task_group() as reads:
                reads.start_soon(read_detail)
                reads.start_soon(read_path)
        except BaseExceptionGroup as group:
            raise _first_failure(group) from None

        record: OdasRequirementDetail = detail  # type: ignore[assignment]
        child_count = record.child_count
        if child_count is None:
            child_count = await self._child_count(token, project_id, requirement_id)

        return RequirementDetail(
            id=record.id,
            name=record.name,
            label=record.label,
            statement=record.statement,
            rationale=record.rationale,
            level=record.level,
            type=record.type,
            is_atomic=record.is_atomic,
            altitude=self._altitude_of(record),
            parent_id=record.confirmed_parent_id,
            child_count=child_count,
            path=path,
        )
