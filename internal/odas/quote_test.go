package odas

import "testing"

// Expected values were produced by Python's urllib.parse.quote and
// quote_plus, so the paths and query strings sent to ODAS stay exactly the
// ones it has always received.
func TestQuoteMatchesPython(t *testing.T) {
	cases := []struct {
		in, safeColon, safeNone, plus string
	}{
		{"class:adc", "class:adc", "class%3Aadc", "class%3Aadc"},
		{"group:analog/x", "group:analog%2Fx", "group%3Aanalog%2Fx", "group%3Aanalog%2Fx"},
		{"a b", "a%20b", "a%20b", "a+b"},
		{"adc.sar", "adc.sar", "adc.sar", "adc.sar"},
		{"x~y_z-1.2", "x~y_z-1.2", "x~y_z-1.2", "x~y_z-1.2"},
		{"100%", "100%25", "100%25", "100%25"},
		{"é/ü", "%C3%A9%2F%C3%BC", "%C3%A9%2F%C3%BC", "%C3%A9%2F%C3%BC"},
		{"q?#&=+,;", "q%3F%23%26%3D%2B%2C%3B", "q%3F%23%26%3D%2B%2C%3B", "q%3F%23%26%3D%2B%2C%3B"},
		{"[::1]", "%5B::1%5D", "%5B%3A%3A1%5D", "%5B%3A%3A1%5D"},
		{"", "", "", ""},
	}
	for _, c := range cases {
		if got := quote(c.in, ":"); got != c.safeColon {
			t.Errorf("quote(%q, \":\") = %q, want %q", c.in, got, c.safeColon)
		}
		if got := quote(c.in, ""); got != c.safeNone {
			t.Errorf("quote(%q, \"\") = %q, want %q", c.in, got, c.safeNone)
		}
		if got := queryEscape(c.in); got != c.plus {
			t.Errorf("queryEscape(%q) = %q, want %q", c.in, got, c.plus)
		}
	}
}

func TestEncodeQueryDropsNilAndKeepsOrder(t *testing.T) {
	var none *string
	some := "x y"
	got := encodeQuery([]param{{"b", 2}, {"a", none}, {"c", &some}, {"d", nil}, {"e", "v"}})
	if want := "b=2&c=x+y&e=v"; got != want {
		t.Errorf("encodeQuery = %q, want %q", got, want)
	}
}

func TestSecretIsMasked(t *testing.T) {
	s := NewSecret("hunter2")
	for _, rendered := range []string{s.String(), s.GoString(), s.LogValue().String()} {
		if rendered == "hunter2" || rendered == "" {
			t.Errorf("secret rendered as %q", rendered)
		}
	}
	if s.Reveal() != "hunter2" {
		t.Error("Reveal lost the value")
	}
}
