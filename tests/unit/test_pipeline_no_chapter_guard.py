"""Verify pipeline.py contains no chapter-specific if-guards."""
from pathlib import Path


def test_no_chapter_equality_guard():
    src = Path(__file__).parents[2] / "src" / "pipeline.py"
    text = src.read_text()
    assert "if chapter ==" not in text, (
        "pipeline.py must not contain 'if chapter ==' guards; "
        "chapter-specific logic belongs in chapter modules or the test suite"
    )
