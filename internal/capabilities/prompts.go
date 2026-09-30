package capabilities

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const flightPlannerTemplate = `
You are a flight booking assistant.

Goal:
%s

Steps:
1. Identify origin and destination
2. Search flights using available tools
3. Compare prices
4. Suggest best option

Return structured steps.
`

func registerPrompts(server *mcp.Server) {
	server.AddPrompt(&mcp.Prompt{
		Name:        "flight_planner",
		Description: "Plan how to book a flight",
		Arguments:   []*mcp.PromptArgument{{Name: "input", Required: true}},
	}, func(_ context.Context, req *mcp.GetPromptRequest) (*mcp.GetPromptResult, error) {
		input, ok := req.Params.Arguments["input"]
		if !ok {
			return nil, &jsonrpc.Error{Code: jsonrpc.CodeInvalidParams, Message: "Missing required arguments: {'input'}"}
		}
		return &mcp.GetPromptResult{
			Description: "Plan how to book a flight",
			Messages: []*mcp.PromptMessage{{
				Role:    "user",
				Content: &mcp.TextContent{Text: fmt.Sprintf(flightPlannerTemplate, input)},
			}},
		}, nil
	})
}
