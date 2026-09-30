package capabilities

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"

	"github.com/google/jsonschema-go/jsonschema"
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
)

// Clients are the outbound clients the tools call.
type Clients struct {
	DeviceClass           *odas.DeviceClassClient
	ArchitectureSelection *odas.ArchitectureSelectionClient
	Requirement           *odas.RequirementClient
}

// Register adds every tool, prompt and resource to server, and returns the
// names of the tools.
func Register(server *mcp.Server, clients Clients, logger *slog.Logger) []string {
	r := &registrar{server: server, logger: logger}
	registerArchitectureTools(r, clients.ArchitectureSelection)
	registerOntologyTools(r, clients.DeviceClass)
	registerRequirementTools(r, clients.Requirement)
	registerPrompts(server)
	registerResources(server)
	return r.tools
}

type registrar struct {
	server *mcp.Server
	logger *slog.Logger
	tools  []string
}

// toolDef is one tool's declaration.
type toolDef struct {
	name        string
	description string
	meta        mcp.Meta
	annotations *mcp.ToolAnnotations
	input       *jsonschema.Schema
}

// addTool registers a tool with structured output.
//
// Every failure reaches the model as an error result under the tool's name,
// never as a protocol error: bad arguments are the model's to read and
// correct. A deliberate failure (a ToolError) keeps its own text after the
// prefix; anything else is logged, and only the prefix is returned, so
// nothing from an unexpected failure reaches the client.
//
// The text content carries the same object as the structured content,
// pretty-printed, for clients that only read text.
func addTool[In, Out any](r *registrar, def toolDef, handle func(context.Context, *mcp.CallToolRequest, In) (Out, error)) {
	prefix := "Error executing tool " + def.name
	validator := newArgsValidator(def.name, def.input)

	tool := &mcp.Tool{
		Name:         def.name,
		Description:  def.description,
		Meta:         def.meta,
		Annotations:  def.annotations,
		InputSchema:  def.input,
		OutputSchema: outputSchema[Out](),
	}
	r.tools = append(r.tools, def.name)
	r.server.AddTool(tool, func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, problem := validator.validate(req.Params.Arguments)
		if problem != "" {
			return errorResult(prefix + ": " + problem), nil
		}
		var in In
		if err := json.Unmarshal(args, &in); err != nil {
			return errorResult(prefix + ": " + err.Error()), nil
		}

		out, err := handle(ctx, req, in)
		if err != nil {
			var toolErr *odas.ToolError
			if errors.As(err, &toolErr) {
				return errorResult(prefix + ": " + toolErr.Message), nil
			}
			r.logger.ErrorContext(ctx, "Tool "+def.name+" raised an unexpected error", "error", err)
			return errorResult(prefix), nil
		}

		structured, err := json.Marshal(out)
		if err != nil {
			return nil, err
		}
		text, err := json.MarshalIndent(out, "", "  ")
		if err != nil {
			return nil, err
		}
		return &mcp.CallToolResult{
			Content:           []mcp.Content{&mcp.TextContent{Text: string(text)}},
			StructuredContent: json.RawMessage(structured),
		}, nil
	})
}

func errorResult(message string) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: message}},
		IsError: true,
	}
}
