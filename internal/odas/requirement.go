package odas

import (
	"context"
	"log/slog"
	"net/http"

	"golang.org/x/sync/errgroup"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

// Requirement-tree reads.
//
// Read-only by construction: there is no method here that writes. A parent
// is confirmed by a human through PATCH …/requirements/{id}/parent, and these
// tools must not offer a path around that.
//
// Two domain rules are resolved here rather than asked of the caller: the
// legal-parent altitude bound, and excluding a requirement's own subtree. A
// rule enforced in the tool cannot be violated by the model, and a candidate
// that never arrives costs nothing.

const requirementServiceLabel = "requirements API"

// ---- query params on GET …/requirements ----
const (
	reqParentIDParam       = "parentId"
	reqAltitudeParam       = "altitude"
	reqQueryParam          = "q"
	reqExcludeSubtreeParam = "excludeSubtreeOf"
	reqInSubtreeParam      = "inSubtreeOf"
	reqSortParam           = "sort"
	reqViewParam           = "view"
	reqTypeParam           = "type"
	reqPageParam           = "page"
	reqLimitParam          = "limit"

	compactView = "compact"

	// Sorting is opt-in at ODAS, and left off, the order is explicitly
	// unspecified, which over more than one page means silently skipped and
	// repeated rows. Every read here asks for it.
	sortByName = "name"

	// noParent is the literal ODAS wants for "requirements with no parent".
	// parentId= is indistinguishable from a caller that built the query
	// string wrong, and returning the whole project in that case is the kind
	// of bug nobody notices until a model has been shown every requirement.
	noParent = "none"

	// Ids go in a path segment whole; none of them may be read as a separator.
	requirementIDSafeCharacters = ""
)

// RequirementClient is read-only access to one project's requirement tree.
type RequirementClient struct {
	apiClient
	projectsURL      string
	requirementsPath string
	ancestorsPath    string
}

type RequirementURLs struct {
	ProjectsURL      string
	RequirementsPath string
	AncestorsPath    string
}

func NewRequirementClient(httpClient *http.Client, logger *slog.Logger, urls RequirementURLs) *RequirementClient {
	return &RequirementClient{
		apiClient:        newAPIClient(httpClient, logger, requirementServiceLabel),
		projectsURL:      urls.ProjectsURL,
		requirementsPath: urls.RequirementsPath,
		ancestorsPath:    urls.AncestorsPath,
	}
}

// ---- urls ----

func (c *RequirementClient) collectionURL(projectID string) string {
	return c.projectsURL + "/" + quote(projectID, requirementIDSafeCharacters) + c.requirementsPath
}

func (c *RequirementClient) itemURL(projectID, requirementID string) string {
	return c.collectionURL(projectID) + "/" + quote(requirementID, requirementIDSafeCharacters)
}

func (c *RequirementClient) ancestorsURL(projectID, requirementID string) string {
	return c.itemURL(projectID, requirementID) + c.ancestorsPath
}

// ---- translation ----

// altitudes lists the altitudes that may legally parent a child at this
// altitude. Nil when the caller states no child altitude: that, and only
// that, is when an unknown-altitude requirement is offered as a candidate.
func altitudes(child *schemas.ChildAltitude) (*string, error) {
	if child == nil {
		return nil, nil
	}
	joined, err := schemas.LegalParentAltitudeParam(*child)
	if err != nil {
		return nil, err
	}
	return &joined, nil
}

// toNode trims one ODAS row to the node the tools return.
//
// The path is dropped unless asked for: every compact row carries it, but it
// is only worth its tokens on a search hit, whose position the caller has not
// walked to.
func toNode(row schemas.OdasRequirementRow, withPath bool) schemas.RequirementNode {
	node := schemas.RequirementNode{
		ID:         row.ID,
		Name:       row.Name,
		Label:      row.Label,
		Statement:  row.Statement,
		Truncated:  row.Truncated,
		Level:      row.Level,
		Type:       row.Type,
		IsAtomic:   row.IsAtomic,
		Altitude:   row.Altitude,
		ChildCount: row.ChildCount,
	}
	if withPath {
		path := append([]string{}, row.Path...)
		node.Path = &path
	}
	return node
}

// toListing wraps ODAS's rows in the envelope the traversal tools return.
//
// hasMore is redundant against page*limit < total and computed here anyway:
// it takes the arithmetic off the model's path, and with it one way for the
// model to stop paging early by mistake.
func toListing(odasPage schemas.OdasRequirementPage, page, limit int, withPaths bool) schemas.RequirementListing {
	// The window ODAS says it applied, falling back to the one asked for.
	appliedPage, appliedLimit := page, limit
	if odasPage.Page != nil && *odasPage.Page != 0 {
		appliedPage = *odasPage.Page
	}
	if odasPage.Limit != nil && *odasPage.Limit != 0 {
		appliedLimit = *odasPage.Limit
	}
	items := make([]schemas.RequirementNode, 0, len(odasPage.Items))
	for _, row := range odasPage.Items {
		items = append(items, toNode(row, withPaths))
	}
	return schemas.RequirementListing{
		Items:   items,
		Page:    appliedPage,
		Limit:   appliedLimit,
		Total:   odasPage.Total,
		HasMore: appliedPage*appliedLimit < odasPage.Total,
	}
}

// ---- reads ----

type listFilters struct {
	parentID        *string
	query           *string
	childAltitude   *schemas.ChildAltitude
	requirementType *schemas.RequirementType
	excludeID       *string
	inSubtreeOf     *string
}

func (c *RequirementClient) list(ctx context.Context, token Secret, projectID string, page, limit int, f listFilters) (schemas.OdasRequirementPage, error) {
	altitude, err := altitudes(f.childAltitude)
	if err != nil {
		return schemas.OdasRequirementPage{}, toolError("%v", err)
	}
	var requirementType *string
	if f.requirementType != nil {
		value := string(*f.requirementType)
		requirementType = &value
	}
	return get[schemas.OdasRequirementPage](ctx, &c.apiClient, c.collectionURL(projectID), token,
		param{reqParentIDParam, f.parentID},
		param{reqQueryParam, f.query},
		param{reqAltitudeParam, altitude},
		param{reqTypeParam, requirementType},
		param{reqExcludeSubtreeParam, f.excludeID},
		param{reqInSubtreeParam, f.inSubtreeOf},
		param{reqSortParam, sortByName},
		param{reqViewParam, compactView},
		param{reqPageParam, page},
		param{reqLimitParam, limit},
	)
}

// ancestorIDs is the ancestor path as ids, root first: the same spelling the
// compact row uses, so a path means one thing whichever tool produced it.
func (c *RequirementClient) ancestorIDs(ctx context.Context, token Secret, projectID, requirementID string) ([]string, error) {
	ancestors, err := get[schemas.OdasAncestors](ctx, &c.apiClient, c.ancestorsURL(projectID, requirementID), token)
	if err != nil {
		return nil, err
	}
	ids := make([]string, 0, len(ancestors.Items))
	for _, ancestor := range ancestors.Items {
		ids = append(ids, ancestor.ID)
	}
	return ids, nil
}

// ---- what the tools call ----

func (c *RequirementClient) Roots(ctx context.Context, token Secret, projectID string, childAltitude *schemas.ChildAltitude, excludeID *string, page, limit int) (schemas.RequirementListing, error) {
	parent := noParent
	odasPage, err := c.list(ctx, token, projectID, page, limit, listFilters{
		parentID: &parent, childAltitude: childAltitude, excludeID: excludeID,
	})
	if err != nil {
		return schemas.RequirementListing{}, err
	}
	return toListing(odasPage, page, limit, false), nil
}

func (c *RequirementClient) Children(ctx context.Context, token Secret, projectID, requirementID string, childAltitude *schemas.ChildAltitude, excludeID *string, page, limit int) (schemas.RequirementListing, error) {
	odasPage, err := c.list(ctx, token, projectID, page, limit, listFilters{
		parentID: &requirementID, childAltitude: childAltitude, excludeID: excludeID,
	})
	if err != nil {
		return schemas.RequirementListing{}, err
	}
	return toListing(odasPage, page, limit, false), nil
}

func (c *RequirementClient) Search(ctx context.Context, token Secret, projectID, query string, childAltitude *schemas.ChildAltitude, requirementType *schemas.RequirementType, excludeID, inSubtreeOf *string, page, limit int) (schemas.RequirementListing, error) {
	odasPage, err := c.list(ctx, token, projectID, page, limit, listFilters{
		query: &query, childAltitude: childAltitude, requirementType: requirementType,
		excludeID: excludeID, inSubtreeOf: inSubtreeOf,
	})
	if err != nil {
		return schemas.RequirementListing{}, err
	}
	return toListing(odasPage, page, limit, true), nil
}

// Node is one requirement in full, with its path.
//
// The record and the ancestor chain are independent reads, so they go out
// together. The first failure wins and cancels the other read.
func (c *RequirementClient) Node(ctx context.Context, token Secret, projectID, requirementID string) (schemas.RequirementDetail, error) {
	var (
		detail schemas.OdasRequirementDetail
		path   []string
	)
	group, groupCtx := errgroup.WithContext(ctx)
	group.Go(func() error {
		var err error
		detail, err = get[schemas.OdasRequirementDetail](groupCtx, &c.apiClient, c.itemURL(projectID, requirementID), token)
		return err
	})
	group.Go(func() error {
		var err error
		path, err = c.ancestorIDs(groupCtx, token, projectID, requirementID)
		return err
	})
	if err := group.Wait(); err != nil {
		return schemas.RequirementDetail{}, err
	}

	return schemas.RequirementDetail{
		ID:         detail.ID,
		Name:       detail.Name,
		Label:      detail.Label,
		Statement:  detail.Statement,
		Rationale:  detail.Rationale,
		Level:      detail.Level,
		Type:       detail.Type,
		IsAtomic:   detail.IsAtomic,
		Altitude:   detail.Altitude,
		ParentID:   detail.ConfirmedParentID(),
		ChildCount: detail.ChildCount,
		Path:       path,
	}, nil
}
