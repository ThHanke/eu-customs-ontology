from __future__ import annotations

import datetime
import logging
import tempfile
from pathlib import Path

import anthropic
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from src.reasoning.konclude import KoncludeConsistencyError, check_consistency
from src.schema.node_axiom_set import (
    PROPOSE_AXIOMS_TOOL_SCHEMA,
    NewClass,
    NewProperty,
    NodeAxiomSet,
    NodeRestriction,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "axiom_agent_system.txt"
_MAX_ATTEMPTS = 3


def _load_system_prompt(static_context: str) -> str:
    template = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{static_context}", static_context)


def _build_axiom_graph(axiom_set: NodeAxiomSet) -> Graph:
    """Convert a NodeAxiomSet into an rdflib Graph of OWL triples."""
    g = Graph()
    eucn_ns = "https://w3id.org/eucn/"
    def _iri(s: str) -> URIRef:
        # If already a full IRI, return as-is; otherwise treat as local name under EUCN
        if s.startswith("http://") or s.startswith("https://"):
            return URIRef(s)
        return URIRef(f"{eucn_ns}{s}")

    # Declare new classes
    for nc in axiom_set.new_classes:
        cls_iri = _iri(nc.iri_local_name)
        parent_iri = URIRef(nc.bfo_parent_iri)
        g.add((cls_iri, RDF.type, OWL.Class))
        g.add((cls_iri, RDFS.subClassOf, parent_iri))
        g.add((cls_iri, RDFS.label, Literal(nc.label_en, lang="en")))
        g.add((cls_iri, RDFS.label, Literal(nc.label_de, lang="de")))
        g.add((cls_iri, URIRef("http://purl.obolibrary.org/obo/IAO_0000115"),
               Literal(nc.definition_en, lang="en")))

    # Declare new properties
    for np_ in axiom_set.new_properties:
        prop_iri = _iri(np_.iri_local_name)
        if np_.property_type == "object":
            g.add((prop_iri, RDF.type, OWL.ObjectProperty))
            if np_.is_functional:
                g.add((prop_iri, RDF.type, OWL.FunctionalProperty))
        else:
            g.add((prop_iri, RDF.type, OWL.DatatypeProperty))
            if np_.is_functional:
                g.add((prop_iri, RDF.type, OWL.FunctionalProperty))
        g.add((prop_iri, RDFS.label, Literal(np_.label_en, lang="en")))
        if np_.domain_iri:
            g.add((prop_iri, RDFS.domain, _iri(np_.domain_iri)))
        if np_.range_iri:
            g.add((prop_iri, RDFS.range, _iri(np_.range_iri)))

    # Declare restrictions
    for i, restr in enumerate(axiom_set.restrictions):
        cls_iri = _iri(restr.owl_class_iri)
        prop_iri = _iri(restr.property_iri)
        key = f"{axiom_set.cn_code}:{i}"

        if restr.restriction_type == "someValuesFrom":
            r = BNode(f"r_sv_{key}")
            g.add((r, RDF.type, OWL.Restriction))
            g.add((r, OWL.onProperty, prop_iri))
            g.add((r, OWL.someValuesFrom, _iri(restr.value)))
            g.add((cls_iri, RDFS.subClassOf, r))

        elif restr.restriction_type == "hasValue":
            r = BNode(f"r_hv_{key}")
            g.add((r, RDF.type, OWL.Restriction))
            g.add((r, OWL.onProperty, prop_iri))
            val_str = restr.value
            if ":" in val_str:
                # IRI-shaped value (e.g. named singleton individual like eucn:GrapeFermentation_individual)
                filler = URIRef(val_str)
            elif val_str.lower() in ("true", "false"):
                filler = Literal(val_str.lower() == "true", datatype=XSD.boolean)
            else:
                filler = Literal(val_str, datatype=XSD.string)
            g.add((r, OWL.hasValue, filler))
            g.add((cls_iri, RDFS.subClassOf, r))

        elif restr.restriction_type == "decimalRange":
            facet_iri = URIRef(restr.facet) if restr.facet else XSD.maxInclusive
            facet_b = BNode(f"facet_{key}")
            g.add((facet_b, facet_iri, Literal(str(float(restr.value)), datatype=XSD.decimal)))
            dtype = BNode(f"dtype_{key}")
            g.add((dtype, RDF.type, RDFS.Datatype))
            g.add((dtype, OWL.onDatatype, XSD.decimal))
            fl = BNode(f"fl_{key}")
            g.add((fl, RDF.first, facet_b))
            g.add((fl, RDF.rest, RDF.nil))
            g.add((dtype, OWL.withRestrictions, fl))
            r = BNode(f"r_dr_{key}")
            g.add((r, RDF.type, OWL.Restriction))
            g.add((r, OWL.onProperty, prop_iri))
            g.add((r, OWL.someValuesFrom, dtype))
            g.add((cls_iri, RDFS.subClassOf, r))

        elif restr.restriction_type == "complement":
            inner = BNode(f"r_sv_inner_{key}")
            g.add((inner, RDF.type, OWL.Restriction))
            g.add((inner, OWL.onProperty, prop_iri))
            g.add((inner, OWL.someValuesFrom, _iri(restr.value)))
            compl = BNode(f"r_compl_{key}")
            g.add((compl, RDF.type, OWL.Class))
            g.add((compl, OWL.complementOf, inner))
            g.add((cls_iri, RDFS.subClassOf, compl))

    return g


def _build_scratch_ttl(
    base_tbox_path: Path,
    running_tbox_path: Path,
    existing_axioms_ttl: str,
    axiom_set: NodeAxiomSet,
) -> Path:
    """Merge base TBox + running TBox + existing axioms + new axioms into a temp file."""
    g = Graph()
    g.parse(str(base_tbox_path), format="turtle")
    if running_tbox_path.exists():
        g.parse(str(running_tbox_path), format="turtle")
    if existing_axioms_ttl and existing_axioms_ttl.strip():
        g.parse(data=existing_axioms_ttl, format="turtle")
    axiom_g = _build_axiom_graph(axiom_set)
    for triple in axiom_g:
        g.add(triple)
    with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False, mode="w") as f:
        scratch_path = Path(f.name)
    try:
        g.serialize(destination=str(scratch_path), format="turtle")
    except Exception:
        scratch_path.unlink(missing_ok=True)
        raise
    return scratch_path


def _parse_tool_use(response_content: list) -> tuple:
    """Extract (tool_use_block, tool_input_dict) from API response content."""
    for block in response_content:
        if getattr(block, "type", None) == "tool_use":
            return block, block.input
    raise ValueError("No tool_use block found in API response")


def _extract_stderr_feedback(exc: KoncludeConsistencyError) -> str:
    raw = str(exc)
    lines = raw.splitlines()
    filtered = [l for l in lines if "[INFO]" not in l]
    return "\n".join(filtered)[:2000]


def _build_node_context_message(cn_code: str, node_context: dict) -> str:
    parts: list[str] = [f"CN code: {cn_code}"]

    hierarchy = node_context.get("hierarchy_path", [])
    if hierarchy:
        path_strs = []
        for entry in hierarchy:
            code = entry.get("cn_code", "")
            questions = entry.get("question_texts", [])
            q_str = "; ".join(questions) if questions else "(no questions)"
            path_strs.append(f"  {code}: {q_str}")
        parts.append("Hierarchy path:\n" + "\n".join(path_strs))

    notes_en = node_context.get("notes_en", [])
    if notes_en:
        parts.append("Legal notes (EN):\n" + "\n---\n".join(notes_en))

    notes_de = node_context.get("notes_de", [])
    if notes_de:
        parts.append("Legal notes (DE):\n" + "\n---\n".join(notes_de))

    running_tbox = node_context.get("running_tbox", "")
    if running_tbox and running_tbox.strip():
        parts.append(f"Running TBox (current axioms for this session):\n```turtle\n{running_tbox}\n```")

    existing_axioms = node_context.get("existing_axioms", [])
    if existing_axioms:
        parts.append("Existing axioms for this node:\n" + "\n".join(existing_axioms))

    return "\n\n".join(parts)


class LLMAxiomAgent:
    """Core LLM-driven axiom agent.

    Builds a prompt, calls Claude with the `propose_axioms` tool, validates
    output via Konclude, and runs a feedback loop for up to _MAX_ATTEMPTS
    iterations.
    """

    def __init__(self, model: str, static_context: str) -> None:
        self.model = model
        self.static_context = static_context
        self._client = anthropic.Anthropic()
        self._system_prompt = _load_system_prompt(static_context)
        # Cache the system prompt — identical for every node in the chapter
        self._system_blocks = [
            {"type": "text", "text": self._system_prompt, "cache_control": {"type": "ephemeral"}}
        ]

    def run(
        self,
        cn_code: str,
        node_context: dict,
        base_tbox_path: Path,
        running_tbox_path: Path,
        existing_axioms_ttl: str = "",
    ) -> NodeAxiomSet:
        """Run the axiom proposal loop.

        Returns a NodeAxiomSet with status="proposed" on success, or
        status="failed" after _MAX_ATTEMPTS inconsistent attempts.
        """
        # Edge case: no legal text
        notes_en = node_context.get("notes_en", [])
        notes_de = node_context.get("notes_de", [])
        if not notes_en and not notes_de:
            return NodeAxiomSet(
                cn_code=cn_code,
                new_classes=[],
                new_properties=[],
                restrictions=[],
                coverage_score=0.0,
                coverage_explanation="No legal text available",
                source_note_ids=[],
                source_text_hash="0" * 64,
                tbox_hash="0" * 64,
                status="approved",
                agent_model=self.model,
                generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
            )

        user_message = _build_node_context_message(cn_code, node_context)
        messages: list[dict] = [{"role": "user", "content": user_message}]

        for attempt in range(_MAX_ATTEMPTS):
            logger.debug("LLMAxiomAgent: attempt %d/%d for CN %s", attempt + 1, _MAX_ATTEMPTS, cn_code)

            response = self._client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=self._system_blocks,
                tools=[PROPOSE_AXIOMS_TOOL_SCHEMA],
                tool_choice={"type": "any"},
                messages=messages,
            )
            usage = response.usage
            logger.debug(
                "CN %s attempt %d — in=%d out=%d cache_read=%d cache_write=%d",
                cn_code, attempt + 1,
                usage.input_tokens, usage.output_tokens,
                getattr(usage, "cache_read_input_tokens", 0),
                getattr(usage, "cache_creation_input_tokens", 0),
            )

            try:
                tool_block, tool_input = _parse_tool_use(response.content)

                # Build NodeAxiomSet from tool output
                axiom_set = NodeAxiomSet(
                    cn_code=tool_input["cn_code"],
                    new_classes=[NewClass(**c) for c in tool_input.get("new_classes", [])],
                    new_properties=[NewProperty(**p) for p in tool_input.get("new_properties", [])],
                    restrictions=[NodeRestriction(**r) for r in tool_input.get("restrictions", [])],
                    coverage_score=tool_input["coverage_score"],
                    coverage_explanation=tool_input["coverage_explanation"],
                    source_note_ids=tool_input.get("source_note_ids", []),
                    source_text_hash=tool_input.get("source_text_hash", "0" * 64),
                    tbox_hash=tool_input.get("tbox_hash", "0" * 64),
                    status="proposed",
                    agent_model=self.model,
                    generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
                )
            except (ValueError, Exception) as exc:
                logger.warning(
                    "LLMAxiomAgent: invalid response on attempt %d for CN %s: %s",
                    attempt + 1, cn_code, exc,
                )
                if attempt < _MAX_ATTEMPTS - 1:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Your previous response was invalid: {exc}. "
                            "Please provide a valid propose_axioms tool call."
                        ),
                    })
                    continue
                break

            # Check consistency via Konclude
            scratch_path: Path | None = None
            try:
                scratch_path = _build_scratch_ttl(
                    base_tbox_path, running_tbox_path, existing_axioms_ttl, axiom_set
                )
                check_consistency(scratch_path)
                # Consistent — auto-approve and return
                axiom_set.status = "approved"
                logger.info(
                    "LLMAxiomAgent: axioms consistent (attempt %d) — approved CN %s",
                    attempt + 1, cn_code,
                )
                return axiom_set

            except KoncludeConsistencyError as exc:
                feedback = _extract_stderr_feedback(exc)
                logger.warning(
                    "LLMAxiomAgent: inconsistency on attempt %d for CN %s: %s",
                    attempt + 1, cn_code, feedback[:200],
                )

                if attempt < _MAX_ATTEMPTS - 1:
                    # Append assistant response and tool result to continue the conversation
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": (
                                f"The axioms you proposed caused an ontology inconsistency. "
                                f"Please revise them.\n\nKonclude error:\n{feedback}"
                            ),
                            "is_error": True,
                        }],
                    })

            except Exception as exc:
                # Konclude unavailable or crashed — leave as proposed for manual review
                logger.warning(
                    "LLMAxiomAgent: Konclude check failed for CN %s: %s — leaving as proposed",
                    cn_code, exc,
                )
                return axiom_set

            finally:
                if scratch_path is not None and scratch_path.exists():
                    try:
                        scratch_path.unlink()
                    except OSError:
                        pass

        # All attempts exhausted
        logger.error("LLMAxiomAgent: all %d attempts failed for CN %s", _MAX_ATTEMPTS, cn_code)
        return NodeAxiomSet(
            cn_code=cn_code,
            new_classes=[],
            new_properties=[],
            restrictions=[],
            coverage_score=0,
            coverage_explanation=f"All {_MAX_ATTEMPTS} attempts produced inconsistent axioms.",
            source_note_ids=[],
            source_text_hash="0" * 64,
            tbox_hash="0" * 64,
            status="failed",
            agent_model=self.model,
            generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )
