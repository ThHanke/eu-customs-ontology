from uuid import UUID

from rdflib import Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD  # noqa: F401

EUCN = Namespace("https://w3id.org/eucn/")
ONTOLOGY_IRI = URIRef("https://w3id.org/eucn")
VANN = Namespace("http://purl.org/vocab/vann/")
BFO = Namespace("http://purl.obolibrary.org/obo/")
BFO_OBJECT = BFO["BFO_0000030"]
BFO_PROCESS = BFO["BFO_0000015"]
RO_HAS_OUTPUT = BFO["RO_0002234"]

# Fixed pipeline namespace UUID (v4, random, generated once, never changes)
PIPELINE_NS_UUID = UUID("a3e7c1d2-5f4b-4e8a-9c0d-1b2e3f4a5b6c")
