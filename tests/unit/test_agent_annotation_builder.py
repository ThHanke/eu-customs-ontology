from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from src.agent.annotation_builder import build_note_annotations
from src.ontology.namespaces import DCTERMS, EUCN
from src.schema.legal_text import LegalSection


def _section(note_id, lang, source_text, cn_code="220820", note_type="CNEN HS Subheading Notes"):
    return LegalSection(
        note_id=note_id,
        chapter=22,
        cn_code=cn_code,
        note_type=note_type,
        source_text=source_text,
        ingestion_date="2023-10-06",
        language=lang,
        source_url="https://webgate.ec.europa.eu/class-public-ui-web/#/search",
        fetched_at="2026-06-08",
    )


NOTE_ID = "abcd1234efgh5678"
MAPPING = {"220820": "WhiskySpirit"}


def test_single_en_section_mapped_cn_code():
    g = Graph()
    s = _section(NOTE_ID, "en", "Whisky is a spirit.", cn_code="220820")
    build_note_annotations(g, [s], MAPPING)

    note_iri = EUCN[f"note_{NOTE_ID[:8]}"]
    cls_iri = EUCN["WhiskySpirit"]
    defn = Literal("Whisky is a spirit.", lang="en")

    assert (note_iri, SKOS.definition, defn) in g
    assert (cls_iri, SKOS.definition, defn) in g


def test_bilingual_single_note_id_no_duplicate_metadata():
    g = Graph()
    s_en = _section(NOTE_ID, "en", "Whisky is a spirit.")
    s_de = _section(NOTE_ID, "de", "Whisky ist ein Spirituose.")
    build_note_annotations(g, [s_en, s_de], MAPPING)

    note_iri = EUCN[f"note_{NOTE_ID[:8]}"]

    assert (note_iri, SKOS.definition, Literal("Whisky is a spirit.", lang="en")) in g
    assert (note_iri, SKOS.definition, Literal("Whisky ist ein Spirituose.", lang="de")) in g

    # Only one ExplanatoryNote type assertion — no duplicate metadata
    type_triples = list(g.triples((note_iri, RDF.type, EUCN["ExplanatoryNote"])))
    assert len(type_triples) == 1

    note_id_triples = list(g.triples((note_iri, EUCN["noteId"], None)))
    assert len(note_id_triples) == 1


def test_unmapped_cn_code_note_emitted_no_class_triple():
    g = Graph()
    s = _section(NOTE_ID, "en", "Some product.", cn_code="999999")
    build_note_annotations(g, [s], MAPPING)

    note_iri = EUCN[f"note_{NOTE_ID[:8]}"]
    assert (note_iri, RDF.type, EUCN["ExplanatoryNote"]) in g
    assert (note_iri, EUCN["noteId"], Literal(NOTE_ID, datatype=XSD.string)) in g

    # No OWL class IRI should carry a skos:definition
    cls_iri = EUCN["SomeUnknownClass"]
    assert (cls_iri, SKOS.definition, None) not in g


def test_idempotent_double_call():
    g = Graph()
    s_en = _section(NOTE_ID, "en", "Whisky is a spirit.")
    s_de = _section(NOTE_ID, "de", "Whisky ist ein Spirituose.")
    sections = [s_en, s_de]

    build_note_annotations(g, sections, MAPPING)
    count_after_first = len(g)

    build_note_annotations(g, sections, MAPPING)
    assert len(g) == count_after_first


def test_has_explanatory_note_link():
    g = Graph()
    s = _section(NOTE_ID, "en", "Whisky is a spirit.")
    build_note_annotations(g, [s], MAPPING)

    note_iri = EUCN[f"note_{NOTE_ID[:8]}"]
    cls_iri = EUCN["WhiskySpirit"]
    assert (cls_iri, EUCN["hasExplanatoryNote"], note_iri) in g


def test_dcterms_modified_typed_as_xsd_date():
    g = Graph()
    s = _section(NOTE_ID, "en", "Whisky is a spirit.")
    build_note_annotations(g, [s], MAPPING)

    note_iri = EUCN[f"note_{NOTE_ID[:8]}"]
    modified_triples = list(g.triples((note_iri, DCTERMS.modified, None)))
    assert len(modified_triples) == 1
    _, _, obj = modified_triples[0]
    assert isinstance(obj, Literal)
    assert obj.datatype == XSD.date
