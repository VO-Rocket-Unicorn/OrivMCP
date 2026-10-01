package server

import (
	"context"
	"errors"
	"log/slog"
	"strings"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestRecoverMiddlewareTurnsAPanicIntoAnInternalError(t *testing.T) {
	var logs syncBuilder
	logger := slog.New(slog.NewTextHandler(&logs, nil))
	handler := recoverMiddleware(logger)(func(context.Context, string, mcp.Request) (mcp.Result, error) {
		panic("boom")
	})

	result, err := handler(context.Background(), "tools/call", &mcp.CallToolRequest{})
	var wireErr *jsonrpc.Error
	if result != nil || !errors.As(err, &wireErr) || wireErr.Code != jsonrpc.CodeInternalError {
		t.Fatalf("result = %v, err = %v", result, err)
	}
	if strings.Contains(wireErr.Message, "boom") {
		t.Errorf("the panic value reached the client: %q", wireErr.Message)
	}
	if !strings.Contains(logs.String(), "panic while handling tools/call: boom") {
		t.Errorf("panic not logged:\n%s", logs.String())
	}
}

func TestRecoverMiddlewarePassesResultsThrough(t *testing.T) {
	want := &mcp.CallToolResult{}
	handler := recoverMiddleware(slog.New(slog.DiscardHandler))(func(context.Context, string, mcp.Request) (mcp.Result, error) {
		return want, nil
	})
	result, err := handler(context.Background(), "tools/call", &mcp.CallToolRequest{})
	if err != nil || result != want {
		t.Errorf("result = %v, err = %v", result, err)
	}
}
