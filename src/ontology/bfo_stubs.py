from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from src.ontology.namespaces import BFO, BFO_HAS_PART, BFO_OBJECT, BFO_PROCESS, RO_HAS_OUTPUT, RO_HAS_QUALITY

BFO_ONTOLOGY_URI = URIRef("http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl")
RO_ONTOLOGY_URI = URIRef("http://purl.obolibrary.org/obo/ro.owl")

# BFO 2020 parent classes
BFO_INDEPENDENT_CONTINUANT = BFO["BFO_0000004"]  # parent of material entity (BFO_0000030)
BFO_OCCURRENT = BFO["BFO_0000003"]               # parent of process (BFO_0000015)


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
    # BFO_0000030 parent: independent continuant (BFO_0000004)
    g.add((BFO_OBJECT, RDFS.subClassOf, BFO_INDEPENDENT_CONTINUANT))
    g.add((BFO_INDEPENDENT_CONTINUANT, RDF.type, OWL.Class))
    g.add((BFO_INDEPENDENT_CONTINUANT, RDFS.label, Literal("independent continuant", lang="en")))
    g.add((BFO_INDEPENDENT_CONTINUANT, RDFS.label, Literal("unabhängige Kontinuante", lang="de")))
    g.add((BFO_INDEPENDENT_CONTINUANT, RDFS.isDefinedBy, BFO_ONTOLOGY_URI))
    g.add((BFO_INDEPENDENT_CONTINUANT, SKOS.definition, Literal(
        "continuant that is not specifically dependent on or generically dependent on any other entity",
        lang="en",
    )))
    g.add((BFO_INDEPENDENT_CONTINUANT, SKOS.definition, Literal(
        "Kontinuante, die weder spezifisch noch generisch von einer anderen Entität abhängig ist",
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
    # BFO_0000015 parent: occurrent (BFO_0000003)
    g.add((BFO_PROCESS, RDFS.subClassOf, BFO_OCCURRENT))
    g.add((BFO_OCCURRENT, RDF.type, OWL.Class))
    g.add((BFO_OCCURRENT, RDFS.label, Literal("occurrent", lang="en")))
    g.add((BFO_OCCURRENT, RDFS.label, Literal("Okkurrent", lang="de")))
    g.add((BFO_OCCURRENT, RDFS.isDefinedBy, BFO_ONTOLOGY_URI))
    g.add((BFO_OCCURRENT, SKOS.definition, Literal(
        "entity that unfolds itself in time or it is the instantaneous boundary of such an entity",
        lang="en",
    )))
    g.add((BFO_OCCURRENT, SKOS.definition, Literal(
        "Entität, die sich in der Zeit entfaltet oder die momentane Grenze einer solchen Entität ist",
        lang="de",
    )))
    # BFO:has_part (BFO_0000051)
    g.add((BFO_HAS_PART, RDF.type, OWL.ObjectProperty))
    g.add((BFO_HAS_PART, RDFS.label, Literal("has part", lang="en")))
    g.add((BFO_HAS_PART, RDFS.label, Literal("hat Teil", lang="de")))
    g.add((BFO_HAS_PART, RDFS.isDefinedBy, BFO_ONTOLOGY_URI))
    g.add((BFO_HAS_PART, SKOS.definition, Literal(
        "a core relation that holds between a whole and its parts",
        lang="en",
    )))

    # RO:has_quality (RO_0000086)
    g.add((RO_HAS_QUALITY, RDF.type, OWL.ObjectProperty))
    g.add((RO_HAS_QUALITY, RDFS.label, Literal("has quality", lang="en")))
    g.add((RO_HAS_QUALITY, RDFS.label, Literal("hat Eigenschaft", lang="de")))
    g.add((RO_HAS_QUALITY, RDFS.isDefinedBy, RO_ONTOLOGY_URI))
    g.add((RO_HAS_QUALITY, SKOS.definition, Literal(
        "a relation between an independent continuant and a quality that it bears",
        lang="en",
    )))
    g.add((RO_HAS_QUALITY, RDFS.domain, BFO_OBJECT))

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
