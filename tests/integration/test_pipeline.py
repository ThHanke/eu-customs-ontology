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
        from datetime import date
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        _write_fixture_json(tmp_path)
        ed = date(2026, 6, 5)
        pipeline_mod.run(
            chapter=22,
            skip_fetch=True,
            skip_scrape=True,
            no_reasoner=False,
            no_classify=True,
            extract_date=ed,
        )
        ttl = tmp_path / "eucn-ch22-beverages-2026-06-05.ttl"
        trig = tmp_path / "eucn-ch22-beverages-2026-06-05.trig"
        assert ttl.exists(), "eucn-ch22-beverages-2026-06-05.ttl not produced"
        assert trig.exists(), "eucn-ch22-beverages-2026-06-05.trig not produced"
        content = ttl.read_text()
        assert "TARICMeasure" in content or "w3id.org/eucn" in content

    def test_classify_step_writes_inferred_graph(self, tmp_path, monkeypatch):
        """Step 4.5: classify runs and .trig is written (empty result is OK)."""
        from datetime import date
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        _write_fixture_json(tmp_path)
        ed = date(2026, 6, 5)
        pipeline_mod.run(
            chapter=22,
            skip_fetch=True,
            skip_scrape=True,
            no_reasoner=False,
            no_classify=False,
            extract_date=ed,
        )
        trig = tmp_path / "eucn-ch22-beverages-2026-06-05.trig"
        assert trig.exists(), ".trig must be written even when classify produces empty output"

    def test_no_classify_flag_skips_classify(self, tmp_path, monkeypatch):
        from datetime import date
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        _write_fixture_json(tmp_path)
        ed = date(2026, 6, 5)
        # Must not raise even with no_classify=True
        pipeline_mod.run(
            chapter=22, skip_fetch=True, skip_scrape=True,
            no_reasoner=True, no_classify=True, extract_date=ed,
        )
        trig = tmp_path / "eucn-ch22-beverages-2026-06-05.trig"
        assert trig.exists(), ".trig written from build step regardless of classify"

    def test_idempotent_output(self, tmp_path, monkeypatch):
        from datetime import date
        import src.pipeline as pipeline_mod
        monkeypatch.setattr(pipeline_mod, "DATA_INTERMEDIATE", tmp_path)
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", tmp_path)
        _write_fixture_json(tmp_path)
        ed = date(2026, 6, 5)

        out1 = tmp_path / "run1"
        out1.mkdir()
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", out1)
        pipeline_mod.run(chapter=22, skip_fetch=True, skip_scrape=True,
                         no_reasoner=True, no_classify=True, extract_date=ed)
        nt1 = sorted((out1 / "eucn-ch22-beverages-2026-06-05.ttl").read_text().splitlines())

        out2 = tmp_path / "run2"
        out2.mkdir()
        monkeypatch.setattr(pipeline_mod, "DATA_ONTOLOGY", out2)
        pipeline_mod.run(chapter=22, skip_fetch=True, skip_scrape=True,
                         no_reasoner=True, no_classify=True, extract_date=ed)
        nt2 = sorted((out2 / "eucn-ch22-beverages-2026-06-05.ttl").read_text().splitlines())

        assert nt1 == nt2, "Output not idempotent — sorted Turtle lines differ"
