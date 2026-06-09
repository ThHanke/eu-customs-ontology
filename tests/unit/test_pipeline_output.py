"""Unit tests verifying pipeline output file names and content (no network, no reasoner)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.schema.taric import ChapterData, MeasureComponent, TARICMeasure
from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree


def _write_fixture_json(tmp_path: Path) -> tuple[Path, Path]:
    """Write minimal Chapter 22 fixture files to tmp_path."""
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
                    duty_amount=13.1,
                    monetary_unit=None,
                    measurement_unit=None,
                )
            ],
        )
    ]
    cd = ChapterData(chapter=22, measures=measures)
    taric_path = tmp_path / "taric_ch22.json"
    taric_path.write_text(cd.model_dump_json(indent=2))

    root = ClassificationNode(
        node_id="root", question_text="Is it wine?", path_from_root=[],
        answer_options=[AnswerOption(answer_text="Yes", next_node_id="term")],
        is_terminal=False,
    )
    term = ClassificationNode(
        node_id="term", question_text="", path_from_root=["Yes"],
        answer_options=[], is_terminal=True, cn_code="2204219100",
    )
    wizard_path = tmp_path / "wizard_ch22.jsonl"
    with open(wizard_path, "w") as fh:
        fh.write(json.dumps(root.model_dump(), default=str) + "\n")
        fh.write(json.dumps(term.model_dump(), default=str) + "\n")

    return taric_path, wizard_path


@pytest.fixture()
def pipeline_output(tmp_path, monkeypatch):
    """Run the pipeline with fixtures and return the output directory."""
    import src.pipeline as pipeline_mod
    monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
    monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
    _write_fixture_json(tmp_path)
    ed = date(2026, 6, 5)
    pipeline_mod.run(
        chapter=22,
        skip_fetch=True,
        skip_scrape=True,
        skip_legal_text=True,
        skip_commodity_details=True,
        no_reasoner=True,
        no_classify=True,
        extract_date=ed,
    )
    return tmp_path


class TestPipelineOutputFiles:
    def test_chapter_ttl_produced(self, pipeline_output):
        """eucn-ch22-beverages-{date}.ttl is produced."""
        assert (pipeline_output / "eucn-ch22-beverages-2026-06-05.ttl").exists()

    def test_chapter_latest_alias_produced(self, pipeline_output):
        """eucn-ch22-beverages-latest.ttl stable alias is produced."""
        assert (pipeline_output / "eucn-ch22-beverages-latest.ttl").exists()

    def test_core_ttl_produced(self, pipeline_output):
        """eucn-core-{date}.ttl is produced."""
        assert (pipeline_output / "eucn-core-2026-06-05.ttl").exists()

    def test_core_latest_alias_produced(self, pipeline_output):
        """eucn-core-latest.ttl stable alias is produced."""
        assert (pipeline_output / "eucn-core-latest.ttl").exists()

    def test_flat_ttl_produced(self, pipeline_output):
        """eucn-ch22-beverages-{date}-flat.ttl (Konclude input) is produced."""
        assert (pipeline_output / "eucn-ch22-beverages-2026-06-05-flat.ttl").exists()

    def test_chapter_ttl_contains_owl_imports(self, pipeline_output):
        """The chapter TTL contains an owl:imports triple."""
        from rdflib import Graph
        from rdflib.namespace import OWL
        g = Graph()
        g.parse(str(pipeline_output / "eucn-ch22-beverages-2026-06-05.ttl"), format="turtle")
        imports = list(g.triples((None, OWL.imports, None)))
        assert len(imports) > 0, "Chapter TTL must contain at least one owl:imports triple"

    def test_flat_ttl_has_no_owl_imports(self, pipeline_output):
        """The flat TTL must NOT contain any owl:imports triples."""
        content = (pipeline_output / "eucn-ch22-beverages-2026-06-05-flat.ttl").read_text()
        assert "owl:imports" not in content, "Flat TTL must not contain owl:imports"
        assert "imports" not in content.lower() or "owl:imports" not in content, \
            "Flat TTL must not contain owl:imports"

    def test_core_ttl_contains_produced_by(self, pipeline_output):
        """The core TTL contains eucn:producedBy."""
        content = (pipeline_output / "eucn-core-2026-06-05.ttl").read_text()
        assert "producedBy" in content, "Core TTL must contain eucn:producedBy"

    def test_chapter_ttl_contains_chapter_specific_content(self, pipeline_output):
        """The chapter TTL contains chapter-specific content (eucn:Beer)."""
        content = (pipeline_output / "eucn-ch22-beverages-2026-06-05.ttl").read_text()
        assert "Beer" in content, "Chapter TTL must contain chapter-specific content (e.g. eucn:Beer)"
