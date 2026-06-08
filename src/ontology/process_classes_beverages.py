"""Named BFO Process subclasses for CN Chapter 22 beverages.

Process classes are pairwise owl:disjointWith — the load-bearing world-closure
mechanism: eucn:producedBy is owl:FunctionalProperty, so if the unique producedBy
value is typed as (e.g.) MaltFermentation, Konclude can infer
NOT(producedBy someValuesFrom GrapeFermentation) via class disjointness.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 22 has been manually validated, retire via::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(22)

Do NOT retire before validation — the TBox process class vocabulary defined
here is required for correct OWL reasoning until the agent pipeline is
confirmed correct for all Ch22 process classes.
"""
from __future__ import annotations

from rdflib import Graph

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import _disjoint_pairs, _proc


def add_process_classes_beverages(graph: Graph) -> None:
    pass  # retired 2026-06-08
