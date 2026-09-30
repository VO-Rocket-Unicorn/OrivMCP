package schemas

// Schemas for the AI decision-tree walk and its taxonomy resolution.
//
// The wire shape here is already snake_case and clean, so unlike the
// requirement schemas one set of types suffices; there is no raw ODAS layer
// to translate out of.

// DecisionAnswer is one selectable answer to a decision-tree question.
type DecisionAnswer struct {
	Value          string  `json:"value" jsonschema:"The answer text to match the user's reply against."`
	Next           *string `json:"next" jsonschema:"Id of the next question node to ask. Null when this answer reaches a leaf."`
	ResolvesToward *string `json:"resolves_toward" jsonschema:"The architecture name this answer resolves to. Present only when next is null — pass it to resolve_architecture to get the full record."`
	Label          *string `json:"label" jsonschema:"Human-readable button/option text for this answer, distinct from the machine-key value. Not every tree supplies it."`
}

func (a *DecisionAnswer) UnmarshalJSON(data []byte) error {
	o, err := newObject("DecisionAnswer", data)
	if err != nil {
		return err
	}
	var v DecisionAnswer
	required(o, &v.Value, "value")
	optional(o, &v.Next, "next")
	optional(o, &v.ResolvesToward, "resolves_toward")
	optional(o, &v.Label, "label")
	*a = v
	return o.err()
}

// DecisionNode is one question in the decision tree.
type DecisionNode struct {
	ID                  string           `json:"id" jsonschema:"Unique id of this question node."`
	Question            string           `json:"question" jsonschema:"The question to ask the user, verbatim."`
	EvidenceType        string           `json:"evidence_type" jsonschema:"Kind of evidence this question is asking about."`
	RecognitionTriggers []string         `json:"recognition_triggers" jsonschema:"Keywords/phrases that suggest this question is relevant."`
	Answers             []DecisionAnswer `json:"answers" jsonschema:"Possible answers, each pointing to the next node or a resolution."`
}

func (n *DecisionNode) UnmarshalJSON(data []byte) error {
	o, err := newObject("DecisionNode", data)
	if err != nil {
		return err
	}
	var v DecisionNode
	required(o, &v.ID, "id")
	required(o, &v.Question, "question")
	required(o, &v.EvidenceType, "evidence_type")
	optional(o, &v.RecognitionTriggers, "recognition_triggers")
	optional(o, &v.Answers, "answers")
	v.RecognitionTriggers, v.Answers = orEmpty(v.RecognitionTriggers), orEmpty(v.Answers)
	*n = v
	return o.err()
}

// DecisionTree is the full AI decision tree for one device class, returned
// in one response.
//
// Walk it in memory: look up RootQuestionID in Nodes, ask its question, match
// the reply to one of its answers, then follow that answer's next into Nodes
// again. Stop when an answer's next is null; that answer's resolves_toward
// is the result.
type DecisionTree struct {
	TreeID          string                  `json:"tree_id" jsonschema:"Id of this decision tree."`
	Version         string                  `json:"version" jsonschema:"Version of this decision tree."`
	TaxonomyRef     string                  `json:"taxonomy_ref" jsonschema:"Id of the taxonomy this tree resolves into."`
	TaxonomyVersion string                  `json:"taxonomy_version" jsonschema:"Version of the referenced taxonomy."`
	RootQuestionID  string                  `json:"root_question_id" jsonschema:"Id of the node in nodes to start asking from."`
	Nodes           map[string]DecisionNode `json:"nodes" jsonschema:"Every question node in the tree, keyed by node id."`
}

func (t *DecisionTree) UnmarshalJSON(data []byte) error {
	o, err := newObject("DecisionTree", data)
	if err != nil {
		return err
	}
	var v DecisionTree
	required(o, &v.TreeID, "tree_id")
	required(o, &v.Version, "version")
	required(o, &v.TaxonomyRef, "taxonomy_ref")
	required(o, &v.TaxonomyVersion, "taxonomy_version")
	required(o, &v.RootQuestionID, "root_question_id")
	required(o, &v.Nodes, "nodes")
	if v.Nodes == nil {
		v.Nodes = map[string]DecisionNode{}
	}
	*t = v
	return o.err()
}

// DecisionTreeNodeResponse is the response of fetching a single
// decision-tree node, call-per-question.
type DecisionTreeNodeResponse struct {
	Node DecisionNode `json:"node"`
}

func (r *DecisionTreeNodeResponse) UnmarshalJSON(data []byte) error {
	o, err := newObject("DecisionTreeNodeResponse", data)
	if err != nil {
		return err
	}
	var v DecisionTreeNodeResponse
	required(o, &v.Node, "node")
	*r = v
	return o.err()
}

// ArchitectureDetail is one resolved architecture leaf from the taxonomy.
type ArchitectureDetail struct {
	ID                      string  `json:"id" jsonschema:"Unique id of the architecture."`
	Name                    string  `json:"name" jsonschema:"Human-readable name of the architecture."`
	Type                    string  `json:"type" jsonschema:"Taxonomy node type, e.g. 'device_class'."`
	ParentID                *string `json:"parent_id" jsonschema:"Id of the parent taxonomy node, if any."`
	Definition              string  `json:"definition" jsonschema:"What this architecture is."`
	DistinguishingMechanism string  `json:"distinguishing_mechanism" jsonschema:"What distinguishes this architecture from its siblings."`
	CanonicalSpecRef        string  `json:"canonical_spec_ref" jsonschema:"Reference to the canonical specification for this architecture."`
}

func (a *ArchitectureDetail) UnmarshalJSON(data []byte) error {
	o, err := newObject("ArchitectureDetail", data)
	if err != nil {
		return err
	}
	var v ArchitectureDetail
	required(o, &v.ID, "id")
	required(o, &v.Name, "name")
	required(o, &v.Type, "type")
	optional(o, &v.ParentID, "parent_id")
	optional(o, &v.Definition, "definition")
	optional(o, &v.DistinguishingMechanism, "distinguishing_mechanism")
	optional(o, &v.CanonicalSpecRef, "canonical_spec_ref")
	*a = v
	return o.err()
}

// TaxonomyLookupResponse is the response of resolving an architecture name
// against a device class's taxonomy.
type TaxonomyLookupResponse struct {
	TaxonomyID      string               `json:"taxonomyid"`
	TaxonomyVersion string               `json:"taxonomy_version"`
	DeviceClass     string               `json:"device_class"`
	Leaves          []ArchitectureDetail `json:"leaves"`
}

func (r *TaxonomyLookupResponse) UnmarshalJSON(data []byte) error {
	o, err := newObject("TaxonomyLookupResponse", data)
	if err != nil {
		return err
	}
	var v TaxonomyLookupResponse
	required(o, &v.TaxonomyID, "taxonomyid")
	required(o, &v.TaxonomyVersion, "taxonomy_version")
	required(o, &v.DeviceClass, "device_class")
	optional(o, &v.Leaves, "leaves")
	*r = v
	return o.err()
}
