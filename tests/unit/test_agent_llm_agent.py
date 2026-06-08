from __future__ import annotations

import pytest

from src.agent.llm_agent import LLMAxiomAgent, MAX_SECTIONS_DEFAULT
from src.schema.legal_text import LegalSection


class TestLLMAxiomAgent:
    def test_empty_sections_returns_empty_list(self) -> None:
        """Empty sections list should return [], no exception."""
        agent = LLMAxiomAgent()
        result = agent.extract_candidates(
            sections=[],
            owl_class="TestClass",
            chapter=1,
        )
        assert result == []

    def test_max_sections_exceeded_raises_runtime_error(self) -> None:
        """Sections exceeding max_sections should raise RuntimeError."""
        agent = LLMAxiomAgent(max_sections=2)
        sections = [
            LegalSection(
                note_id=f"note_{i}",
                chapter=1,
                cn_code="0101",
                note_type="general",
                source_text=f"Text {i}",
                source_text_hash="",
                ingestion_date="2026-01-01",
                language="EN",
                source_url="http://example.com",
                fetched_at="2026-01-01",
            )
            for i in range(3)
        ]
        with pytest.raises(RuntimeError, match="sections exceeds max_sections"):
            agent.extract_candidates(
                sections=sections,
                owl_class="TestClass",
                chapter=1,
            )

    def test_sections_within_limit_returns_empty_list(self) -> None:
        """Sections within limit should return [], no exception."""
        agent = LLMAxiomAgent(max_sections=5)
        sections = [
            LegalSection(
                note_id=f"note_{i}",
                chapter=1,
                cn_code="0101",
                note_type="general",
                source_text=f"Text {i}",
                source_text_hash="",
                ingestion_date="2026-01-01",
                language="EN",
                source_url="http://example.com",
                fetched_at="2026-01-01",
            )
            for i in range(3)
        ]
        result = agent.extract_candidates(
            sections=sections,
            owl_class="TestClass",
            chapter=1,
        )
        assert result == []

    def test_max_sections_configurable_via_constructor(self) -> None:
        """max_sections should be configurable via constructor."""
        agent_default = LLMAxiomAgent()
        assert agent_default.max_sections == MAX_SECTIONS_DEFAULT

        agent_custom = LLMAxiomAgent(max_sections=10)
        assert agent_custom.max_sections == 10
