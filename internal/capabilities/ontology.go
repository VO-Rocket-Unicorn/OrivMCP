package capabilities

import (
	"context"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

const (
	minListDepth     = 1
	defaultListDepth = 1
	maxListDepth     = 3

	minSearchLimit     = 1
	defaultSearchLimit = 10
)

type listDeviceClassesInput struct {
	ParentID *string `json:"parent_id,omitempty"`
	Depth    int     `json:"depth,omitempty"`
	Cursor   *string `json:"cursor,omitempty"`
}

type searchDeviceClassesInput struct {
	Query string `json:"query"`
	Limit int    `json:"limit,omitempty"`
}

type deviceClassIDInput struct {
	ID string `json:"id"`
}

func registerOntologyTools(server *registrar, client *odas.DeviceClassClient) {
	addTool(server, toolDef{
		name: "list_device_classes",
		description: "Browse one level of the device-class tree. Call with no parent_id to " +
			"see the top-level classes, then call again with a chosen id to go deeper.",
		input: inputSchema[listDeviceClassesInput](map[string]arg{
			"parent_id": {description: "Class to list beneath. Omit for the top-level classes.", nullable: true},
			"depth": {
				description: "How many levels below parent_id to return. 1 is direct children only.",
				def:         defaultListDepth,
				minimum:     new(float64(minListDepth)),
				maximum:     new(float64(maxListDepth)),
			},
			"cursor": {description: "Opaque pagination cursor from a previous nextCursor.", nullable: true},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in listDeviceClassesInput) (schemas.ListDeviceClassesOutput, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.ListDeviceClassesOutput{}, err
		}
		return client.ListDeviceClasses(ctx, token, in.ParentID, in.Depth, in.Cursor)
	})

	addTool(server, toolDef{
		name: "search_device_classes",
		description: "Find device classes by keyword when a term from the datasheet is " +
			"already known. Faster than browsing.",
		input: inputSchema[searchDeviceClassesInput](map[string]arg{
			"query": {
				description: "Case-insensitive substring matched against name and description.",
				minLength:   new(1),
			},
			"limit": {
				description: "Maximum number of matches to return.",
				def:         defaultSearchLimit,
				minimum:     new(float64(minSearchLimit)),
			},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in searchDeviceClassesInput) (schemas.SearchDeviceClassesOutput, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.SearchDeviceClassesOutput{}, err
		}
		return client.SearchDeviceClasses(ctx, token, in.Query, in.Limit)
	})

	addTool(server, toolDef{
		name: "get_device_class",
		description: "Show one class with its parent, children, and siblings. Use to confirm " +
			"a class before committing to it — the siblings are the classes most " +
			"likely to be confused with it.",
		input: inputSchema[deviceClassIDInput](map[string]arg{
			"id": {description: "Id of the device class to inspect."},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in deviceClassIDInput) (schemas.GetDeviceClassOutput, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.GetDeviceClassOutput{}, err
		}
		return client.GetDeviceClass(ctx, token, in.ID)
	})

	addTool(server, toolDef{
		name: "list_device_class_vendors",
		description: "List vendors that have a datasheet profile for a device class. Use " +
			"after confirming the class with get_device_class, to see which " +
			"vendors' datasheets have already been profiled for it.",
		input: inputSchema[deviceClassIDInput](map[string]arg{
			"id": {description: "Id of the device class to look up vendors for."},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in deviceClassIDInput) (schemas.ListDeviceClassVendorsOutput, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.ListDeviceClassVendorsOutput{}, err
		}
		return client.ListDeviceClassVendors(ctx, token, in.ID)
	})
}
