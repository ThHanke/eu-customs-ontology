from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_checkpoint(path: Path, visited: set[str], frontier: list[dict]) -> None:
    path.write_text(json.dumps({
        "visited": list(visited),
        "frontier": frontier,
    }, indent=2))


def append_node_jsonl(path: Path, node_data: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(node_data, default=str) + "\n")


def load_nodes_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    nodes = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            nodes.append(json.loads(line))
    return nodes
