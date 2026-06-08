from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.namespaces import BFO, BFO_OBJECT, BFO_PROCESS, RO_HAS_OUTPUT

BFO_ONTOLOGY_URI = URIRef("http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl")
RO_ONTOLOGY_URI = URIRef("http://purl.obolibrary.org/obo/ro.owl")


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
    # BFO:Process
    g.add((BFO_PROCESS, RDF.type, OWL.Class))
    g.add((BFO_PROCESS, RDFS.label, Literal("process", lang="en")))
    g.add((BFO_PROCESS, RDFS.label, Literal("Prozess", lang="de")))
    g.add((BFO_PROCESS, RDFS.isDefinedBy, BFO_ONTOLOGY_URI))
    g.add((BFO_PROCESS, SKOS.definition, Literal(
        "entity that exists in time by occurring or happening, and that has temporal parts",
        lang="en",
    )))
    g.add((BFO_PROCESS, SKOS.definition, Literal(
        "Entität, die in der Zeit durch Geschehen oder Stattfinden existiert und zeitliche Teile hat",
        lang="de",
    )))
    # RO:has_output
    g.add((RO_HAS_OUTPUT, RDF.type, OWL.ObjectProperty))
    g.add((RO_HAS_OUTPUT, RDFS.label, Literal("has output", lang="en")))
    g.add((RO_HAS_OUTPUT, RDFS.label, Literal("hat Ausgabe", lang="de")))
    g.add((RO_HAS_OUTPUT, RDFS.isDefinedBy, RO_ONTOLOGY_URI))
    g.add((RO_HAS_OUTPUT, SKOS.definition, Literal(
        "a relation between a process and a continuant entity that the process brings into existence",
        lang="en",
    )))
    g.add((RO_HAS_OUTPUT, SKOS.definition, Literal(
        "Beziehung zwischen einem Prozess und einer Kontinuant-Entität, die der Prozess ins Dasein bringt",
        lang="de",
    )))
