from __future__ import annotations

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

from src.ontology.namespaces import DCTERMS, EUCN

PROV_GRAPH_IRI = EUCN["provenance"]


def build_provenance(
    ds: Dataset,
    run_id: str,
    chapter: int,
    sources: list[str],
) -> Graph:
    """Add a prov:Activity individual to the provenance named graph."""
    pg = ds.graph(PROV_GRAPH_IRI)
    pg.bind("prov", PROV)
    pg.bind("dcterms", DCTERMS)
    pg.bind("eucn", EUCN)

    activity_iri = EUCN[f"run/{run_id}"]
    pg.add((activity_iri, RDF.type, PROV.Activity))
    pg.add((activity_iri, DCTERMS.description,
            Literal(f"Pipeline run for Chapter {chapter:02d}", datatype=XSD.string)))
    for src in sources:
        pg.add((activity_iri, DCTERMS.source, URIRef(src)))

    return pg
