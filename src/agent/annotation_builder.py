from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from src.ontology.namespaces import EUCN
from src.schema.legal_text import LegalSection


def build_note_annotations(
    g: Graph,
    sections: list[LegalSection],
    cn_code_to_owl_class: dict[str, str],
) -> None:
    """Emit note resources, skos:definition, and eucn:hasExplanatoryNote links. Idempotent."""
    seen_note_ids: set[str] = set()

    for section in sections:
        note_iri = EUCN[f"note_{section.note_id[:8]}"]

        if section.note_id not in seen_note_ids:
            g.add((note_iri, RDF.type, EUCN["ExplanatoryNote"]))
            g.add((note_iri, EUCN["noteId"], Literal(section.note_id, datatype=XSD.string)))
            g.add((note_iri, EUCN["noteType"], Literal(section.note_type, datatype=XSD.string)))
            g.add((note_iri, EUCN["forCnCode"], Literal(section.cn_code, datatype=XSD.string)))
            g.add((note_iri, DCTERMS.modified, Literal(section.ingestion_date, datatype=XSD.date)))
            g.add((note_iri, DCTERMS.source, URIRef("https://webgate.ec.europa.eu/class-public-ui-web/")))
            seen_note_ids.add(section.note_id)

        g.add((note_iri, SKOS.definition, Literal(section.source_text, lang=section.language)))

        owl_class = cn_code_to_owl_class.get(section.cn_code)
        if owl_class is not None:
            cls_iri = EUCN[owl_class]
            g.add((cls_iri, SKOS.definition, Literal(section.source_text, lang=section.language)))
            g.add((cls_iri, EUCN["hasExplanatoryNote"], note_iri))
