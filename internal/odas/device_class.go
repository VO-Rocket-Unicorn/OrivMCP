package odas

import (
	"context"
	"log/slog"
	"net/http"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

const deviceClassServiceLabel = "device-class API"

// Node ids carry a colon (group:<slug>, class:<key>). Colons are legal in a
// path segment, so they are left intact rather than percent-encoded, which a
// server that does not decode path params would then fail to match.
const deviceClassIDSafeCharacters = ":"

const (
	parentIDParam = "parent_id"
	depthParam    = "depth"
	cursorParam   = "cursor"
	queryParam    = "query"
	limitParam    = "limit"
)

// DeviceClassClient is read-only access to the device-class taxonomy.
type DeviceClassClient struct {
	apiClient
	collectionURL string
	searchURL     string
	vendorsPath   string
	healthURL     string
}

type DeviceClassURLs struct {
	CollectionURL string
	SearchURL     string
	VendorsPath   string
	HealthURL     string
}

func NewDeviceClassClient(httpClient *http.Client, logger *slog.Logger, urls DeviceClassURLs) *DeviceClassClient {
	return &DeviceClassClient{
		apiClient:     newAPIClient(httpClient, logger, deviceClassServiceLabel),
		collectionURL: urls.CollectionURL,
		searchURL:     urls.SearchURL,
		vendorsPath:   urls.VendorsPath,
		healthURL:     urls.HealthURL,
	}
}

// CheckHealth probes ODAS. The other ODAS clients share its host, so this one
// probe covers them all.
func (c *DeviceClassClient) CheckHealth(ctx context.Context) (bool, string) {
	return c.apiClient.CheckHealth(ctx, c.healthURL)
}

func (c *DeviceClassClient) itemURL(classID string) string {
	return c.collectionURL + "/" + quote(classID, deviceClassIDSafeCharacters)
}

func (c *DeviceClassClient) vendorsURL(classID string) string {
	return c.itemURL(classID) + c.vendorsPath
}

func (c *DeviceClassClient) ListDeviceClasses(ctx context.Context, token Secret, parentID *string, depth int, cursor *string) (schemas.ListDeviceClassesOutput, error) {
	return get[schemas.ListDeviceClassesOutput](ctx, &c.apiClient, c.collectionURL, token,
		param{parentIDParam, parentID},
		param{depthParam, depth},
		param{cursorParam, cursor},
	)
}

func (c *DeviceClassClient) SearchDeviceClasses(ctx context.Context, token Secret, query string, limit int) (schemas.SearchDeviceClassesOutput, error) {
	return get[schemas.SearchDeviceClassesOutput](ctx, &c.apiClient, c.searchURL, token,
		param{queryParam, query},
		param{limitParam, limit},
	)
}

func (c *DeviceClassClient) GetDeviceClass(ctx context.Context, token Secret, classID string) (schemas.GetDeviceClassOutput, error) {
	return get[schemas.GetDeviceClassOutput](ctx, &c.apiClient, c.itemURL(classID), token)
}

func (c *DeviceClassClient) ListDeviceClassVendors(ctx context.Context, token Secret, classID string) (schemas.ListDeviceClassVendorsOutput, error) {
	return get[schemas.ListDeviceClassVendorsOutput](ctx, &c.apiClient, c.vendorsURL(classID), token)
}
