package server

import (
	"context"
	"errors"
	"fmt"
	"reflect"
	"strconv"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

const tracerName = "github.com/VO-Rocket-Unicorn/OrivMCP/internal/server"

// tracingMiddleware wraps each inbound MCP message in a SERVER span: named
// "<method> <tool or prompt>", parented on the W3C trace context a client may
// carry in params._meta, and marked as an error when the call fails or a tool
// reports one.
func tracingMiddleware(next mcp.MethodHandler) mcp.MethodHandler {
	tracer := otel.Tracer(tracerName)
	return func(ctx context.Context, method string, req mcp.Request) (mcp.Result, error) {
		target := ""
		switch p := req.GetParams().(type) {
		case *mcp.CallToolParamsRaw:
			if p != nil {
				target = p.Name
			}
		case *mcp.GetPromptParams:
			if p != nil {
				target = p.Name
			}
		}

		attrs := []attribute.KeyValue{attribute.String("mcp.method.name", method)}
		if session, ok := req.GetSession().(*mcp.ServerSession); ok {
			if init := session.InitializeParams(); init != nil {
				attrs = append(attrs, attribute.String("mcp.protocol.version", init.ProtocolVersion))
			}
		}
		switch {
		case method == "tools/call":
			attrs = append(attrs, attribute.String("gen_ai.operation.name", "execute_tool"))
			if target != "" {
				attrs = append(attrs, attribute.String("gen_ai.tool.name", target))
			}
		case method == "prompts/get" && target != "":
			attrs = append(attrs, attribute.String("gen_ai.prompt.name", target))
		}

		name := method
		if target != "" {
			name += " " + target
		}
		ctx = extractTraceContext(ctx, req.GetParams())
		ctx, span := tracer.Start(ctx, name, trace.WithSpanKind(trace.SpanKindServer), trace.WithAttributes(attrs...))
		defer span.End()

		result, err := next(ctx, method, req)
		if err != nil {
			var wireErr *jsonrpc.Error
			if errors.As(err, &wireErr) {
				code := strconv.FormatInt(wireErr.Code, 10)
				span.SetAttributes(attribute.String("error.type", code), attribute.String("rpc.response.status_code", code))
				span.SetStatus(codes.Error, wireErr.Message)
			} else {
				span.SetAttributes(attribute.String("error.type", fmt.Sprintf("%T", err)))
				span.RecordError(err)
				span.SetStatus(codes.Error, err.Error())
			}
			return result, err
		}
		if toolResult, ok := result.(*mcp.CallToolResult); ok && toolResult.IsError {
			span.SetAttributes(attribute.String("error.type", "tool_error"))
			span.SetStatus(codes.Error, "")
		}
		return result, nil
	}
}

// extractTraceContext parents the span on a traceparent carried in _meta,
// falling back to the ambient context when there is none or it is invalid.
func extractTraceContext(ctx context.Context, params mcp.Params) context.Context {
	// A message without params (notifications/initialized, say) arrives as a
	// typed nil pointer, whose GetMeta would panic.
	if params == nil || reflect.ValueOf(params).IsNil() {
		return ctx
	}
	meta := params.GetMeta()
	if len(meta) == 0 {
		return ctx
	}
	carrier := propagation.MapCarrier{}
	for key, value := range meta {
		if s, ok := value.(string); ok {
			carrier[key] = s
		}
	}
	extracted := otel.GetTextMapPropagator().Extract(ctx, carrier)
	if !trace.SpanContextFromContext(extracted).IsValid() {
		return ctx
	}
	return extracted
}
