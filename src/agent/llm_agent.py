from __future__ import annotations

from src.schema.legal_text import LegalSection
from src.schema.axiom_candidate import AxiomCandidate

MAX_SECTIONS_DEFAULT = 20


class LLMAxiomAgent:
    def __init__(self, max_sections: int = MAX_SECTIONS_DEFAULT) -> None:
        self.max_sections = max_sections

    def extract_candidates(
        self,
        sections: list[LegalSection],
        owl_class: str,
        chapter: int,
        available_process_classes: list[str] | None = None,
    ) -> list[AxiomCandidate]:
        """LLM-based fallback extractor. Currently a stub — returns empty list.

        TODO: implement Claude API call when anthropic SDK is added.
        """
        if len(sections) > self.max_sections:
            raise RuntimeError(
                f"LLMAxiomAgent: {len(sections)} sections exceeds max_sections={self.max_sections}"
            )
        return []
