package schemas

import "encoding/json"

// DeviceClassNode is the shape every device-class tool returns for a node.
//
// Children are deliberately never inlined: they arrive from the next
// list_device_classes call or from get_device_class.
type DeviceClassNode struct {
	ID          string   `json:"id" jsonschema:"Unique id of the device class."`
	Name        string   `json:"name" jsonschema:"Human-readable name of the device class."`
	Description string   `json:"description" jsonschema:"What this device class covers."`
	ChildCount  int      `json:"childCount" jsonschema:"Number of direct children. 0 means leaf — use this to tell a leaf from a branch that simply has not been expanded yet."`
	Path        []string `json:"path" jsonschema:"Ids from the root of the taxonomy down to this node, inclusive."`
}

func (n *DeviceClassNode) UnmarshalJSON(data []byte) error {
	o, err := newObject("DeviceClassNode", data)
	if err != nil {
		return err
	}
	var v DeviceClassNode
	required(o, &v.ID, "id")
	required(o, &v.Name, "name")
	required(o, &v.Description, "description")
	required(o, &v.ChildCount, "childCount", "child_count")
	required(o, &v.Path, "path")
	v.Path = orEmpty(v.Path)
	*n = v
	return o.err()
}

type ListDeviceClassesOutput struct {
	Nodes      []DeviceClassNode `json:"nodes" jsonschema:"Nodes within the requested depth, breadth-first. Flat, not nested: rebuild the hierarchy from each node's path."`
	NextCursor *string           `json:"nextCursor" jsonschema:"Always null today — the tree is small enough to return whole. Reserved so the contract survives a larger taxonomy."`
}

func (l *ListDeviceClassesOutput) UnmarshalJSON(data []byte) error {
	o, err := newObject("ListDeviceClassesOutput", data)
	if err != nil {
		return err
	}
	var v ListDeviceClassesOutput
	required(o, &v.Nodes, "nodes")
	optional(o, &v.NextCursor, "nextCursor", "next_cursor")
	v.Nodes = orEmpty(v.Nodes)
	*l = v
	return o.err()
}

type SearchDeviceClassesOutput struct {
	Nodes []DeviceClassNode `json:"nodes" jsonschema:"Matches ordered by relevance: exact name, then name substring, then description substring. Empty when nothing matches."`
}

func (s *SearchDeviceClassesOutput) UnmarshalJSON(data []byte) error {
	o, err := newObject("SearchDeviceClassesOutput", data)
	if err != nil {
		return err
	}
	var v SearchDeviceClassesOutput
	required(o, &v.Nodes, "nodes")
	v.Nodes = orEmpty(v.Nodes)
	*s = v
	return o.err()
}

type GetDeviceClassOutput struct {
	Node      DeviceClassNode   `json:"node" jsonschema:"The requested device class."`
	Ancestors []DeviceClassNode `json:"ancestors" jsonschema:"Chain from the root down to the parent, root first. Empty for a top-level class."`
	Children  []DeviceClassNode `json:"children" jsonschema:"Direct children. Empty for a leaf."`
	Siblings  []DeviceClassNode `json:"siblings" jsonschema:"Classes sharing the same parent, excluding this one — the classes most likely to be confused with it."`
}

func (g *GetDeviceClassOutput) UnmarshalJSON(data []byte) error {
	o, err := newObject("GetDeviceClassOutput", data)
	if err != nil {
		return err
	}
	var v GetDeviceClassOutput
	required(o, &v.Node, "node")
	required(o, &v.Ancestors, "ancestors")
	required(o, &v.Children, "children")
	required(o, &v.Siblings, "siblings")
	v.Ancestors, v.Children, v.Siblings = orEmpty(v.Ancestors), orEmpty(v.Children), orEmpty(v.Siblings)
	*g = v
	return o.err()
}

type ListDeviceClassVendorsOutput struct {
	Vendors []string `json:"vendors" jsonschema:"Vendor names with a datasheet profile for this device class."`
}

func (l *ListDeviceClassVendorsOutput) UnmarshalJSON(data []byte) error {
	o, err := newObject("ListDeviceClassVendorsOutput", data)
	if err != nil {
		return err
	}
	var v ListDeviceClassVendorsOutput
	required(o, &v.Vendors, "vendors")
	v.Vendors = orEmpty(v.Vendors)
	*l = v
	return o.err()
}

var (
	_ json.Unmarshaler = (*DeviceClassNode)(nil)
	_ json.Unmarshaler = (*GetDeviceClassOutput)(nil)
)
