from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.namespaces import BFO, BFO_OBJECT

BFO_ONTOLOGY_URI = URIRef("http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl")


def add_bfo_stubs(graph: Graph) -> None:
    """Declare BFO:Object stub. Idempotent."""
    g = graph
    g.bind("bfo", BFO)
    g.add((BFO_OBJECT, RDF.type, OWL.Class))
    g.add((BFO_OBJECT, RDFS.label, Literal("object", lang="en")))
    g.add((BFO_OBJECT, RDFS.label, Literal("Objekt", lang="de")))
    g.add((BFO_OBJECT, RDFS.isDefinedBy, BFO_ONTOLOGY_URI))
    g.add((BFO_OBJECT, SKOS.definition, Literal(
        "three-dimensional material entity that is spatially self-connected and is not "
        "a continuant part of any other material entity",
        lang="en",
    )))
    g.add((BFO_OBJECT, SKOS.definition, Literal(
        "dreidimensionale materielle Entität, die räumlich zusammenhängend ist und kein "
        "kontinuierender Teil einer anderen materiellen Entität ist",
        lang="de",
    )))
