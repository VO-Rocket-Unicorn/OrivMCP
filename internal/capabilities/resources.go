package capabilities

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

const (
	flightInventoryURITemplate = "file://documents/{airport}"
	flightInventoryURIPrefix   = "file://documents/"
	flightInventoryMIMEType    = "text/plain"
)

func registerResources(server *mcp.Server) {
	server.AddResourceTemplate(&mcp.ResourceTemplate{
		URITemplate: flightInventoryURITemplate,
		Name:        "flight_inventory",
		Description: "Get flight inventory for an airport",
		MIMEType:    flightInventoryMIMEType,
	}, func(_ context.Context, req *mcp.ReadResourceRequest) (*mcp.ReadResourceResult, error) {
		uri := req.Params.URI
		airport, ok := strings.CutPrefix(uri, flightInventoryURIPrefix)
		if !ok || airport == "" || strings.Contains(airport, "/") {
			return nil, mcp.ResourceNotFoundError(uri)
		}
		text, err := json.MarshalIndent(schemas.InventoryOutput{
			Flights: []string{airport + "-DEL", airport + "-MUM"},
		}, "", "  ")
		if err != nil {
			return nil, err
		}
		return &mcp.ReadResourceResult{Contents: []*mcp.ResourceContents{{URI: uri, MIMEType: flightInventoryMIMEType, Text: string(text)}}}, nil
	})
}
