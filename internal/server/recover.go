package server

import (
	"context"
	"fmt"
	"log/slog"
	"runtime/debug"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// recoverMiddleware turns a panic while handling one MCP message into an
// internal error for that message.
//
// The SDK runs handlers on its own goroutines and recovers nothing, so
// without this a single bad tool call would end the process, and with it
// every other session, including the host application when the server runs
// in-process.
func recoverMiddleware(logger *slog.Logger) mcp.Middleware {
	return func(next mcp.MethodHandler) mcp.MethodHandler {
		return func(ctx context.Context, method string, req mcp.Request) (result mcp.Result, err error) {
			defer func() {
				if r := recover(); r != nil {
					logger.ErrorContext(ctx, fmt.Sprintf("panic while handling %s: %v\n%s", method, r, debug.Stack()))
					result = nil
					err = &jsonrpc.Error{Code: jsonrpc.CodeInternalError, Message: "internal error"}
				}
			}()
			return next(ctx, method, req)
		}
	}
}
