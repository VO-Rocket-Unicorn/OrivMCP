"""Schemas for the AI decision-tree walk and its taxonomy resolution.

The wire shape here is already snake_case and clean, so — unlike
`schemas/device_class.py` — one layer of models suffices; there is no
`Odas*` raw layer to translate out of.
"""

from pydantic import BaseModel, ConfigDict, Field


class DecisionAnswer(BaseModel):
    """One selectable answer to a decision-tree question."""

    model_config = ConfigDict(populate_by_name=True)

    value: str = Field(description="The answer text to match the user's reply against.")
    next: str | None = Field(
        default=None,
        description="Id of the next question node to ask. Null when this answer reaches a leaf.",
    )
    resolves_toward: str | None = Field(
        default=None,
        description=(
            "The architecture name this answer resolves to. Present only when `next` "
            "is null — pass it to `resolve_architecture` to get the full record."
        ),
    )
    label: str | None = Field(
        default=None,
        description=(
            "Human-readable button/option text for this answer, distinct from the "
            "machine-key `value`. Not every tree supplies it."
        ),
    )


class DecisionNode(BaseModel):
    """One question in the decision tree."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique id of this question node.")
    question: str = Field(description="The question to ask the user, verbatim.")
    evidence_type: str = Field(description="Kind of evidence this question is asking about.")
    recognition_triggers: list[str] = Field(
        default_factory=list,
        description="Keywords/phrases that suggest this question is relevant.",
    )
    answers: list[DecisionAnswer] = Field(
        default_factory=list,
        description="Possible answers, each pointing to the next node or a resolution.",
    )


class DecisionTree(BaseModel):
    """The full AI decision tree for one device class, returned in one response.

    Walk it in memory: look up `root_question_id` in `nodes`, ask its
    `question`, match the reply to one of its `answers`, then follow that
    answer's `next` into `nodes` again. Stop when an answer's `next` is null —
    that answer's `resolves_toward` is the result.
    """

    model_config = ConfigDict(populate_by_name=True)

    tree_id: str = Field(description="Id of this decision tree.")
    version: str = Field(description="Version of this decision tree.")
    taxonomy_ref: str = Field(description="Id of the taxonomy this tree resolves into.")
    taxonomy_version: str = Field(description="Version of the referenced taxonomy.")
    root_question_id: str = Field(description="Id of the node in `nodes` to start asking from.")
    nodes: dict[str, DecisionNode] = Field(
        description="Every question node in the tree, keyed by node id."
    )


class DecisionTreeNodeResponse(BaseModel):
    """Response of fetching a single decision-tree node — call-per-question.

    Walk it turn by turn: start with `node_id="root"`, ask the returned node's
    `question`, match the answer, then call again with that answer's `next` as
    the new `node_id`. Stop when an answer's `next` is null — that answer's
    `resolves_toward` is the result.
    """

    model_config = ConfigDict(populate_by_name=True)

    node: DecisionNode = Field(description="The requested question node.")


class ArchitectureDetail(BaseModel):
    """One resolved architecture leaf from the taxonomy."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique id of the architecture.")
    name: str = Field(description="Human-readable name of the architecture.")
    type: str = Field(description="Taxonomy node type, e.g. 'device_class'.")
    parent_id: str | None = Field(default=None, description="Id of the parent taxonomy node, if any.")
    definition: str = Field(default="", description="What this architecture is.")
    distinguishing_mechanism: str = Field(
        default="", description="What distinguishes this architecture from its siblings."
    )
    canonical_spec_ref: str = Field(
        default="", description="Reference to the canonical specification for this architecture."
    )


class TaxonomyLookupResponse(BaseModel):
    """Response of resolving an architecture name against a device class's taxonomy."""

    model_config = ConfigDict(populate_by_name=True)

    taxonomyid: str = Field(description="Id of the taxonomy that was searched.")
    taxonomy_version: str = Field(description="Version of the taxonomy that was searched.")
    device_class: str = Field(description="Human-readable device class this taxonomy covers.")
    leaves: list[ArchitectureDetail] = Field(
        default_factory=list,
        description="Matching architecture leaves — normally exactly one.",
    )
