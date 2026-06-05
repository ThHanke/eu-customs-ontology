"""Chapter 22 SPARQL acceptance tests.

EXPECTED_MFN_RATE_2204_21 must be confirmed from CIRCABC source data during
Unit 3 integration. Placeholder 13.4 matches typical MFN ad-valorem for CN 2204 21
as published in the TARIC database (to be validated against actual CIRCABC XML).
"""
import pytest
from datetime import date
from pathlib import Path
from rdflib import Graph
from rdflib.namespace import XSD

from src.ontology.abox import build_abox
from src.ontology.tbox import build_tbox
from src.ontology.namespaces import EUCN
from src.schema.taric import ChapterData, MeasureComponent, TARICMeasure
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.sparql.store import OntologyStore

# Confirmed from CIRCABC Duties Import 01-99.xlsx, June 2026 (UUID 0c2f56a5).
# CN 2204 21 MFN specific duty: still wine ≤2L containers = 13.100 EUR/HLT.
# Source: rows starting with '220421*10' in Duties Import 01-99.xlsx, meas. type 103,
# origin 1011, regulation 0948/09. Verified 2026-06-05.
EXPECTED_MFN_RATE_2204_21 = 13.1


def _build_ch22_store(tmp_path: Path) -> OntologyStore:
    """Build a minimal Chapter 22 ontology and load into SPARQL store."""
    measures = [
        TARICMeasure(
            sid="100001",
            commodity_code="2204219100",
            measure_type_id="103",
            geographical_area_id="1011",
            validity_start=date(2024, 1, 1),
            regulation_id="R2024/0001",
            components=[
                MeasureComponent(
                    duty_expression_id="01",
                    duty_amount=EXPECTED_MFN_RATE_2204_21,
                    monetary_unit=None,
                    measurement_unit=None,
                )
            ],
        ),
        TARICMeasure(
            sid="100002",
            commodity_code="2204219200",
            measure_type_id="103",
            geographical_area_id="1011",
            validity_start=date(2024, 1, 1),
            regulation_id="R2024/0001",
            components=[
                MeasureComponent(
                    duty_expression_id="01",
                    duty_amount=32.0,
                    monetary_unit="EUR",
                    measurement_unit="hl",
                )
            ],
        ),
    ]
    cd = ChapterData(chapter=22, measures=measures)

    root = ClassificationNode(
        node_id="root", question_text="Is it wine?", path_from_root=[],
        answer_options=[AnswerOption(answer_text="Yes", next_node_id="term")],
        is_terminal=False,
    )
    term = ClassificationNode(
        node_id="term", question_text="", path_from_root=["Yes"],
        answer_options=[], is_terminal=True, cn_code="2204219100",
    )
    wt = WizardTree(chapter=22, nodes={"root": root, "term": term}, root_node_id="root")

    g = Graph()
    build_tbox(g)
    build_abox(cd, wt, g)

    ttl_path = tmp_path / "ch22.ttl"
    ttl_path.write_text(g.serialize(format="turtle"))

    store = OntologyStore()
    store.load_turtle(ttl_path)
    return store


PREFIXES = """
PREFIX eucn: <https://w3id.org/eucn/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


class TestChapter22SPARQL:
    def test_measure_count(self, tmp_path):
        store = _build_ch22_store(tmp_path)
        rows = store.query(PREFIXES + """
            SELECT (COUNT(?m) AS ?count) WHERE {
                ?m a eucn:TARICMeasure .
            }
        """)
        assert float(str(rows[0]["count"])) >= 2

    def test_mfn_rate_2204_21(self, tmp_path):
        store = _build_ch22_store(tmp_path)
        rows = store.query(PREFIXES + """
            SELECT ?rate WHERE {
                ?measure a eucn:TARICMeasure ;
                         eucn:codeString ?code ;
                         eucn:measureTypeId "103" ;
                         eucn:geographicScope "1011" ;
                         eucn:dutyAmount ?rate .
                FILTER(STRSTARTS(STR(?code), "220421"))
                FILTER(?rate > 0)
            }
        """)
        assert rows, "No MFN rate found for CN 2204 21"
        rates = [float(str(r["rate"])) for r in rows]
        assert EXPECTED_MFN_RATE_2204_21 in rates, (
            f"Expected {EXPECTED_MFN_RATE_2204_21} in {rates}"
        )

    def test_ask_classification_node(self, tmp_path):
        store = _build_ch22_store(tmp_path)
        result = store.ask(PREFIXES + "ASK { ?x a eucn:ClassificationNode . }")
        assert result is True

    def test_empty_store_returns_empty(self):
        store = OntologyStore()
        rows = store.query(PREFIXES + "SELECT ?x WHERE { ?x a eucn:TARICMeasure . }")
        assert rows == []

    def test_malformed_sparql_raises(self, tmp_path):
        store = _build_ch22_store(tmp_path)
        with pytest.raises(Exception):
            store.query("NOT VALID SPARQL")

    def test_root_node_reachable_by_no_incoming_has_answer(self, tmp_path):
        store = _build_ch22_store(tmp_path)
        rows = store.query(PREFIXES + """
            SELECT ?node WHERE {
                ?node a eucn:ClassificationNode .
                FILTER NOT EXISTS { ?parent eucn:hasAnswer ?node . }
            }
        """)
        assert len(rows) >= 1
