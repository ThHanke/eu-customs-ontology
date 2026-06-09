from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from src.agent import context_builder
from src.agent.llm_axiom_agent import LLMAxiomAgent
from src.agent.node_registry import NodeRegistry
from src.ontology.tbox import build_tbox
from src.schema.legal_text import LegalSection
from src.schema.node_axiom_set import NodeAxiomSet
from src.schema.wizard import WizardTree

logger = logging.getLogger(__name__)


def _log_axiom_set(cn_code: str, axiom_set: "NodeAxiomSet") -> None:
    lines = [
        f"[axioms] {cn_code}  status={axiom_set.status}  "
        f"score={axiom_set.coverage_score:.2f}  "
        f"classes={len(axiom_set.new_classes)}  "
        f"props={len(axiom_set.new_properties)}  "
        f"restrictions={len(axiom_set.restrictions)}"
    ]
    for cls in axiom_set.new_classes:
        lines.append(f"  class  {cls.iri_local_name}  rdfs:subClassOf {cls.bfo_parent_iri}")
    for prop in axiom_set.new_properties:
        lines.append(f"  prop   {prop.iri_local_name}  type={prop.property_type}  functional={prop.is_functional}")
    for r in axiom_set.restrictions:
        owl_local = r.owl_class_iri.rsplit("/", 1)[-1]
        prop_local = r.property_iri.rsplit("/", 1)[-1] if r.property_iri else ""
        lines.append(f"  axiom  {r.restriction_type:15s}  {owl_local:30s}  {prop_local}  {r.value or ''}")
    logger.info("\n".join(lines))


@dataclass
class ChapterRunResult:
    total: int = 0
    skipped: int = 0
    proposed: int = 0
    approved: int = 0
    failed: int = 0


class ChapterRunner:
    """Orchestrate the topological per-node loop for a chapter."""

    def __init__(self, chapter: int, model: str, data_root: Path) -> None:
        self.chapter = chapter
        self.model = model
        self.data_root = data_root

    def run(self, wizard_tree: WizardTree, force: bool = False) -> ChapterRunResult:
        result = ChapterRunResult()

        # 1. Assemble static context and tbox hash
        static_context = context_builder.build_static_context(self.chapter)
        tbox_hash = context_builder.compute_tbox_hash(self.chapter)

        # 2. Load node registry
        registry_dir = self.data_root / "axiom_candidates" / f"ch{self.chapter:02d}"
        node_registry = NodeRegistry(registry_dir)

        # 3. Collect all cn_codes from notes.jsonl, sorted topologically
        notes_path = self.data_root / "legal_text" / f"ch{self.chapter:02d}" / "notes.jsonl"
        sections: list[LegalSection] = []
        if notes_path.exists():
            for line in notes_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    sections.append(LegalSection.model_validate_json(line))

        # Gather unique cn_codes sorted topologically (by code length, then lex)
        all_cn_codes = sorted(
            {s.cn_code for s in sections},
            key=lambda c: (len(c), c),
        )

        # Reset running TBox at start of each chapter run
        running_tbox_path = self.data_root / "agent_tbox" / f"ch{self.chapter:02d}" / "running.ttl"
        if running_tbox_path.exists():
            running_tbox_path.unlink()

        if not all_cn_codes:
            return result

        result.total = len(all_cn_codes)

        # Resolve base_tbox_path
        base_tbox_path = self._resolve_base_tbox()

        # Build wizard_nodes lookup
        wizard_nodes_by_cn: dict[str, list] = {}
        for node in wizard_tree.nodes.values():
            if node.cn_code:
                wizard_nodes_by_cn.setdefault(node.cn_code, []).append(node)

        # Build LLM agent (shared across nodes in this chapter run)
        agent = LLMAxiomAgent(model=self.model, static_context=static_context)

        # Build section index: cn_code -> list[LegalSection] sorted by note_id
        sections_by_cn: dict[str, list[LegalSection]] = {}
        for sec in sections:
            sections_by_cn.setdefault(sec.cn_code, []).append(sec)
        for cn in sections_by_cn:
            sections_by_cn[cn].sort(key=lambda s: s.note_id)

        # 4. Process each cn_code in topological order
        for cn_code in all_cn_codes:
            cn_sections = sections_by_cn.get(cn_code, [])

            # Compute source_text_hash
            source_text_hash = self._compute_source_text_hash(cn_code, cn_sections)

            # Check staleness
            is_stale = force or node_registry.is_stale(cn_code, source_text_hash, tbox_hash)

            if not is_stale:
                logger.info("[agent] skip %s (cache hit)", cn_code)
                result.skipped += 1
                continue

            # Stale but approved — preserve; TBox additions don't invalidate approved axioms
            if not force:
                existing = node_registry.get_approved(cn_code)
                if existing is not None:
                    logger.info("[agent] skip %s (approved, tbox bump only)", cn_code)
                    result.approved += 1
                    self._append_to_running_tbox(existing, running_tbox_path)
                    continue

            logger.info("[agent] process %s", cn_code)

            # Build node context
            running_tbox_ttl = ""
            if running_tbox_path.exists():
                running_tbox_ttl = running_tbox_path.read_text(encoding="utf-8")

            node_context = context_builder.build_node_context(
                cn_code=cn_code,
                legal_sections=sections,
                wizard_nodes=wizard_nodes_by_cn,
                running_tbox_ttl=running_tbox_ttl,
            )

            # Call agent
            try:
                axiom_set = agent.run(
                    cn_code=cn_code,
                    node_context=node_context,
                    base_tbox_path=base_tbox_path,
                    running_tbox_path=running_tbox_path,
                    existing_axioms_ttl="",
                )
            except Exception as exc:
                logger.warning("[agent] error processing %s: %s", cn_code, exc)
                result.failed += 1
                continue

            # Upsert result into registry
            node_registry.upsert(axiom_set)
            _log_axiom_set(cn_code, axiom_set)

            if axiom_set.status in ("proposed", "approved"):
                if axiom_set.status == "proposed":
                    result.proposed += 1
                else:
                    result.approved += 1
                # Append new classes/properties to running TBox
                self._append_to_running_tbox(axiom_set, running_tbox_path)
            else:
                result.failed += 1

        return result

    def _compute_source_text_hash(
        self, cn_code: str, cn_sections: list[LegalSection]
    ) -> str:
        """Compute SHA256 of full note texts for a cn_code, sorted by note_id."""
        texts: list[str] = []
        full_dir = self.data_root / "legal_text" / f"ch{self.chapter:02d}" / "full"
        for section in sorted(cn_sections, key=lambda s: s.note_id):
            full_path = full_dir / f"{section.note_id}.txt"
            if full_path.exists():
                text = full_path.read_text(encoding="utf-8")
            else:
                text = section.source_text
            texts.append(text)
        combined = "\n".join(texts)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _resolve_base_tbox(self) -> Path:
        """Find or build the base TBox TTL for this chapter."""
        ontology_dir = self.data_root / "ontology"
        if ontology_dir.exists():
            flat_ttls = sorted(ontology_dir.glob(f"eucn-ch{self.chapter:02d}-*-flat.ttl"))
            if flat_ttls:
                return flat_ttls[-1]

        # Build from scratch
        g = Graph()
        build_tbox(g, chapter=self.chapter)
        base_tbox_dir = self.data_root / "agent_tbox" / f"ch{self.chapter:02d}"
        base_tbox_dir.mkdir(parents=True, exist_ok=True)
        base_tbox_path = base_tbox_dir / "base_tbox.ttl"
        g.serialize(destination=str(base_tbox_path), format="turtle")
        return base_tbox_path

    def _append_to_running_tbox(
        self, axiom_set: NodeAxiomSet, running_tbox_path: Path
    ) -> None:
        """Merge new classes and properties from axiom_set into running.ttl.

        Parses the existing file (if any) into a graph, adds the new triples,
        then reserializes to avoid duplicate @prefix declarations.
        """
        eucn_ns = "https://w3id.org/eucn/"
        g = Graph()
        if running_tbox_path.exists():
            g.parse(running_tbox_path, format="turtle")

        for cls in axiom_set.new_classes:
            iri = URIRef(f"{eucn_ns}{cls.iri_local_name}")
            g.add((iri, RDF.type, OWL.Class))
            g.add((iri, RDFS.label, Literal(cls.label_en, lang="en")))
            g.add((iri, RDFS.subClassOf, URIRef(cls.bfo_parent_iri)))

        for prop in axiom_set.new_properties:
            iri = URIRef(f"{eucn_ns}{prop.iri_local_name}")
            prop_type = (
                OWL.ObjectProperty if prop.property_type == "object" else OWL.DatatypeProperty
            )
            g.add((iri, RDF.type, prop_type))
            g.add((iri, RDFS.label, Literal(prop.label_en, lang="en")))
            if prop.is_functional:
                g.add((iri, RDF.type, OWL.FunctionalProperty))

        if len(g) == 0:
            return

        running_tbox_path.parent.mkdir(parents=True, exist_ok=True)
        g.serialize(destination=str(running_tbox_path), format="turtle")
