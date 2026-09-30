package telemetry

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"gopkg.in/natefinch/lumberjack.v2"
)

// Log files rotate at 10 MB, and the 5 most recent rotated files are kept.
const (
	maxLogFileMB   = 10
	maxLogBackups  = 5
	logFileSuffix  = ".log"
	fileTimeLayout = "2006-01-02 15:04:05"
)

// LoggerOptions configures NewLogger.
type LoggerOptions struct {
	Name  string
	Level slog.Level
	// Console logs to stderr. Used in the sandbox.
	Console bool
	// FilePath is a directory (the file is <Name>.log inside it) or, when it
	// has an extension, the file itself. Empty disables file logging.
	FilePath string
	// LoggerProvider, when set, also ships records over OTLP. Only INFO and
	// above go there, even when Level is DEBUG, so debug noise stays local.
	LoggerProvider *sdklog.LoggerProvider
}

// NewLogger builds the application logger. The returned closer releases the
// log file.
func NewLogger(opts LoggerOptions) (*slog.Logger, io.Closer, error) {
	var handlers []slog.Handler
	closer := io.Closer(nopCloser{})

	if opts.Console {
		handlers = append(handlers, slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: opts.Level}))
	}

	if opts.FilePath != "" {
		path := opts.FilePath
		if filepath.Ext(path) == "" {
			path = filepath.Join(path, opts.Name+logFileSuffix)
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return nil, nil, fmt.Errorf("creating log directory: %w", err)
		}
		file := &lumberjack.Logger{Filename: path, MaxSize: maxLogFileMB, MaxBackups: maxLogBackups}
		closer = file
		handlers = append(handlers, newLineHandler(file, opts.Name, opts.Level))
	}

	if opts.LoggerProvider != nil {
		otelHandler := otelslog.NewHandler(opts.Name, otelslog.WithLoggerProvider(opts.LoggerProvider))
		handlers = append(handlers, levelFilter{Handler: otelHandler, min: max(opts.Level, slog.LevelInfo)})
	}

	if len(handlers) == 0 {
		return slog.New(slog.DiscardHandler), closer, nil
	}
	return slog.New(slog.NewMultiHandler(handlers...)), closer, nil
}

type nopCloser struct{}

func (nopCloser) Close() error { return nil }

// levelFilter drops records below min before they reach Handler.
type levelFilter struct {
	slog.Handler
	min slog.Level
}

func (f levelFilter) Enabled(ctx context.Context, level slog.Level) bool {
	return level >= f.min && f.Handler.Enabled(ctx, level)
}

func (f levelFilter) WithAttrs(attrs []slog.Attr) slog.Handler {
	return levelFilter{Handler: f.Handler.WithAttrs(attrs), min: f.min}
}

func (f levelFilter) WithGroup(name string) slog.Handler {
	return levelFilter{Handler: f.Handler.WithGroup(name), min: f.min}
}

// lineHandler writes one plain-text line per record:
//
//	2006-01-02 15:04:05 [INFO] OrivMCP message key=value
type lineHandler struct {
	mu     *sync.Mutex
	out    io.Writer
	name   string
	level  slog.Level
	prefix string // pre-rendered attrs from WithAttrs
	group  string
}

func newLineHandler(out io.Writer, name string, level slog.Level) *lineHandler {
	return &lineHandler{mu: &sync.Mutex{}, out: out, name: name, level: level}
}

func (h *lineHandler) Enabled(_ context.Context, level slog.Level) bool { return level >= h.level }

func (h *lineHandler) Handle(_ context.Context, r slog.Record) error {
	var b strings.Builder
	t := r.Time
	if t.IsZero() {
		t = time.Now()
	}
	fmt.Fprintf(&b, "%s [%s] %s %s", t.Format(fileTimeLayout), levelName(r.Level), h.name, r.Message)
	b.WriteString(h.prefix)
	r.Attrs(func(a slog.Attr) bool {
		writeAttr(&b, h.group, a)
		return true
	})
	b.WriteByte('\n')

	h.mu.Lock()
	defer h.mu.Unlock()
	_, err := io.WriteString(h.out, b.String())
	return err
}

func (h *lineHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	clone := *h
	var b strings.Builder
	b.WriteString(h.prefix)
	for _, a := range attrs {
		writeAttr(&b, h.group, a)
	}
	clone.prefix = b.String()
	return &clone
}

func (h *lineHandler) WithGroup(name string) slog.Handler {
	clone := *h
	if clone.group != "" {
		clone.group += "."
	}
	clone.group += name
	return &clone
}

func writeAttr(b *strings.Builder, group string, a slog.Attr) {
	a.Value = a.Value.Resolve()
	if a.Equal(slog.Attr{}) {
		return
	}
	key := a.Key
	if group != "" {
		key = group + "." + key
	}
	if a.Value.Kind() == slog.KindGroup {
		for _, inner := range a.Value.Group() {
			writeAttr(b, key, inner)
		}
		return
	}
	fmt.Fprintf(b, " %s=%q", key, a.Value.String())
}

// levelName spells levels ERROR, WARNING, INFO and DEBUG (WARNING, not WARN),
// so searches and alerts written against earlier log files still match.
func levelName(level slog.Level) string {
	switch {
	case level >= slog.LevelError:
		return "ERROR"
	case level >= slog.LevelWarn:
		return "WARNING"
	case level >= slog.LevelInfo:
		return "INFO"
	default:
		return "DEBUG"
	}
}
