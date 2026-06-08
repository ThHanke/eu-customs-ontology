"""Manually curated owl:equivalentClass axioms for Chapter 22 product classes.

Encodes the discriminating physical criteria for each CN heading/subheading
using the canonical data properties from discriminating_props_beverages.py.

OWL 2 DL: no punning issues — named product classes (eucn:Beer etc.) are the
subjects of owl:equivalentClass. BNode intersection class is the object.

DEPRECATION NOTICE
------------------
This module is superseded by the LLM axiom agent pipeline
(src/agent/axiom_builder.py + src/agent/candidate_registry.py).
Once agent output for Chapter 22 has been manually validated for quality and
consistency (run Konclude check), this module should be retired by calling::

    from src.scripts.retire_chapter import retire_chapter
    retire_chapter(22)

Do NOT retire before validation — this module remains the authoritative source
until the agent pipeline is confirmed correct for all Ch22 product classes.
"""
from __future__ import annotations

from rdflib import Graph, Literal
from rdflib.namespace import XSD

from src.ontology.namespaces import EUCN
from src.ontology.owl_helpers import (
    _bnode,
    _build_list,
    _decimal_range_restr,
    _equiv,
    _has_value_restr,
    _neg_hasvalue_from_disjoint_equiv,
    _some_values_class_restr,
)


def add_equivalence_axioms_beverages(graph: Graph) -> None:
    pass  # retired 2026-06-08
