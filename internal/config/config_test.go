package config

import (
	"reflect"
	"strings"
	"testing"
)

func TestNormalizeHostEntry(t *testing.T) {
	cases := map[string][]string{
		"localhost":                  {"localhost", "localhost:*"},
		" localhost ":                {"localhost", "localhost:*"},
		"localhost:8000":             {"localhost:8000"},
		"localhost:*":                {"localhost:*"},
		"https://example.com/mcp":    {"example.com", "example.com:*"},
		"https://example.com:443/x":  {"example.com:443"},
		"[::1]":                      {"[::1]", "[::1]:*"},
		"[::1]:8000":                 {"[::1]:8000"},
		"":                           nil,
		"http://":                    nil,
		"abc.ngrok-free.app/path/to": {"abc.ngrok-free.app", "abc.ngrok-free.app:*"},
	}
	for in, want := range cases {
		if got := NormalizeHostEntry(in); !reflect.DeepEqual(got, want) {
			t.Errorf("NormalizeHostEntry(%q) = %v, want %v", in, got, want)
		}
	}
}

func TestNormalizeOriginEntry(t *testing.T) {
	cases := map[string][]string{
		"http://localhost":          {"http://localhost", "http://localhost:*"},
		"http://localhost:3000/app": {"http://localhost:3000"},
		"https://[::1]":             {"https://[::1]", "https://[::1]:*"},
		"localhost":                 {"localhost", "localhost:*"},
	}
	for in, want := range cases {
		if got := NormalizeOriginEntry(in); !reflect.DeepEqual(got, want) {
			t.Errorf("NormalizeOriginEntry(%q) = %v, want %v", in, got, want)
		}
	}
}

func TestLoadDefaults(t *testing.T) {
	s, err := LoadFrom([]string{"OTEL_URL=http://otel:4318"}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if s.Server.ProjectName != "OrivMCP" || s.Server.Host != "0.0.0.0" || s.Server.Port != 8000 ||
		s.Server.Workers != 1 || s.Server.TimeoutKeepAlive != 5 || s.Server.MCPPath != "/mcp" {
		t.Errorf("server defaults: %+v", s.Server)
	}
	if s.App.Environment != EnvironmentProduction {
		t.Errorf("environment default: %q", s.App.Environment)
	}
	if s.HTTP.TimeoutSeconds != 10 || s.HTTP.MaxConnections != 20 {
		t.Errorf("http defaults: %+v", s.HTTP)
	}
	if len(s.Security.AllowedHosts) != 0 || len(s.Security.AllowedOrigins) != 0 {
		t.Errorf("security defaults: %+v", s.Security)
	}
	if got := s.URLs.OtelLogsURL(); got != "http://otel:4318/v1/logs" {
		t.Errorf("OtelLogsURL = %q", got)
	}
	if got := s.URLs.DeviceClassesSearchURL(); got != "/api/v1/device-classes/search" {
		t.Errorf("unconfigured DeviceClassesSearchURL = %q", got)
	}
}

func TestLoadOverridesAndPrecedence(t *testing.T) {
	s, err := LoadFrom(
		[]string{
			"OTEL_URL=http://otel:4318",
			"port= 9001 ",
			"ALLOWED_HOSTS=[\"localhost\",\"https://a.example.com/x\",\"localhost\"]",
			"ENVIRONMENT=sandbox",
			"ODAS_BASE_URL=https://odas.example",
		},
		map[string]string{"PORT": "1234", "PROJECT_NAME": "FromDotenv"},
	)
	if err != nil {
		t.Fatal(err)
	}
	if s.Server.Port != 9001 {
		t.Errorf("environment should win over .env: port = %d", s.Server.Port)
	}
	if s.Server.ProjectName != "FromDotenv" {
		t.Errorf(".env value not read: %q", s.Server.ProjectName)
	}
	wantHosts := []string{"localhost", "localhost:*", "a.example.com", "a.example.com:*"}
	if !reflect.DeepEqual(s.Security.AllowedHosts, wantHosts) {
		t.Errorf("AllowedHosts = %v, want %v", s.Security.AllowedHosts, wantHosts)
	}
	if s.App.LogLevel().String() != "DEBUG" {
		t.Errorf("sandbox log level = %v", s.App.LogLevel())
	}
	if got := s.URLs.OdasHealthURL(); got != "https://odas.example/health" {
		t.Errorf("OdasHealthURL = %q", got)
	}
}

func TestLoadErrors(t *testing.T) {
	_, err := LoadFrom([]string{
		"ALLOWED_HOSTS=a,b",
		"ENVIRONMENT=prod",
		"PORT=",
		"HTTP_TIMEOUT_SECONDS=0",
		"HTTP_MAX_CONNECTIONS=-1",
	}, nil)
	if err == nil {
		t.Fatal("expected an error")
	}
	for _, name := range []string{"OTEL_URL", "ALLOWED_HOSTS", "ENVIRONMENT", "PORT", "HTTP_TIMEOUT_SECONDS", "HTTP_MAX_CONNECTIONS"} {
		if !strings.Contains(err.Error(), name) {
			t.Errorf("error does not mention %s:\n%v", name, err)
		}
	}
}
