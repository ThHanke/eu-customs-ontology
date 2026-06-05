"""Integration tests for the pipeline orchestration script."""
import json
import pytest
from datetime import date
from pathlib import Path

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


class TestPipelineIntegration:
    def test_skip_fetch_missing_file_raises(self, tmp_path, monkeypatch):
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        with pytest.raises(FileNotFoundError, match="taric_ch22.json"):
            pipeline_mod.run(chapter=22, skip_fetch=True, skip_scrape=True)

    def test_skip_scrape_missing_file_raises(self, tmp_path, monkeypatch):
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        # Create taric JSON but not wizard JSONL
        cd = ChapterData(chapter=22, measures=[])
        (tmp_path / "taric_ch22.json").write_text(cd.model_dump_json())
        with pytest.raises(FileNotFoundError, match="wizard_ch22.jsonl"):
            pipeline_mod.run(chapter=22, skip_fetch=True, skip_scrape=True)

    def test_fixture_pipeline_produces_ttl(self, tmp_path, monkeypatch):
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        _write_fixture_json(tmp_path)
        pipeline_mod.run(
            chapter=22,
            skip_fetch=True,
            skip_scrape=True,
            no_reasoner=False,
        )
        ttl = tmp_path / "ch22.ttl"
        trig = tmp_path / "ch22.trig"
        assert ttl.exists(), "ch22.ttl not produced"
        assert trig.exists(), "ch22.trig not produced"
        content = ttl.read_text()
        assert "TARICMeasure" in content or "customs" in content

    def test_idempotent_output(self, tmp_path, monkeypatch):
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        _write_fixture_json(tmp_path)

        out1 = tmp_path / "run1"
        out1.mkdir()
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", out1)
        pipeline_mod.run(chapter=22, skip_fetch=True, skip_scrape=True, no_reasoner=True)
        nt1 = sorted((out1 / "ch22.ttl").read_text().splitlines())

        out2 = tmp_path / "run2"
        out2.mkdir()
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", out2)
        pipeline_mod.run(chapter=22, skip_fetch=True, skip_scrape=True, no_reasoner=True)
        nt2 = sorted((out2 / "ch22.ttl").read_text().splitlines())

        # longturtle has provenance-free output but run_id differs → compare structural triples
        # Test that same semantic content (TARIC measures, CN codes) is present
        assert nt1 == nt2, "Output not idempotent — sorted Turtle lines differ"
