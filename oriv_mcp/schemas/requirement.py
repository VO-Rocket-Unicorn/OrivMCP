"""Requirement-tree shapes. Contract: temp/requirements-tools.md.

Two sets of models, deliberately. ODAS speaks `requirementId` and returns rows
under its own envelope; the tools speak the compact node the traversal spec
fixes, which is trimmed to what a model needs to decide *descend or not*.
Translating between them is the client's job — see `clients/requirement.py`.
"""

from enum import StrEnum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# `limit` defaults to 25 and caps at 100; `page` is 1-based.
MIN_PAGE = 1
DEFAULT_PAGE = 1
MIN_LIMIT = 1
DEFAULT_LIMIT = 25
MAX_LIMIT = 100

# `statement` is cut here, on a word boundary, with `truncated` set. No ellipsis
# character: the flag carries the fact, and a literal "…" reads to a model as
# authored text. ODAS does the cutting for `view=compact`; this is the contract
# it cuts to.
STATEMENT_LIMIT = 240


class Altitude(StrEnum):
    """`level` and `isAtomic` read as one value.

    The three usable rungs run coarsest to finest — a parent must sit at the
    same altitude as its child or coarser, never finer. `unknown` is the fourth
    state, not a fourth rung: it means unclassified, so whether it may legally
    parent anything is not yet knowable.
    """

    STAKEHOLDER = "stakeholder"
    SYSTEM = "system"
    ATOMIC = "atomic"
    UNKNOWN = "unknown"


class ChildAltitude(StrEnum):
    """The altitude of the requirement being placed.

    `unknown` is absent on purpose: its legal parents cannot be worked out, so
    it is not something a caller may ask for candidates against.
    """

    STAKEHOLDER = "stakeholder"
    SYSTEM = "system"
    ATOMIC = "atomic"


# A parent must be the same altitude or coarser. Resolved here rather than
# asked of the caller: a rule enforced in the tool cannot be violated by the
# model, and a candidate that never arrives costs nothing. `unknown` appears in
# no entry — it is offered only when the caller states no child altitude at all.
LEGAL_PARENT_ALTITUDES: dict[ChildAltitude, tuple[Altitude, ...]] = {
    ChildAltitude.STAKEHOLDER: (Altitude.STAKEHOLDER,),
    ChildAltitude.SYSTEM: (Altitude.STAKEHOLDER, Altitude.SYSTEM),
    ChildAltitude.ATOMIC: (Altitude.STAKEHOLDER, Altitude.SYSTEM, Altitude.ATOMIC),
}


class RequirementLevel(StrEnum):
    STAKEHOLDER = "STAKEHOLDER"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


class RequirementType(StrEnum):
    FUNCTIONAL = "FUNCTIONAL"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    UNKNOWN = "UNKNOWN"


def altitude_of(level: RequirementLevel, is_atomic: bool) -> Altitude:
    """Derive altitude from the pair ODAS stores.

    ODAS is asked to send `altitude` computed; this is the fallback for a
    response that predates that, and the one place the mapping is written.
    """
    if level is RequirementLevel.STAKEHOLDER:
        return Altitude.STAKEHOLDER
    if level is RequirementLevel.SYSTEM:
        return Altitude.ATOMIC if is_atomic else Altitude.SYSTEM
    return Altitude.UNKNOWN


# ---------------------------------------------------------------------------
# What ODAS returns
# ---------------------------------------------------------------------------


class OdasRequirementFields(BaseModel):
    """The fields every ODAS requirement row carries, listed or shown.

    Ids and flags are read through `AliasChoices` because the same value is
    spelled differently across ODAS's list and show responses; `altitude` is
    optional so a response that has not started sending it computed still
    validates, and is derived on the way out.
    """

    id: str = Field(validation_alias=AliasChoices("requirementId", "id"))
    name: str
    label: str = ""
    statement: str = Field(
        default="", validation_alias=AliasChoices("statement", "description")
    )
    level: RequirementLevel
    type: RequirementType
    is_atomic: bool = Field(validation_alias=AliasChoices("isAtomic", "is_atomic"))
    altitude: Altitude | None = None


class OdasRequirementRow(OdasRequirementFields):
    """One row of `GET …/requirements?view=compact`.

    `childCount` is required rather than defaulted: it is what makes traversal
    possible, and a row silently missing it would read as a leaf and stop the
    walk. A validation failure naming it is the more useful outcome.
    """

    truncated: bool = False
    child_count: int = Field(validation_alias=AliasChoices("childCount", "child_count"))


class OdasParentRef(BaseModel):
    """A requirement referred to from another one.

    Show resolves the confirmed parent to an object; the listed row spells the
    same thing as a bare id. Only the id is kept — the parent's own name and
    label arrive with the ancestor path, which is where they are useful.
    """

    id: str = Field(validation_alias=AliasChoices("requirementId", "id"))
    name: str = ""
    label: str = ""


class OdasRequirementDetail(OdasRequirementFields):
    """`GET …/requirements/{id}` — the untruncated record.

    Show carries far more than these tools return: the per-criterion
    completeness array, the level and type reasoning, every suggested relation
    and the audit trail. All of it is ignored here. `rationale` is the one
    heavyweight field kept, and only because a candidate under serious
    consideration is worth spending it on.

    It carries no `childCount` and no `altitude`, so both are worked out on the
    way past: the count from a separate read, the altitude from the pair ODAS
    does send.
    """

    rationale: str = ""
    # Show resolves the parent to an object; the full listed row gives a scalar
    # `parentId`, and older list responses only ever carried `parents`. Read
    # whichever arrived.
    parent: OdasParentRef | None = None
    parent_id: str | None = Field(
        default=None, validation_alias=AliasChoices("parentId", "parent_id")
    )
    parents: list[str] = Field(default_factory=list)
    child_count: int | None = Field(
        default=None, validation_alias=AliasChoices("childCount", "child_count")
    )

    @property
    def confirmed_parent_id(self) -> str | None:
        if self.parent is not None:
            return self.parent.id
        return self.parent_id or (self.parents[0] if self.parents else None)


class OdasRequirementPage(BaseModel):
    """The payload of a requirement listing: matches, and how many there are in all.

    ODAS echoes the window it actually applied. That is worth reading back
    rather than assuming the requested one held: omitting `limit` there means
    "everything", answered as page 1 of one page.
    """

    items: list[OdasRequirementRow] = Field(default_factory=list)
    total: int = 0
    page: int | None = None
    limit: int | None = None


class OdasAncestor(BaseModel):
    """One step of `GET …/requirements/{id}/ancestors`."""

    id: str = Field(validation_alias=AliasChoices("requirementId", "id"))
    name: str
    label: str = ""
    altitude: Altitude | None = None


class OdasAncestors(BaseModel):
    items: list[OdasAncestor] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# What the tools return
# ---------------------------------------------------------------------------


class RequirementNode(BaseModel):
    """The one shape every listing tool returns for a requirement.

    Trimmed on purpose: this is read by a language model, and every field costs
    budget that could have gone to another candidate. `completeness`, the audit
    fields and `rationale` are all absent — `rationale` arrives only from
    `requirement_tree_node`, for a candidate under serious consideration.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        description=(
            "The requirement's real ODAS id — what a confirmed parent edge is "
            "recorded against. Always send this back, never `name`."
        )
    )
    name: str = Field(
        description="ODAS's canonical name, e.g. REQ-14. For reasoning and logs, not for edges."
    )
    label: str = Field(description="The author's own label. Empty when unset.")
    statement: str = Field(
        description=(
            f"The requirement text, cut at {STATEMENT_LIMIT} characters on a word "
            "boundary when longer."
        )
    )
    truncated: bool = Field(
        description=(
            "True when `statement` was cut. Call requirement_tree_node for the "
            "rest before committing to this candidate."
        )
    )
    level: RequirementLevel = Field(description="ODAS's stored level.")
    type: RequirementType = Field(description="Functional or not, as ODAS records it.")
    is_atomic: bool = Field(
        alias="isAtomic",
        description="Whether the requirement is atomic — a SYSTEM requirement that is not decomposed further.",
    )
    altitude: Altitude = Field(
        description=(
            "`level` and `isAtomic` read as one value. A parent must be at the "
            "same altitude as its child or coarser: stakeholder, then system, then atomic."
        )
    )
    child_count: int = Field(
        alias="childCount",
        description=(
            "Number of direct children. 0 means there is nothing to descend "
            "into — do not call requirement_tree_children on it."
        ),
    )
    path: list[str] | None = Field(
        default=None,
        description=(
            "Ancestor names, root first, ending at the direct parent; empty for "
            "a root. Carried on search hits, where the caller has not walked "
            "down to the node and so does not otherwise know where it sits. "
            "Null on roots and children listings, where the position is already known."
        ),
    )


class RequirementListing(BaseModel):
    """One page of requirements.

    Rows arrive in ODAS's order and are not re-sorted here: sorting a single
    page is not sorting the set, so re-ordering locally would make paging look
    ordered while still skipping and repeating rows. A stable total order is
    ODAS's to guarantee.
    """

    model_config = ConfigDict(populate_by_name=True)

    items: list[RequirementNode] = Field(
        description="This page of requirements. Empty means nothing matched — a real answer, not a failure."
    )
    page: int = Field(description="Which page this is, 1-based.")
    limit: int = Field(description="Page size this page was read at.")
    total: int = Field(
        description="How many requirements match in all, across every page."
    )
    has_more: bool = Field(
        alias="hasMore",
        description=(
            "True when further pages remain. Read this rather than comparing "
            "page against total yourself."
        ),
    )


class RequirementDetail(BaseModel):
    """One requirement in full — the only shape carrying untruncated text."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="The requirement's real ODAS id.")
    name: str = Field(description="ODAS's canonical name, e.g. REQ-14.")
    label: str = Field(description="The author's own label. Empty when unset.")
    statement: str = Field(description="The full requirement text, never truncated.")
    rationale: str = Field(
        description="Why the requirement exists, in full. Often empty."
    )
    level: RequirementLevel = Field(description="ODAS's stored level.")
    type: RequirementType = Field(description="Functional or not, as ODAS records it.")
    is_atomic: bool = Field(alias="isAtomic", description="Whether the requirement is atomic.")
    altitude: Altitude = Field(
        description="`level` and `isAtomic` read as one value: stakeholder, system, atomic, or unknown."
    )
    parent_id: str | None = Field(
        alias="parentId",
        description="Id of the confirmed parent, or null when this is a root.",
    )
    child_count: int = Field(
        alias="childCount", description="Number of direct children."
    )
    path: list[str] = Field(
        description="Ancestor names, root first, ending at the direct parent. Empty for a root."
    )
