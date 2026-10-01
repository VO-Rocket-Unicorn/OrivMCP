package config

import "strings"

// A Host/Origin entry without a port only matches a request that carries no
// port either, so every bare entry is paired with this wildcard form.
const (
	PortWildcardSuffix = ":*"
	schemeSeparator    = "://"
)

// hasExplicitPort reports whether host pins a port. Bracketed IPv6 literals
// carry inner colons.
func hasExplicitPort(host string) bool {
	if strings.HasPrefix(host, "[") {
		closing := strings.Index(host, "]")
		return closing != -1 && strings.Contains(host[closing+1:], ":")
	}
	return strings.Contains(host, ":")
}

// expandHost pairs a bare host with its port-wildcard form; pinned ports are
// left alone.
func expandHost(host string) []string {
	if host == "" {
		return nil
	}
	if strings.HasSuffix(host, PortWildcardSuffix) || hasExplicitPort(host) {
		return []string{host}
	}
	return []string{host, host + PortWildcardSuffix}
}

// NormalizeHostEntry reduces an entry to Host-header form: no scheme, no
// path, plus wildcard.
func NormalizeHostEntry(entry string) []string {
	host := strings.TrimSpace(entry)
	if _, rest, ok := strings.Cut(host, schemeSeparator); ok {
		host = rest
	}
	host, _, _ = strings.Cut(host, RootPath)
	return expandHost(host)
}

// NormalizeOriginEntry reduces an entry to Origin-header form:
// scheme://host, no path, plus wildcard.
func NormalizeOriginEntry(entry string) []string {
	origin := strings.TrimSpace(entry)
	scheme, rest, ok := strings.Cut(origin, schemeSeparator)
	if !ok {
		return NormalizeHostEntry(origin)
	}
	rest, _, _ = strings.Cut(rest, RootPath)
	var out []string
	for _, host := range expandHost(rest) {
		out = append(out, scheme+schemeSeparator+host)
	}
	return out
}

// normalizeAll applies normalize to every entry and drops duplicates,
// keeping first-seen order.
func normalizeAll(entries []string, normalize func(string) []string) []string {
	seen := make(map[string]bool)
	out := []string{}
	for _, entry := range entries {
		for _, value := range normalize(entry) {
			if !seen[value] {
				seen[value] = true
				out = append(out, value)
			}
		}
	}
	return out
}
