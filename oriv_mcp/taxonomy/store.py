"""Flat, read-only index over the device-class taxonomy JSON.

The raw file is a nested tree. Tools need the facts the nesting leaves
implicit — a node's parent, its ancestry, how many children it has — without
walking the tree on every call, so the whole thing is flattened once at load.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLASSES_KEY = "classes"
CHILDREN_KEY = "children"
ID_KEY = "id"
NAME_KEY = "name"
DESCRIPTION_KEY = "description"
VERSION_KEY = "version"
PURPOSE_KEY = "purpose"


@dataclass(frozen=True)
class IndexEntry:
    """A taxonomy node plus its position in the tree."""

    node: dict[str, Any]
    parent_id: str | None
    path: tuple[str, ...]

    @property
    def id(self) -> str:
        return self.node[ID_KEY]

    @property
    def name(self) -> str:
        return self.node[NAME_KEY]

    @property
    def description(self) -> str:
        return self.node[DESCRIPTION_KEY]

    @property
    def child_ids(self) -> list[str]:
        return [child[ID_KEY] for child in self.node.get(CHILDREN_KEY, [])]

    @property
    def child_count(self) -> int:
        """0 means leaf — the caller can tell a leaf from an unexpanded branch."""
        return len(self.node.get(CHILDREN_KEY, []))


class UnknownDeviceClassError(KeyError):
    """Raised when an id is not present in the taxonomy."""


class DeviceClassTaxonomy:
    """Immutable in-memory view of the taxonomy."""

    def __init__(
        self,
        version: str,
        purpose: str,
        root_ids: list[str],
        index: dict[str, IndexEntry],
    ) -> None:
        self.version = version
        self.purpose = purpose
        self._root_ids = root_ids
        self._index = index

    def __len__(self) -> int:
        return len(self._index)

    @property
    def root_ids(self) -> list[str]:
        return list(self._root_ids)

    def entry(self, class_id: str) -> IndexEntry:
        """Look up one node, or raise if the id is unknown."""
        try:
            return self._index[class_id]
        except KeyError:
            raise UnknownDeviceClassError(class_id) from None

    def entries(self) -> list[IndexEntry]:
        return list(self._index.values())

    def children_of(self, parent_id: str | None) -> list[IndexEntry]:
        """Direct children of `parent_id`, or the top-level classes when None."""
        child_ids = (
            self._root_ids if parent_id is None else self.entry(parent_id).child_ids
        )
        return [self._index[child_id] for child_id in child_ids]

    def descendants_of(self, parent_id: str | None, depth: int) -> list[IndexEntry]:
        """Every node within `depth` levels below `parent_id`, breadth-first.

        Returned flat rather than nested: each entry carries its own `path`, so
        the caller can rebuild the hierarchy without an inline `children` array.
        """
        found: list[IndexEntry] = []
        frontier = self.children_of(parent_id)
        for _ in range(depth):
            if not frontier:
                break
            found.extend(frontier)
            frontier = [
                self._index[child_id]
                for entry in frontier
                for child_id in entry.child_ids
            ]
        return found

    def ancestors_of(self, class_id: str) -> list[IndexEntry]:
        """Root-first chain above the node, excluding the node itself."""
        return [self._index[ancestor_id] for ancestor_id in self.entry(class_id).path[:-1]]

    def siblings_of(self, class_id: str) -> list[IndexEntry]:
        """Nodes sharing a parent, excluding the node itself."""
        entry = self.entry(class_id)
        return [
            sibling
            for sibling in self.children_of(entry.parent_id)
            if sibling.id != class_id
        ]


def load_taxonomy(path: Path) -> DeviceClassTaxonomy:
    """Read the taxonomy file and flatten it into an id-keyed index."""
    raw = json.loads(Path(path).read_text())
    index: dict[str, IndexEntry] = {}

    def visit(
        nodes: list[dict[str, Any]],
        parent_id: str | None,
        parent_path: tuple[str, ...],
    ) -> list[str]:
        ids: list[str] = []
        for node in nodes:
            node_id = node[ID_KEY]
            if node_id in index:
                raise ValueError(f"Duplicate device-class id in taxonomy: {node_id}")
            node_path = parent_path + (node_id,)
            index[node_id] = IndexEntry(
                node=node, parent_id=parent_id, path=node_path
            )
            ids.append(node_id)
            visit(node.get(CHILDREN_KEY, []), node_id, node_path)
        return ids

    root_ids = visit(raw[CLASSES_KEY], None, ())
    return DeviceClassTaxonomy(
        version=raw[VERSION_KEY],
        purpose=raw[PURPOSE_KEY],
        root_ids=root_ids,
        index=index,
    )
