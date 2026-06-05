from uuid import UUID

from rdflib import Namespace
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS, XSD  # noqa: F401

CUSTOMS = Namespace("https://eu-customs-ontology.example.org/ontology/")

# Fixed pipeline namespace UUID (v4, random, generated once, never changes)
PIPELINE_NS_UUID = UUID("a3e7c1d2-5f4b-4e8a-9c0d-1b2e3f4a5b6c")
