// Package telemetry wires the OpenTelemetry providers (traces, metrics, logs)
// and the application logger.
//
// It ports the parts of lib-oriv-telemetry this server uses. Export is
// OTLP/HTTP: every endpoint is a full URL, which is how the configuration
// builds them (OTEL_URL + /v1/logs|traces|metrics).
package telemetry

import (
	"context"
	"errors"
	"fmt"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploghttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

// metricExportInterval is how often metrics are pushed to the collector.
const metricExportInterval = 5 * time.Second

// Options configures the providers. An empty endpoint leaves that signal off.
type Options struct {
	ServiceName    string
	ServiceVersion string
	Environment    string
	TraceEndpoint  string
	LogEndpoint    string
	MetricEndpoint string
}

// Telemetry owns the process-wide providers.
type Telemetry struct {
	TracerProvider *sdktrace.TracerProvider
	MeterProvider  *sdkmetric.MeterProvider
	LoggerProvider *sdklog.LoggerProvider
}

// New builds the providers and installs them as the OpenTelemetry globals.
// Exporters connect lazily, so an unreachable collector does not stop the
// process from starting; export failures are reported by the SDK.
func New(ctx context.Context, opts Options) (*Telemetry, error) {
	res, err := resource.New(ctx,
		resource.WithFromEnv(),
		resource.WithTelemetrySDK(),
		resource.WithAttributes(
			attribute.String("service.name", opts.ServiceName),
			attribute.String("service.version", opts.ServiceVersion),
			attribute.String("deployment.environment", opts.Environment),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("telemetry resource: %w", err)
	}

	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{}, propagation.Baggage{},
	))

	t := &Telemetry{}

	if opts.MetricEndpoint != "" {
		exporter, err := otlpmetrichttp.New(ctx, otlpmetrichttp.WithEndpointURL(opts.MetricEndpoint))
		if err != nil {
			return nil, fmt.Errorf("metric exporter: %w", err)
		}
		t.MeterProvider = sdkmetric.NewMeterProvider(
			sdkmetric.WithResource(res),
			sdkmetric.WithReader(sdkmetric.NewPeriodicReader(exporter, sdkmetric.WithInterval(metricExportInterval))),
		)
		otel.SetMeterProvider(t.MeterProvider)
	}

	if opts.TraceEndpoint != "" {
		exporter, err := otlptracehttp.New(ctx, otlptracehttp.WithEndpointURL(opts.TraceEndpoint))
		if err != nil {
			return nil, fmt.Errorf("trace exporter: %w", err)
		}
		t.TracerProvider = sdktrace.NewTracerProvider(
			sdktrace.WithResource(res),
			sdktrace.WithBatcher(exporter),
		)
		otel.SetTracerProvider(t.TracerProvider)
	}

	if opts.LogEndpoint != "" {
		exporter, err := otlploghttp.New(ctx, otlploghttp.WithEndpointURL(opts.LogEndpoint))
		if err != nil {
			return nil, fmt.Errorf("log exporter: %w", err)
		}
		t.LoggerProvider = sdklog.NewLoggerProvider(
			sdklog.WithResource(res),
			sdklog.WithProcessor(sdklog.NewBatchProcessor(exporter)),
		)
	}

	return t, nil
}

// Shutdown flushes and stops every provider that was started.
func (t *Telemetry) Shutdown(ctx context.Context) error {
	var errs []error
	if t.TracerProvider != nil {
		errs = append(errs, t.TracerProvider.Shutdown(ctx))
	}
	if t.MeterProvider != nil {
		errs = append(errs, t.MeterProvider.Shutdown(ctx))
	}
	if t.LoggerProvider != nil {
		errs = append(errs, t.LoggerProvider.Shutdown(ctx))
	}
	return errors.Join(errs...)
}
