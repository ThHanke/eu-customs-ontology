"""Named OWL product class hierarchy for CN Chapter 22 (Beverages).

All heading-level siblings are pairwise disjoint (owl:disjointWith).
Root eucn:Beverage is a subClassOf BFO:Object (BFO_0000030).
No owl:AllDisjointClasses — pairwise only (Konclude WASM constraint).

Each product class carries a rdfs:subClassOf owl:hasValue restriction on
eucn:cnHeadingCode so that the OWL reasoner propagates the CN code to
classified individuals automatically.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 22 has been manually validated, retire via::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(22)

Do NOT retire before validation — the TBox product class hierarchy defined
here is required for correct OWL reasoning until the agent pipeline is
confirmed correct for all Ch22 product classes.
"""
from __future__ import annotations

from rdflib import Graph, URIRef

from src.ontology.namespaces import BFO_OBJECT, EUCN
from src.ontology.owl_helpers import _bnode, _cls, _cn_heading, _disjoint_pairs, _sub


def add_product_classes_beverages(graph: Graph) -> None:
    pass  # retired 2026-06-08
