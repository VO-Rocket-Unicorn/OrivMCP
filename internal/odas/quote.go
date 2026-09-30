package odas

import "strings"

const upperHex = "0123456789ABCDEF"

// quote percent-encodes s for one URL path segment, byte for byte as
// Python's urllib.parse.quote(s, safe=safe) does. Letters, digits and
// "_.-~" are never encoded, and "/" is encoded unless it is in safe.
func quote(s, safe string) string {
	return escape(s, safe, false)
}

// queryEscape encodes a query key or value as urllib.parse.quote_plus does,
// which is how httpx built query strings in the Python implementation.
func queryEscape(s string) string {
	return escape(s, "", true)
}

func escape(s, safe string, plus bool) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case isUnreserved(c) || (c < 0x80 && strings.IndexByte(safe, c) >= 0):
			b.WriteByte(c)
		case plus && c == ' ':
			b.WriteByte('+')
		default:
			b.WriteByte('%')
			b.WriteByte(upperHex[c>>4])
			b.WriteByte(upperHex[c&0x0f])
		}
	}
	return b.String()
}

func isUnreserved(c byte) bool {
	return 'a' <= c && c <= 'z' || 'A' <= c && c <= 'Z' || '0' <= c && c <= '9' ||
		c == '_' || c == '.' || c == '-' || c == '~'
}
