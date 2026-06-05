"""Integration test: build ABox from fixture JSON, serialize and parse back."""
import json
from datetime import date
from pathlib import Path
from rdflib import Graph
from rdflib.namespace import RDF

from src.schema.taric import ChapterData, MeasureComponent, TARICMeasure
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.ontology.abox import build_abox
from src.ontology.tbox import build_tbox
from src.ontology.namespaces import CUSTOMS


def _make_fixture():
    measures = [
        TARICMeasure(
            sid=str(i),
            commodity_code=f"2204{i:06d}",
            measure_type_id="103",
            geographical_area_id="1011",
            validity_start=date(2024, 1, 1),
            regulation_id=f"R2024/{i:04d}",
            components=[
                MeasureComponent(duty_expression_id="01", duty_amount=float(i), monetary_unit=None)
            ],
        )
        for i in range(1, 6)
    ]
    cd = ChapterData(chapter=22, measures=measures)

    root = ClassificationNode(
        node_id="root", question_text="Is it still wine?", path_from_root=[],
        answer_options=[AnswerOption(answer_text="Yes", next_node_id="term")],
        is_terminal=False,
    )
    term = ClassificationNode(
        node_id="term", question_text="", path_from_root=["Yes"],
        answer_options=[], is_terminal=True, cn_code="22040001",
    )
    wt = WizardTree(chapter=22, nodes={"root": root, "term": term}, root_node_id="root")
    return cd, wt


class TestABoxIntegration:
    def test_round_trip_size(self):
        cd, wt = _make_fixture()
        g = Graph()
        build_tbox(g)
        build_abox(cd, wt, g)
        ttl = g.serialize(format="turtle")
        g2 = Graph()
        g2.parse(data=ttl, format="turtle")
        assert len(g2) >= 100, f"Expected ≥100 triples, got {len(g2)}"

    def test_measure_individuals_present(self):
        cd, wt = _make_fixture()
        g = build_abox(cd, wt, Graph())
        measures = list(g.subjects(RDF.type, CUSTOMS.TARICMeasure))
        assert len(measures) >= 1

    def test_serialization_roundtrip(self, tmp_path):
        cd, wt = _make_fixture()
        g = build_abox(cd, wt, Graph())
        out = tmp_path / "test.ttl"
        out.write_text(g.serialize(format="longturtle"))
        g2 = Graph()
        g2.parse(str(out), format="turtle")
        assert len(g2) == len(g)
