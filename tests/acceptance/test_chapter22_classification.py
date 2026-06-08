"""Chapter 22 classification acceptance tests.

Tests product class structure, equivalence axioms, and disjointness via SPARQL.
Note: pyoxigraph is a SPARQL 1.1 engine without OWL reasoning — inferred triples
must be explicitly present (from the TBox or classify output) for queries to return them.
"""
import itertools
import json
import pytest
from datetime import date
from pathlib import Path
from rdflib import Graph

from src.ontology.abox import build_abox
from src.ontology.namespaces import EUCN
from src.ontology.tbox import build_tbox
from src.schema.taric import ChapterData
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.sparql.store import OntologyStore

PREFIXES = """
PREFIX eucn: <https://w3id.org/eucn/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX bfo: <http://purl.obolibrary.org/obo/>
"""

HEADING_CLASSES = [
    "https://w3id.org/eucn/Water",
    "https://w3id.org/eucn/NonAlcoholicBeverage",
    "https://w3id.org/eucn/Beer",
    "https://w3id.org/eucn/Wine",
    "https://w3id.org/eucn/FlavouredWine",
    "https://w3id.org/eucn/FermentedBeverage",
    "https://w3id.org/eucn/EthylAlcohol",
    "https://w3id.org/eucn/Spirit",
    "https://w3id.org/eucn/Vinegar",
]


def _empty_wizard() -> WizardTree:
    root = ClassificationNode(
        node_id="root",
        question_text="Ist das Erzeugnis ein Getränk (Kapitel 22)?",
        answer_options=[AnswerOption(answer_text="Ja", next_node_id=None)],
        is_terminal=False,
        path_from_root=[],
    )
    return WizardTree(chapter=22, nodes={"root": root}, root_node_id="root")


def _build_store(tmp_path: Path) -> OntologyStore:
    g = Graph()
    build_tbox(g)
    build_abox(ChapterData(chapter=22, measures=[]), _empty_wizard(), g)
    ttl = tmp_path / "ch22_class.ttl"
    ttl.write_text(g.serialize(format="turtle"))
    store = OntologyStore()
    store.load_turtle(ttl)
    return store


class TestProductClassStructure:
    def test_beer_is_owl_class(self, tmp_path):
        store = _build_store(tmp_path)
        assert store.ask(PREFIXES + "ASK { eucn:Beer a owl:Class . }")

    def test_product_class_count_at_least_12(self, tmp_path):
        store = _build_store(tmp_path)
        rows = store.query(PREFIXES + "SELECT (COUNT(?c) AS ?count) WHERE { ?c a owl:Class . }")
        assert rows
        assert int(float(str(rows[0]["count"]))) >= 12

    def test_still_wine_subclass_chain(self, tmp_path):
        store = _build_store(tmp_path)
        assert store.ask(PREFIXES + """
            ASK {
                eucn:StillWine rdfs:subClassOf eucn:Wine .
                eucn:Wine rdfs:subClassOf eucn:Beverage .
            }
        """)

    def test_beverage_subclass_of_bfo_object(self, tmp_path):
        store = _build_store(tmp_path)
        assert store.ask(PREFIXES + """
            ASK {
                eucn:Beverage rdfs:subClassOf
                    <http://purl.obolibrary.org/obo/BFO_0000030> .
            }
        """)


class TestDisjointness:
    def test_beer_disjoint_wine_present(self, tmp_path):
        store = _build_store(tmp_path)
        assert store.ask(PREFIXES + "ASK { eucn:Beer owl:disjointWith eucn:Wine . }")

    def test_no_individual_both_beer_and_wine(self, tmp_path):
        store = _build_store(tmp_path)
        rows = store.query(PREFIXES + """
            SELECT ?x WHERE {
                ?x a eucn:Beer .
                ?x a eucn:Wine .
            }
        """)
        assert rows == [], f"Unexpected Beer+Wine individuals: {rows}"

    def test_all_heading_pairs_disjoint(self, tmp_path):
        store = _build_store(tmp_path)
        for a, b in itertools.combinations(HEADING_CLASSES, 2):
            result = store.ask(f"""
                ASK {{ <{a}> <http://www.w3.org/2002/07/owl#disjointWith> <{b}> . }}
            """)
            assert result, f"Missing disjointWith: {a} ⊥ {b}"

    def test_no_all_disjoint_classes(self, tmp_path):
        store = _build_store(tmp_path)
        rows = store.query(PREFIXES + """
            SELECT ?x WHERE { ?x a owl:AllDisjointClasses . }
        """)
        assert rows == [], "owl:AllDisjointClasses must not appear"


class TestEquivalenceAxioms:
    def test_beer_has_equivalentclass(self, tmp_path):
        store = _build_store(tmp_path)
        rows = store.query(PREFIXES + """
            SELECT ?anon WHERE { eucn:Beer owl:equivalentClass ?anon . }
        """)
        assert rows, "eucn:Beer must have owl:equivalentClass"

    def test_all_product_classes_have_equiv(self, tmp_path):
        store = _build_store(tmp_path)
        for cls_iri in HEADING_CLASSES:
            result = store.ask(f"""
                ASK {{
                    <{cls_iri}>
                        <http://www.w3.org/2002/07/owl#equivalentClass> ?anon .
                }}
            """)
            assert result, f"{cls_iri} missing owl:equivalentClass"

    def test_discriminating_props_as_datatype_properties(self, tmp_path):
        store = _build_store(tmp_path)
        for prop_suffix in [
            "alcoholByVolumePercent", "isCarbonated", "isDenatured",
            "maxContainerVolumeL", "fermentationBase",
        ]:
            result = store.ask(f"""
                ASK {{
                    <https://w3id.org/eucn/{prop_suffix}>
                        a <http://www.w3.org/2002/07/owl#DatatypeProperty> .
                }}
            """)
            assert result, f"eucn:{prop_suffix} not found as DatatypeProperty"


class TestCoverageReport:
    def test_coverage_json_exists_after_pipeline(self, tmp_path, monkeypatch):
        """Pipeline writes wizard_axiom_coverage_ch22.json to intermediate dir."""
        import src.pipeline as pipeline_mod
        from src.schema.taric import MeasureComponent, TARICMeasure
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)

        measures = [
            TARICMeasure(
                sid="1", commodity_code="2204219100", measure_type_id="103",
                geographical_area_id="1011", validity_start=date(2024, 1, 1),
                regulation_id="R2024/001",
                components=[MeasureComponent(duty_expression_id="01", duty_amount=13.1)],
            )
        ]
        (tmp_path / "taric_ch22.json").write_text(
            ChapterData(chapter=22, measures=measures).model_dump_json(indent=2)
        )
        root = ClassificationNode(
            node_id="root", question_text="Is it a beverage?", path_from_root=[],
            answer_options=[AnswerOption(answer_text="Ja", next_node_id=None)],
            is_terminal=False,
        )
        import json as _json
        with open(tmp_path / "wizard_ch22.jsonl", "w") as fh:
            fh.write(_json.dumps(root.model_dump(), default=str) + "\n")

        pipeline_mod.run(
            chapter=22, skip_fetch=True, skip_scrape=True,
            no_reasoner=True, no_classify=True,
            extract_date=date(2026, 6, 8),
        )

        cov_path = tmp_path / "wizard_axiom_coverage_ch22.json"
        assert cov_path.exists(), "wizard_axiom_coverage_ch22.json not written"
        data = json.loads(cov_path.read_text())
        assert "total_terminal_nodes" in data
        assert data["total_terminal_nodes"] == 0
        assert data["coverage_pct"] == 100.0
