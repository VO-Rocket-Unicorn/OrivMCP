package capabilities

import (
	"context"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

// Requirement-tree traversal.
//
// Four read-only tools let a model walk a project's requirement tree instead
// of being handed the whole thing: fetch one level, score it, descend only
// where a score justifies it. A run then costs the branches it explored
// rather than the field.
//
// Argument names are the contract's own (forChildAltitude, excludeId), not
// this codebase's casing; the sidecar binds against them. The project is the
// exception: it is fixed for a session, so it arrives on the X-Project-Id
// header beside the credential rather than as an argument the model has to
// carry through every call.

// ---- arguments shared by the listing tools ----

const (
	requirementIDDescription    = "Id of the requirement to read."
	forChildAltitudeDescription = "Altitude of the requirement being PLACED. Only requirements that " +
		"may legally parent it are returned: a parent must sit at the same " +
		"altitude or coarser. Omit it and everything comes back, including " +
		"requirements whose altitude is still unknown."
	excludeIDDescription = "A requirement to omit together with its entire subtree. Pass the " +
		"requirement being placed: it cannot parent itself, and a descendant " +
		"of it cannot parent it either — that closes a cycle, which ODAS " +
		"refuses, so such a candidate is one no human could ever accept."
	inSubtreeOfDescription = "Restrict the search to one branch: only requirements beneath this " +
		"id, at any depth. Use it to search inside a subtree that already " +
		"looks right, instead of across the whole project."
)

var (
	requirementIDArg    = arg{description: requirementIDDescription, minLength: new(1)}
	forChildAltitudeArg = arg{description: forChildAltitudeDescription, nullable: true}
	excludeIDArg        = arg{description: excludeIDDescription, nullable: true}
	inSubtreeOfArg      = arg{description: inSubtreeOfDescription, nullable: true}
	pageArg             = arg{description: "Which page to read, 1-based.", def: schemas.DefaultPage, minimum: new(float64(schemas.MinPage))}
	limitArg            = arg{description: "Page size.", def: schemas.DefaultLimit, minimum: new(float64(schemas.MinLimit)), maximum: new(float64(schemas.MaxLimit))}
)

type requirementTreeRootsInput struct {
	ForChildAltitude *schemas.ChildAltitude `json:"forChildAltitude,omitempty"`
	ExcludeID        *string                `json:"excludeId,omitempty"`
	Page             int                    `json:"page,omitempty"`
	Limit            int                    `json:"limit,omitempty"`
}

type requirementTreeChildrenInput struct {
	RequirementID    string                 `json:"requirementId"`
	ForChildAltitude *schemas.ChildAltitude `json:"forChildAltitude,omitempty"`
	ExcludeID        *string                `json:"excludeId,omitempty"`
	Page             int                    `json:"page,omitempty"`
	Limit            int                    `json:"limit,omitempty"`
}

type requirementTreeSearchInput struct {
	Query            string                   `json:"query"`
	ForChildAltitude *schemas.ChildAltitude   `json:"forChildAltitude,omitempty"`
	Type             *schemas.RequirementType `json:"type,omitempty"`
	ExcludeID        *string                  `json:"excludeId,omitempty"`
	InSubtreeOf      *string                  `json:"inSubtreeOf,omitempty"`
	Page             int                      `json:"page,omitempty"`
	Limit            int                      `json:"limit,omitempty"`
}

type requirementTreeNodeInput struct {
	RequirementID string `json:"requirementId"`
}

// requirementScope is the caller's credential and project, both off headers.
func requirementScope(req *mcp.CallToolRequest) (odas.Secret, string, error) {
	token, err := odasToken(req)
	if err != nil {
		return odas.Secret{}, "", err
	}
	projectID, err := requireHeader(req, ProjectIDHeader, ProjectIDHint)
	if err != nil {
		return odas.Secret{}, "", err
	}
	return token, projectID, nil
}

func registerRequirementTools(server *registrar, client *odas.RequirementClient) {
	// Nothing here writes. Declared so a client that gates side effects can
	// permit these without asking.
	readOnly := func() *mcp.ToolAnnotations { return &mcp.ToolAnnotations{ReadOnlyHint: true} }
	meta := func() mcp.Meta { return tagsMeta(RequirementsTag) }

	addTool(server, toolDef{
		name: "requirement_tree_roots",
		description: "Start here. The top of the project's requirement tree: requirements " +
			"with no parent. When every result has childCount 0 and total covers " +
			"the whole project, the project has no hierarchy yet — use " +
			"requirement_tree_search instead of descending.",
		annotations: readOnly(),
		meta:        meta(),
		input: inputSchema[requirementTreeRootsInput](map[string]arg{
			"forChildAltitude": forChildAltitudeArg,
			"excludeId":        excludeIDArg,
			"page":             pageArg,
			"limit":            limitArg,
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in requirementTreeRootsInput) (schemas.RequirementListing, error) {
		token, projectID, err := requirementScope(req)
		if err != nil {
			return schemas.RequirementListing{}, err
		}
		return client.Roots(ctx, token, projectID, in.ForChildAltitude, in.ExcludeID, in.Page, in.Limit)
	})

	addTool(server, toolDef{
		name: "requirement_tree_children",
		description: "Descend one level. The direct children of one requirement. Call it on " +
			"a candidate that scored well and whose childCount is above zero. One " +
			"level only — depth is your decision, made from the scores you have " +
			"just seen. A leaf returns an empty list, not an error.",
		annotations: readOnly(),
		meta:        meta(),
		input: inputSchema[requirementTreeChildrenInput](map[string]arg{
			"requirementId":    requirementIDArg,
			"forChildAltitude": forChildAltitudeArg,
			"excludeId":        excludeIDArg,
			"page":             pageArg,
			"limit":            limitArg,
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in requirementTreeChildrenInput) (schemas.RequirementListing, error) {
		token, projectID, err := requirementScope(req)
		if err != nil {
			return schemas.RequirementListing{}, err
		}
		return client.Children(ctx, token, projectID, in.RequirementID, in.ForChildAltitude, in.ExcludeID, in.Page, in.Limit)
	})

	addTool(server, toolDef{
		name: "requirement_tree_search",
		description: "Find candidates by keyword, with each hit's ancestor path from the " +
			"root. Use it when the tree is flat, or to jump into a deep branch " +
			"without walking every level above it; pass inSubtreeOf to search " +
			"within one branch instead of the whole project. Every word given must " +
			"match, so send two or three distinctive words rather than the whole " +
			"statement, and drop words if nothing comes back. Results are unranked, " +
			"in match order, so page further before concluding nothing fits. No " +
			"match is an empty list, not an error.",
		annotations: readOnly(),
		meta:        meta(),
		input: inputSchema[requirementTreeSearchInput](map[string]arg{
			"query": {
				description: "Free text matched against each requirement's statement and label.",
				minLength:   new(1),
			},
			"forChildAltitude": forChildAltitudeArg,
			"type":             {description: "Keep only requirements of this type. Omit to search both.", nullable: true},
			"excludeId":        excludeIDArg,
			"inSubtreeOf":      inSubtreeOfArg,
			"page":             pageArg,
			"limit":            limitArg,
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in requirementTreeSearchInput) (schemas.RequirementListing, error) {
		token, projectID, err := requirementScope(req)
		if err != nil {
			return schemas.RequirementListing{}, err
		}
		return client.Search(ctx, token, projectID, in.Query, in.ForChildAltitude, in.Type, in.ExcludeID, in.InSubtreeOf, in.Page, in.Limit)
	})

	addTool(server, toolDef{
		name: "requirement_tree_node",
		description: "The full, untruncated statement and rationale for one requirement, " +
			"with its path from the root. Call it before committing to a candidate " +
			"whose listed statement came back truncated.",
		annotations: readOnly(),
		meta:        meta(),
		input: inputSchema[requirementTreeNodeInput](map[string]arg{
			"requirementId": requirementIDArg,
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in requirementTreeNodeInput) (schemas.RequirementDetail, error) {
		token, projectID, err := requirementScope(req)
		if err != nil {
			return schemas.RequirementDetail{}, err
		}
		return client.Node(ctx, token, projectID, in.RequirementID)
	})
}
