package odas

import (
	"context"
	"log/slog"
	"net/http"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

const architectureSelectionServiceLabel = "architecture-selection API"

// Device-class keys carry a dot (e.g. "adc.sar") and may carry a colon, like
// device-class ids do. Both are left intact rather than percent-encoded.
const architectureIDSafeCharacters = ":"

const (
	byParam               = "by"
	byAIValue             = "ai"
	architectureNameField = "architecture_name"
)

// ArchitectureSelectionClient is read-only access to AI decision trees and
// their taxonomy resolution.
type ArchitectureSelectionClient struct {
	apiClient
	decisionTreesURL string
	taxonomiesURL    string
	healthURL        string
}

type ArchitectureSelectionURLs struct {
	DecisionTreesURL string
	TaxonomiesURL    string
	HealthURL        string
}

func NewArchitectureSelectionClient(httpClient *http.Client, logger *slog.Logger, urls ArchitectureSelectionURLs) *ArchitectureSelectionClient {
	return &ArchitectureSelectionClient{
		apiClient:        newAPIClient(httpClient, logger, architectureSelectionServiceLabel),
		decisionTreesURL: urls.DecisionTreesURL,
		taxonomiesURL:    urls.TaxonomiesURL,
		healthURL:        urls.HealthURL,
	}
}

func (c *ArchitectureSelectionClient) CheckHealth(ctx context.Context) (bool, string) {
	return c.apiClient.CheckHealth(ctx, c.healthURL)
}

func (c *ArchitectureSelectionClient) decisionTreeURL(deviceClassKey string) string {
	return c.decisionTreesURL + "/" + quote(deviceClassKey, architectureIDSafeCharacters)
}

func (c *ArchitectureSelectionClient) decisionTreeNodeURL(deviceClassKey, nodeID string) string {
	return c.decisionTreeURL(deviceClassKey) + "/nodes/" + quote(nodeID, architectureIDSafeCharacters)
}

func (c *ArchitectureSelectionClient) taxonomyURL(deviceClassKey string) string {
	return c.taxonomiesURL + "/" + quote(deviceClassKey, architectureIDSafeCharacters)
}

func (c *ArchitectureSelectionClient) GetDecisionTree(ctx context.Context, token Secret, deviceClassKey string) (schemas.DecisionTree, error) {
	return get[schemas.DecisionTree](ctx, &c.apiClient, c.decisionTreeURL(deviceClassKey), token,
		param{byParam, byAIValue})
}

func (c *ArchitectureSelectionClient) GetDecisionTreeNode(ctx context.Context, token Secret, deviceClassKey, nodeID string) (schemas.DecisionNode, error) {
	response, err := get[schemas.DecisionTreeNodeResponse](ctx, &c.apiClient, c.decisionTreeNodeURL(deviceClassKey, nodeID), token,
		param{byParam, byAIValue})
	if err != nil {
		return schemas.DecisionNode{}, err
	}
	return response.Node, nil
}

func (c *ArchitectureSelectionClient) ResolveArchitecture(ctx context.Context, token Secret, deviceClassKey, architectureName string) (schemas.ArchitectureDetail, error) {
	response, err := get[schemas.TaxonomyLookupResponse](ctx, &c.apiClient, c.taxonomyURL(deviceClassKey), token,
		param{architectureNameField, architectureName})
	if err != nil {
		return schemas.ArchitectureDetail{}, err
	}
	if len(response.Leaves) == 0 {
		return schemas.ArchitectureDetail{}, toolError(
			"No architecture resolved for '%s' under device class '%s'.", architectureName, deviceClassKey)
	}
	return response.Leaves[0], nil
}
