package schemas

import (
	"fmt"
	"strings"
)

// Requirement-tree shapes.
//
// There are two sets of types, deliberately. ODAS speaks requirementId and
// returns rows under its own envelope. The tools speak the compact node the
// traversal spec fixes, trimmed to what a model needs to decide whether to
// descend. Translating between them is the client's job.

// limit defaults to 25 and caps at 100; page is 1-based.
const (
	MinPage      = 1
	DefaultPage  = 1
	MinLimit     = 1
	DefaultLimit = 25
	MaxLimit     = 100
)

// StatementLimit is where ODAS cuts statement, on a word boundary, with
// truncated set, for view=compact. No ellipsis character: the flag carries
// the fact, and a literal "…" reads to a model as authored text.
const StatementLimit = 240

// Altitude is level and isAtomic read as one value.
//
// The three usable rungs run coarsest to finest; a parent must sit at the
// same altitude as its child or coarser, never finer. unknown is a fourth
// state, not a fourth rung: it means unclassified, so whether it may legally
// parent anything is not yet knowable.
type Altitude string

const (
	AltitudeStakeholder Altitude = "stakeholder"
	AltitudeSystem      Altitude = "system"
	AltitudeAtomic      Altitude = "atomic"
	AltitudeUnknown     Altitude = "unknown"
)

var Altitudes = enum[Altitude]{AltitudeStakeholder, AltitudeSystem, AltitudeAtomic, AltitudeUnknown}

func (a *Altitude) UnmarshalJSON(data []byte) error { return Altitudes.decode(data, a, "Altitude") }

// ChildAltitude is the altitude of the requirement being placed.
//
// unknown is absent on purpose: its legal parents cannot be worked out, so it
// is not something a caller may ask for candidates against.
type ChildAltitude string

const (
	ChildAltitudeStakeholder ChildAltitude = "stakeholder"
	ChildAltitudeSystem      ChildAltitude = "system"
	ChildAltitudeAtomic      ChildAltitude = "atomic"
)

var ChildAltitudes = enum[ChildAltitude]{ChildAltitudeStakeholder, ChildAltitudeSystem, ChildAltitudeAtomic}

func (c *ChildAltitude) UnmarshalJSON(data []byte) error {
	return ChildAltitudes.decode(data, c, "ChildAltitude")
}

// LegalParentAltitudes: a parent must be the same altitude or coarser.
// Resolved here rather than asked of the caller, because a rule enforced in
// the tool cannot be violated by the model, and a candidate that never
// arrives costs nothing. unknown appears in no entry; it is offered only when
// the caller states no child altitude at all.
var LegalParentAltitudes = map[ChildAltitude][]Altitude{
	ChildAltitudeStakeholder: {AltitudeStakeholder},
	ChildAltitudeSystem:      {AltitudeStakeholder, AltitudeSystem},
	ChildAltitudeAtomic:      {AltitudeStakeholder, AltitudeSystem, AltitudeAtomic},
}

// LegalParentAltitudeParam is the comma-joined altitude filter for a child
// altitude.
func LegalParentAltitudeParam(child ChildAltitude) (string, error) {
	legal, ok := LegalParentAltitudes[child]
	if !ok {
		return "", fmt.Errorf("unknown child altitude %q", child)
	}
	parts := make([]string, len(legal))
	for i, altitude := range legal {
		parts[i] = string(altitude)
	}
	return strings.Join(parts, ","), nil
}

type RequirementLevel string

const (
	RequirementLevelStakeholder RequirementLevel = "STAKEHOLDER"
	RequirementLevelSystem      RequirementLevel = "SYSTEM"
	RequirementLevelUnknown     RequirementLevel = "UNKNOWN"
)

var RequirementLevels = enum[RequirementLevel]{RequirementLevelStakeholder, RequirementLevelSystem, RequirementLevelUnknown}

func (l *RequirementLevel) UnmarshalJSON(data []byte) error {
	return RequirementLevels.decode(data, l, "RequirementLevel")
}

type RequirementType string

const (
	RequirementTypeFunctional    RequirementType = "FUNCTIONAL"
	RequirementTypeNonFunctional RequirementType = "NON_FUNCTIONAL"
	RequirementTypeUnknown       RequirementType = "UNKNOWN"
)

var RequirementTypes = enum[RequirementType]{RequirementTypeFunctional, RequirementTypeNonFunctional, RequirementTypeUnknown}

func (t *RequirementType) UnmarshalJSON(data []byte) error {
	return RequirementTypes.decode(data, t, "RequirementType")
}

// ---------------------------------------------------------------------------
// What ODAS returns
// ---------------------------------------------------------------------------

// OdasRequirementFields are the fields every ODAS requirement row carries,
// listed or shown.
//
// Ids and text are read under several names because the same value is
// spelled differently across ODAS's list and show responses. altitude is
// required: ODAS derives it from level and isAtomic and sends it on every
// shape, so nothing here re-derives it.
type OdasRequirementFields struct {
	ID        string
	Name      string
	Label     string
	Statement string
	Level     RequirementLevel
	Type      RequirementType
	IsAtomic  bool
	Altitude  Altitude
}

func (f *OdasRequirementFields) decode(o *object) {
	required(o, &f.ID, "requirementId", "id")
	required(o, &f.Name, "name")
	optional(o, &f.Label, "label")
	optional(o, &f.Statement, "statement", "description")
	required(o, &f.Level, "level")
	required(o, &f.Type, "type")
	required(o, &f.IsAtomic, "isAtomic", "is_atomic")
	required(o, &f.Altitude, "altitude")
}

// OdasRequirementRow is one row of GET …/requirements?view=compact.
//
// childCount is required rather than defaulted: it is what makes traversal
// possible, and a row silently missing it would read as a leaf and stop the
// walk. A validation failure naming it is the more useful outcome.
type OdasRequirementRow struct {
	OdasRequirementFields
	Truncated  bool
	ChildCount int
	// Path is the root->parent ancestor ids, sent on every compact row.
	// Passed on only for search hits, whose position in the tree the caller
	// has not walked to.
	Path []string
}

func (r *OdasRequirementRow) UnmarshalJSON(data []byte) error {
	o, err := newObject("OdasRequirementRow", data)
	if err != nil {
		return err
	}
	var v OdasRequirementRow
	v.decode(o)
	optional(o, &v.Truncated, "truncated")
	required(o, &v.ChildCount, "childCount", "child_count")
	optional(o, &v.Path, "path")
	v.Path = orEmpty(v.Path)
	*r = v
	return o.err()
}

// OdasParentRef is a requirement referred to from another one. Only the id is
// used; the parent's own name and label arrive with the ancestor path.
type OdasParentRef struct {
	ID    string
	Name  string
	Label string
}

func (p *OdasParentRef) UnmarshalJSON(data []byte) error {
	o, err := newObject("OdasParentRef", data)
	if err != nil {
		return err
	}
	var v OdasParentRef
	required(o, &v.ID, "requirementId", "id")
	optional(o, &v.Name, "name")
	optional(o, &v.Label, "label")
	*p = v
	return o.err()
}

// OdasRequirementDetail is GET …/requirements/{id}, the untruncated record.
//
// Show carries far more than these tools return; all of it is ignored.
// rationale is the one heavyweight field kept. It carries no ancestor path,
// which still comes from the ancestors endpoint.
type OdasRequirementDetail struct {
	OdasRequirementFields
	Rationale string
	// Show resolves the parent to an object; the full listed row gives a
	// scalar parentId, and older list responses only ever carried parents.
	// Whichever arrived is read.
	Parent     *OdasParentRef
	ParentID   *string
	Parents    []string
	ChildCount int
}

func (d *OdasRequirementDetail) UnmarshalJSON(data []byte) error {
	o, err := newObject("OdasRequirementDetail", data)
	if err != nil {
		return err
	}
	var v OdasRequirementDetail
	v.decode(o)
	optional(o, &v.Rationale, "rationale")
	optional(o, &v.Parent, "parent")
	optional(o, &v.ParentID, "parentId", "parent_id")
	optional(o, &v.Parents, "parents")
	required(o, &v.ChildCount, "childCount", "child_count")
	*d = v
	return o.err()
}

// ConfirmedParentID prefers the resolved parent object, then the scalar id,
// then the first of the legacy parents list.
func (d *OdasRequirementDetail) ConfirmedParentID() *string {
	if d.Parent != nil {
		id := d.Parent.ID
		return &id
	}
	if d.ParentID != nil && *d.ParentID != "" {
		return d.ParentID
	}
	if len(d.Parents) > 0 {
		id := d.Parents[0]
		return &id
	}
	return nil
}

// OdasRequirementPage is the payload of a requirement listing: matches, and
// how many there are in all.
//
// ODAS echoes the window it actually applied. That is worth reading back
// rather than assuming the requested one held: omitting limit there means
// "everything", answered as page 1 of one page.
type OdasRequirementPage struct {
	Items []OdasRequirementRow
	Total int
	Page  *int
	Limit *int
}

func (p *OdasRequirementPage) UnmarshalJSON(data []byte) error {
	o, err := newObject("OdasRequirementPage", data)
	if err != nil {
		return err
	}
	var v OdasRequirementPage
	optional(o, &v.Items, "items")
	optional(o, &v.Total, "total")
	optional(o, &v.Page, "page")
	optional(o, &v.Limit, "limit")
	v.Items = orEmpty(v.Items)
	*p = v
	return o.err()
}

// OdasAncestor is one step of GET …/requirements/{id}/ancestors.
type OdasAncestor struct {
	ID       string
	Name     string
	Label    string
	Altitude *Altitude
}

func (a *OdasAncestor) UnmarshalJSON(data []byte) error {
	o, err := newObject("OdasAncestor", data)
	if err != nil {
		return err
	}
	var v OdasAncestor
	required(o, &v.ID, "requirementId", "id")
	required(o, &v.Name, "name")
	optional(o, &v.Label, "label")
	optional(o, &v.Altitude, "altitude")
	*a = v
	return o.err()
}

type OdasAncestors struct {
	Items []OdasAncestor
}

func (a *OdasAncestors) UnmarshalJSON(data []byte) error {
	o, err := newObject("OdasAncestors", data)
	if err != nil {
		return err
	}
	var v OdasAncestors
	optional(o, &v.Items, "items")
	*a = v
	return o.err()
}

// ---------------------------------------------------------------------------
// What the tools return
// ---------------------------------------------------------------------------

// RequirementNode is the one shape every listing tool returns for a
// requirement.
//
// Trimmed on purpose: it is read by a language model, and every field costs
// budget that could have gone to another candidate. rationale arrives only
// from requirement_tree_node, for a candidate under serious consideration.
type RequirementNode struct {
	ID         string           `json:"id" jsonschema:"The requirement's real ODAS id — what a confirmed parent edge is recorded against. Always send this back, never name."`
	Name       string           `json:"name" jsonschema:"ODAS's canonical name, e.g. REQ-14. For reasoning and logs, not for edges."`
	Label      string           `json:"label" jsonschema:"The author's own label. Empty when unset."`
	Statement  string           `json:"statement" jsonschema:"The requirement text, cut at 240 characters on a word boundary when longer."`
	Truncated  bool             `json:"truncated" jsonschema:"True when statement was cut. Call requirement_tree_node for the rest before committing to this candidate."`
	Level      RequirementLevel `json:"level" jsonschema:"ODAS's stored level."`
	Type       RequirementType  `json:"type" jsonschema:"Functional or not, as ODAS records it."`
	IsAtomic   bool             `json:"isAtomic" jsonschema:"Whether the requirement is atomic — a SYSTEM requirement that is not decomposed further."`
	Altitude   Altitude         `json:"altitude" jsonschema:"level and isAtomic read as one value. A parent must be at the same altitude as its child or coarser: stakeholder, then system, then atomic."`
	ChildCount int              `json:"childCount" jsonschema:"Number of direct children. 0 means there is nothing to descend into — do not call requirement_tree_children on it."`
	// Path is null on roots and children listings, where the position is
	// already known, and an array on search hits.
	Path *[]string `json:"path" jsonschema:"Ancestor ids, root first, ending at the direct parent; empty for a root. Carried on search hits, where the caller has not walked down to the node and so does not otherwise know where it sits — pass one of these ids to requirement_tree_node to see what it is. Null on roots and children listings, where the position is already known."`
}

// RequirementListing is one page of requirements.
//
// Read under ODAS's opt-in sort, whose order is total and stable, so paging
// cannot silently skip or repeat a row.
type RequirementListing struct {
	Items   []RequirementNode `json:"items" jsonschema:"This page of requirements. Empty means nothing matched — a real answer, not a failure."`
	Page    int               `json:"page" jsonschema:"Which page this is, 1-based."`
	Limit   int               `json:"limit" jsonschema:"Page size this page was read at."`
	Total   int               `json:"total" jsonschema:"How many requirements match in all, across every page."`
	HasMore bool              `json:"hasMore" jsonschema:"True when further pages remain. Read this rather than comparing page against total yourself."`
}

// RequirementDetail is one requirement in full, the only shape carrying
// untruncated text.
type RequirementDetail struct {
	ID         string           `json:"id" jsonschema:"The requirement's real ODAS id."`
	Name       string           `json:"name" jsonschema:"ODAS's canonical name, e.g. REQ-14."`
	Label      string           `json:"label" jsonschema:"The author's own label. Empty when unset."`
	Statement  string           `json:"statement" jsonschema:"The full requirement text, never truncated."`
	Rationale  string           `json:"rationale" jsonschema:"Why the requirement exists, in full. Often empty."`
	Level      RequirementLevel `json:"level" jsonschema:"ODAS's stored level."`
	Type       RequirementType  `json:"type" jsonschema:"Functional or not, as ODAS records it."`
	IsAtomic   bool             `json:"isAtomic" jsonschema:"Whether the requirement is atomic."`
	Altitude   Altitude         `json:"altitude" jsonschema:"level and isAtomic read as one value: stakeholder, system, atomic, or unknown."`
	ParentID   *string          `json:"parentId" jsonschema:"Id of the confirmed parent, or null when this is a root."`
	ChildCount int              `json:"childCount" jsonschema:"Number of direct children."`
	Path       []string         `json:"path" jsonschema:"Ancestor ids, root first, ending at the direct parent. Empty for a root. Each can be passed straight back to requirement_tree_node."`
}
