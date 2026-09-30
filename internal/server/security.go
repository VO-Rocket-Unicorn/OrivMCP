package server

import (
	"log/slog"
	"net/http"
	"slices"
	"strings"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
)

// maxRequestBodyBytes caps an MCP request body at 4 MiB.
const maxRequestBodyBytes = 4 << 20

// transportGuard enforces the transport checks on the MCP endpoint: a JSON
// Content-Type on POST, a bounded body, and DNS-rebinding protection against
// the Host and Origin allowlists.
type transportGuard struct {
	allowedHosts   []string
	allowedOrigins []string
	logger         *slog.Logger
}

// matches reports whether value is allowed: an exact entry, or an entry
// ending in ":*" whose base matches with any port.
func matches(value string, allowed []string) bool {
	if slices.Contains(allowed, value) {
		return true
	}
	for _, entry := range allowed {
		if base, ok := strings.CutSuffix(entry, config.PortWildcardSuffix); ok && strings.HasPrefix(value, base+":") {
			return true
		}
	}
	return false
}

func (g transportGuard) wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			if r.ContentLength > maxRequestBodyBytes {
				http.Error(w, "Request body too large", http.StatusRequestEntityTooLarge)
				return
			}
			r.Body = http.MaxBytesReader(w, r.Body, maxRequestBodyBytes)

			contentType := r.Header.Get("Content-Type")
			if !strings.HasPrefix(strings.ToLower(contentType), "application/json") {
				http.Error(w, "Invalid Content-Type header", http.StatusBadRequest)
				return
			}
		}

		// Go keeps the Host header on the request itself, not in its headers.
		host := r.Host
		if host == "" {
			g.logger.Warn("Missing Host header in request")
			http.Error(w, "Invalid Host header", http.StatusMisdirectedRequest)
			return
		}
		if !matches(host, g.allowedHosts) {
			g.logger.Warn("Invalid Host header: " + host)
			http.Error(w, "Invalid Host header", http.StatusMisdirectedRequest)
			return
		}

		// Origin can be absent for same-origin and non-browser requests.
		if origin := r.Header.Get("Origin"); origin != "" && !matches(origin, g.allowedOrigins) {
			g.logger.Warn("Invalid Origin header: " + origin)
			http.Error(w, "Invalid Origin header", http.StatusForbidden)
			return
		}

		next.ServeHTTP(w, r)
	})
}
