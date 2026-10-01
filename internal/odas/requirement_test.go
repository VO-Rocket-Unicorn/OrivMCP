package odas

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

// fakeRequirements routes requirement reads to canned payloads.
type fakeRequirements struct {
	mu      sync.Mutex
	queries []string
	routes  map[string]func(http.ResponseWriter)
}

func (f *fakeRequirements) serve(t *testing.T) (*RequirementClient, *httptest.Server) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		f.queries = append(f.queries, r.URL.EscapedPath()+"?"+r.URL.RawQuery)
		f.mu.Unlock()
		if route, ok := f.routes[r.URL.EscapedPath()]; ok {
			route(w)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	t.Cleanup(srv.Close)
	client := NewRequirementClient(NewHTTPClient(2*time.Second, 4), discard, RequirementURLs{
		ProjectsURL:      srv.URL + "/api/v1/projects",
		RequirementsPath: "/requirements",
		AncestorsPath:    "/ancestors",
	})
	return client, srv
}

func payload200(v any) func(http.ResponseWriter) {
	return func(w http.ResponseWriter) {
		body, _ := json.Marshal(map[string]any{"respcode": 200, "payload": v})
		_, _ = w.Write(body)
	}
}

func row(id string, extra map[string]any) map[string]any {
	r := map[string]any{
		"requirementId": id, "name": "REQ-" + id, "level": "SYSTEM", "type": "FUNCTIONAL",
		"isAtomic": false, "altitude": "system", "childCount": 0, "path": []string{"r0"},
	}
	for k, v := range extra {
		r[k] = v
	}
	return r
}

const collection = "/api/v1/projects/p%2F1/requirements"

func TestRootsQueryAndListing(t *testing.T) {
	f := &fakeRequirements{routes: map[string]func(http.ResponseWriter){
		collection: payload200(map[string]any{"items": []any{row("r1", nil)}, "total": 30}),
	}}
	client, _ := f.serve(t)
	system := schemas.ChildAltitudeSystem
	exclude := "r9"
	listing, err := client.Roots(context.Background(), NewSecret("t"), "p/1", &system, &exclude, 2, 10)
	if err != nil {
		t.Fatal(err)
	}
	wantQuery := collection + "?parentId=none&altitude=stakeholder%2Csystem&excludeSubtreeOf=r9&sort=name&view=compact&page=2&limit=10"
	if f.queries[0] != wantQuery {
		t.Errorf("query = %s\nwant    %s", f.queries[0], wantQuery)
	}
	// ODAS echoed no window, so the requested one applies: 2*10 < 30.
	if listing.Page != 2 || listing.Limit != 10 || listing.Total != 30 || !listing.HasMore {
		t.Errorf("listing window = %+v", listing)
	}
	if listing.Items[0].Path != nil {
		t.Error("roots must not carry a path")
	}
}

func TestSearchCarriesPathsAndAppliedWindow(t *testing.T) {
	f := &fakeRequirements{routes: map[string]func(http.ResponseWriter){
		collection: payload200(map[string]any{
			"items": []any{
				row("r2", nil),
				// ODAS's other spellings: id, description, is_atomic, child_count, no path.
				map[string]any{"id": "r3", "name": "REQ-3", "description": "desc", "level": "UNKNOWN",
					"type": "NON_FUNCTIONAL", "is_atomic": true, "altitude": "unknown", "child_count": 4},
			},
			"total": 60, "page": 1, "limit": 50,
		}),
	}}
	client, _ := f.serve(t)
	functional := schemas.RequirementTypeFunctional
	listing, err := client.Search(context.Background(), NewSecret("t"), "p/1", "power supply", nil, &functional, nil, nil, 1, 25)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(f.queries[0], "?q=power+supply&type=FUNCTIONAL&sort=name") {
		t.Errorf("query = %s", f.queries[0])
	}
	if listing.Limit != 50 || !listing.HasMore {
		t.Errorf("applied window not used: %+v", listing)
	}
	if p := listing.Items[0].Path; p == nil || strings.Join(*p, ",") != "r0" {
		t.Errorf("first hit path = %v", p)
	}
	second := listing.Items[1]
	if p := second.Path; p == nil || len(*p) != 0 {
		t.Errorf("a hit with no path must carry [] not null: %v", p)
	}
	if second.ID != "r3" || second.Statement != "desc" || !second.IsAtomic || second.ChildCount != 4 {
		t.Errorf("alias fields not read: %+v", second)
	}
}

func TestListingRejectsRowWithoutChildCount(t *testing.T) {
	bad := row("r1", nil)
	delete(bad, "childCount")
	f := &fakeRequirements{routes: map[string]func(http.ResponseWriter){
		collection: payload200(map[string]any{"items": []any{bad}, "total": 1}),
	}}
	client, _ := f.serve(t)
	_, err := client.Children(context.Background(), NewSecret("t"), "p/1", "r0", nil, nil, 1, 25)
	if got := toolMessage(t, err); !strings.Contains(got, "does not match the expected shape") {
		t.Errorf("message = %q", got)
	}
}

func TestNodeParentPrecedence(t *testing.T) {
	cases := map[string]struct {
		extra map[string]any
		want  string
	}{
		"object":        {map[string]any{"parent": map[string]any{"requirementId": "pa"}, "parentId": "pb"}, "pa"},
		"scalar":        {map[string]any{"parentId": "pb", "parents": []string{"pc"}}, "pb"},
		"legacy":        {map[string]any{"parents": []string{"pc", "pd"}}, "pc"},
		"empty scalar":  {map[string]any{"parentId": "", "parents": []string{"pc"}}, "pc"},
		"root (absent)": {map[string]any{}, ""},
	}
	for name, c := range cases {
		t.Run(name, func(t *testing.T) {
			f := &fakeRequirements{routes: map[string]func(http.ResponseWriter){
				collection + "/r2":           payload200(row("r2", c.extra)),
				collection + "/r2/ancestors": payload200(map[string]any{"items": []any{map[string]any{"requirementId": "r1", "name": "REQ-1"}}}),
			}}
			client, _ := f.serve(t)
			detail, err := client.Node(context.Background(), NewSecret("t"), "p/1", "r2")
			if err != nil {
				t.Fatal(err)
			}
			got := ""
			if detail.ParentID != nil {
				got = *detail.ParentID
			}
			if got != c.want {
				t.Errorf("parentId = %q, want %q", got, c.want)
			}
			if strings.Join(detail.Path, ",") != "r1" {
				t.Errorf("path = %v", detail.Path)
			}
		})
	}
}

func TestNodeFailsWhenEitherReadFails(t *testing.T) {
	f := &fakeRequirements{routes: map[string]func(http.ResponseWriter){
		collection + "/r2": payload200(row("r2", nil)),
		collection + "/r2/ancestors": func(w http.ResponseWriter) {
			w.WriteHeader(http.StatusInternalServerError)
		},
	}}
	client, _ := f.serve(t)
	_, err := client.Node(context.Background(), NewSecret("t"), "p/1", "r2")
	if got := toolMessage(t, err); !strings.HasPrefix(got, "The requirements API is unavailable.") {
		t.Errorf("message = %q", got)
	}
}

func TestLegalParentAltitudes(t *testing.T) {
	cases := map[schemas.ChildAltitude]string{
		schemas.ChildAltitudeStakeholder: "stakeholder",
		schemas.ChildAltitudeSystem:      "stakeholder,system",
		schemas.ChildAltitudeAtomic:      "stakeholder,system,atomic",
	}
	for child, want := range cases {
		got, err := altitudes(&child)
		if err != nil || *got != want {
			t.Errorf("altitudes(%s) = %v, %v; want %s", child, got, err, want)
		}
	}
	if got, _ := altitudes(nil); got != nil {
		t.Error("no child altitude must mean no filter")
	}
}
