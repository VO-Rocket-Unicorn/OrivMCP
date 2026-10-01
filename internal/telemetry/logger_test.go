package telemetry

import (
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func TestFileLoggerFormatAndLevel(t *testing.T) {
	dir := t.TempDir()
	logger, closer, err := NewLogger(LoggerOptions{Name: "OrivMCP", Level: slog.LevelInfo, FilePath: dir})
	if err != nil {
		t.Fatal(err)
	}
	logger.Debug("hidden")
	logger.With("service", "odas").Info("ODAS preflight: reachable", "url", "http://x")
	logger.Warn("careful")
	if err := closer.Close(); err != nil {
		t.Fatal(err)
	}

	data, err := os.ReadFile(filepath.Join(dir, "OrivMCP.log"))
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if len(lines) != 2 {
		t.Fatalf("want 2 lines (DEBUG filtered), got %q", lines)
	}
	info := regexp.MustCompile(`^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[INFO\] OrivMCP ODAS preflight: reachable service="odas" url="http://x"$`)
	if !info.MatchString(lines[0]) {
		t.Errorf("info line = %q", lines[0])
	}
	if !strings.Contains(lines[1], "[WARNING] OrivMCP careful") {
		t.Errorf("warn line = %q", lines[1])
	}
}

func TestFileLoggerExplicitFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nested", "app.log")
	logger, closer, err := NewLogger(LoggerOptions{Name: "OrivMCP", Level: slog.LevelDebug, FilePath: path})
	if err != nil {
		t.Fatal(err)
	}
	logger.Debug("shown")
	_ = closer.Close()
	if data, err := os.ReadFile(path); err != nil || !strings.Contains(string(data), "[DEBUG] OrivMCP shown") {
		t.Errorf("explicit file: %v %q", err, data)
	}
}
