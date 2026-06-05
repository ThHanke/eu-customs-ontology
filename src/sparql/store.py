from __future__ import annotations

from pathlib import Path
from typing import Any

import pyoxigraph
from pyoxigraph import RdfFormat


class OntologyStore:
    def __init__(self) -> None:
        self._store = pyoxigraph.Store()

    def load_turtle(self, path: Path) -> None:
        self._store.bulk_load(path=str(path), format=RdfFormat.TURTLE)

    def query(self, sparql: str) -> list[dict[str, Any]]:
        results = self._store.query(sparql, use_default_graph_as_union=True)
        variables = results.variables  # on QuerySolutions, not QuerySolution
        out = []
        for row in results:
            out.append({var.value: _term(row[var]) for var in variables})
        return out

    def ask(self, sparql: str) -> bool:
        result = self._store.query(sparql, use_default_graph_as_union=True)
        # pyoxigraph returns QueryBoolean for ASK
        return bool(result)

    def count(self, sparql: str) -> int:
        rows = self.query(sparql)
        if rows and "count" in rows[0]:
            return int(str(rows[0]["count"]))
        return len(rows)


def _term(t: Any) -> Any:
    if t is None:
        return None
    if isinstance(t, pyoxigraph.Literal):
        val = t.value
        try:
            return float(val)
        except (ValueError, TypeError):
            return val
    if isinstance(t, (pyoxigraph.NamedNode, pyoxigraph.BlankNode)):
        return str(t)
    return str(t)
