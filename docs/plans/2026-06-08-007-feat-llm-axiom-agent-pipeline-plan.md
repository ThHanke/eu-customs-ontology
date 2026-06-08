---
title: "feat: LLM-driven per-node axiom generation with BFO compliance and Konclude feedback"
type: feat
status: active
date: 2026-06-08
---

# feat: LLM-driven per-node axiom generation with BFO compliance and Konclude feedback

## Overview

Replace the chapter-specific hand-coded equivalence axioms and rule-based regex extractor with an
LLM agent that processes each CN classification node individually, derives BFO-compliant OWL
axioms from legal text and wizard-tree hierarchy, validates them against Konclude, and iterates
on failures. A per-chapter harmonization pass deduplicates concepts coined by sibling nodes. The
agent self-reports coverage metrics so gaps are visible.

This supersedes `src/agent/rule_extractor.py`, `src/ontology/equivalence_axioms_beverages.py`,
`src/ontology/equivalence_axioms_ch23_feed.py`, `src/ontology/process_classes_beverages.py`,
`src/ontology/process_classes_ch23_feed.py`, `src/ontology/product_classes_beverages.py`,
and `src/ontology/product_classes_ch23_feed.py`. Those files become legacy fallback until the
new pipeline has been validated.

## Problem Frame

The current design has four interconnected flaws:

1. **Hand-coded axioms are assertions, not derivations.** `Wine subClassOf someValuesFrom
   producedBy GrapeFermentation` is our guess. The legal text may contradict it, refine it, or
   omit it entirely.

2. **The rule extractor is chapter-specific.** Its regex patterns are tuned for beverages; Chapter
   23 returned zero candidates. A new chapter requires a developer to extend the extractor.

3. **Class names are invented, not derived.** `eucn:GrapeFermentation`, `eucn:Wine` etc. were
   coined by the developer without grounding in the legal text's vocabulary.

4. **No coverage metric.** There is no way to know what fraction of the legal text is captured
   by the current axiom set.

## Requirements Trace

- R1. Every CN classification node that has an associated CLASS API legal text note gets
  processed by the LLM agent.
- R2. The agent derives OWL classes and properties BFO-compliant (subClassOf BFO_0000030 for
  material entities, BFO_0000015 for processes) or reuses existing ones.
- R3. New classes and properties coined in one node's axioms are visible as context to all
  subsequent nodes processed in the same chapter run.
- R4. Axioms are validated against Konclude before being stored; inconsistency triggers a
  feedback loop (max 3 iterations per node).
- R5. If the source text hash for a node is unchanged from a prior run, the node is skipped.
- R6. A per-chapter harmonization pass detects and merges duplicate concepts coined by sibling
  nodes before the chapter's final Konclude check.
- R7. The agent self-reports a coverage score (0–1) per node indicating how completely the legal
  text was axiomatised, plus a plain-text explanation of what was and was not captured.
- R8. All axioms are traceable to their source note (note_id, source_text_hash, ingestion_date).
- R9. Hand-authored equivalence axiom modules remain as an explicit legacy fallback for chapters
  that have no agent-produced registry, and are retired chapter-by-chapter as the agent output
  is validated.
- R10. The pipeline continues to produce a consistent, Konclude-passing ontology after every run.

## Scope Boundaries

- Agent does not process ABox data (TARIC measures, wizard node instances).
- No web search or external retrieval beyond what is already in `data/legal_text/`.
- No fine-tuning or model training; inference only via Anthropic API.
- No multi-language axiom generation in this iteration: EN notes are primary; DE notes are
  provided as supporting context only.
- The wizard-axiom transform (`src/ontology/wizard_axioms.py`) is not changed; it continues
  producing path-based equivalence axioms for individual commodity codes.

### Deferred to Separate Tasks

- Replacing the wizard-axiom transform with agent-derived hierarchy axioms.
- Automated approval workflow for proposed candidates.
- UI for reviewing and approving agent-proposed axioms.

## Context & Research

### Relevant Code and Patterns

- `src/ontology/bfo_stubs.py` — current BFO stub declarations (BFO_0000030, BFO_0000015,
  RO_0002234); this is the static context seed.
- `src/ontology/core.py` — builds the chapter-agnostic TBox; serialized as Turtle for agent
  context.
- `src/ontology/tbox.py` — full TBox including chapter-specific props; serialized for context.
- `src/agent/candidate_registry.py` — JSONL registry with `load/upsert/get_active/save`;
  the node registry extends this pattern.
- `src/schema/axiom_candidate.py` — existing candidate schema to be replaced/extended.
- `src/schema/legal_text.py` — `LegalSection` with `source_text_hash`; hash reuse for
  staleness detection.
- `src/reasoning/konclude.py` — `check_consistency(ttl_path)`, `classify(ttl_path)`;
  used for per-node validation.
- `src/ontology/owl_helpers.py` — `_equiv`, `_some_values_class_restr`, `_has_value_restr`,
  `_decimal_range_restr`; used to build RDF from structured output.
- `data/legal_text/ch22/notes.jsonl` — 126 notes, 79 unique CN codes, depth 2/4/6/8.
- `data/axiom_candidates/ch22.jsonl` — current flat JSONL registry (to be migrated to
  per-node structure).

### Institutional Learnings

- `project_owl_classification_pattern.md` — world-closure via FunctionalProperty + named
  singletons; must be preserved in agent output.
- `project_konclude_wasm_abox_realization.md` — Konclude ABox realization deferred; TBox
  consistency check and TBox classification are the available validation modes.
- Double-prefix IRI bug (past session): `value` field in candidates must be local name only
  (e.g. `GrapeFermentation` not `eucn:GrapeFermentation`).

### External References

- BFO 2020 OWL: `http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl` — the agent needs
  the label/definition spine of the relevant classes.
- Anthropic Python SDK: `anthropic>=0.40` already in `pyproject.toml`; use
  `client.messages.create` with `model="claude-opus-4-8"`.
- OWL 2 DL Turtle serialization conventions: blank-node restrictions via
  `owl:intersectionOf`, `owl:Restriction`, `owl:onProperty`, `owl:someValuesFrom`.

## Key Technical Decisions

- **Topological processing order**: nodes are processed depth-first by CN code length
  (2-digit chapter → 4-digit heading → 6-digit subheading → 8-digit commodity). Children see
  all concepts coined by ancestors and same-depth siblings processed earlier.

- **Running TBox accumulation**: after each node's axioms pass consistency, any new
  OWL classes or properties declared in them are serialized and appended to a
  `data/agent_tbox/{chapter}/running_tbox.ttl` scratch file. The next node's context includes
  this file. This file is ephemeral per chapter run; the approved axioms are the canonical
  artefact.

- **Node-level registry**: each CN code gets its own registry entry in
  `data/axiom_candidates/{chapter}/node_{cn_code}.jsonl`. This replaces the flat
  `ch{chapter}.jsonl`. The flat file is kept as a compatibility alias generated at the end of
  each chapter run.

- **Static context assembly**: the system prompt embeds a curated BFO excerpt (labels,
  definitions, and hierarchy for BFO_0000001–BFO_0000040 relevant to material entities and
  processes) plus the chapter's full TBox serialized in compact Turtle. This is ~300 triples /
  ~3k tokens. It never changes within a chapter run; it is assembled once and reused for
  every node agent call.

- **Structured output via tool use**: the agent is given a single tool `propose_axioms` whose
  JSON schema enforces the shape of the response: new classes, new properties, restrictions,
  and the coverage report. No free-text parsing needed.

- **Consistency validation approach**: for each node, build a scratch graph =
  `base_tbox + running_tbox + node_axioms`. Remove any triples previously stored for
  this node (staleness case). Serialize to a temp TTL and call `check_consistency`. On
  failure, pass the Konclude stderr (truncated to 2k chars) back to the agent as a tool
  result and request a revision.

- **Coverage metric**: the agent reports `coverage_score` (float 0–1) and
  `coverage_explanation` (string) as part of the `propose_axioms` tool call response.
  These are stored in the node registry entry and aggregated into a per-chapter report.

- **Harmonization pass**: after all nodes in a chapter are processed, a second LLM call
  receives the full set of new class/property IRIs coined during the chapter run and is asked
  to identify semantic duplicates and propose merge corrections. Corrections are applied as
  owl:equivalentClass or owl:equivalentProperty links (not renames, to preserve IRI stability)
  and Konclude-checked.

- **Legacy fallback**: `abox.py` dispatch continues to fall back to `add_equivalence_axioms`
  when no approved candidates exist for a chapter. This is removed chapter-by-chapter as
  validation completes.

- **TBox version hash**: each node registry entry records `tbox_hash` (SHA256 of the core +
  chapter TBox Turtle at time of generation). If the TBox changes, the staleness check must
  also consider whether `tbox_hash` differs from the current TBox hash, and if so flag the
  node for re-processing.

## Open Questions

### Resolved During Planning

- **Which model?** `claude-opus-4-8` — the prompt is rich (full TBox in context) and the
  output structure is complex (BFO hierarchy, OWL axiom shapes). Cheaper models may produce
  malformed Turtle or miss BFO alignment. Cost per node is acceptable given the hash-based
  cache prevents re-running unchanged nodes.

- **How to pass the full note text to the agent?** The `noteDescrSnippet` from the CLASS API
  is truncated. The full text is available via `fetch_note_pdf`. The agent must receive the
  full text; fetching the PDF for each node is a required upstream step.

- **What does the Konclude error look like?** `stderr` is a mix of OWLAPI parse errors and
  OWL-DL violation messages. The most informative fragment is the first 2000 chars of stderr
  after stripping `[INFO]` log lines. This is the format to pass as feedback.

### Deferred to Implementation

- Exact JSON schema for the `propose_axioms` tool — finalise during IU2 once the output
  shape is confirmed against a few manual test cases.
- Whether `noteDescrSnippet` is sufficient for most nodes (PDF fetch may be avoidable for
  short notes) — test during IU4 implementation.
- Maximum useful running TBox size before it starts hurting model reasoning — monitor during
  integration testing; 500-triple limit is a reasonable starting guard.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not
> implementation specification. The implementing agent should treat it as context, not code
> to reproduce.*

```
Chapter run flow
─────────────────────────────────────────────────────────────────────────────
1. ASSEMBLE STATIC CONTEXT
   bfo_excerpt.ttl + current TBox (core + chapter props) → system_prompt_context

2. FETCH FULL NOTE TEXTS (incremental — skip if hash unchanged)
   CLASS API /getNotesById per note_id → data/legal_text/ch{N}/full/

3. FOR EACH CN CODE (topological: len=2 → len=4 → len=6 → len=8):
   a. Compute source_hash = SHA256(all full notes for this cn_code, sorted)
   b. If node_registry[cn_code].source_hash == source_hash
      AND node_registry[cn_code].tbox_hash == current_tbox_hash
      → SKIP (cache hit)
   c. Build node_context:
      - hierarchy_path: ancestor cn_codes + their question_text from wizard tree
      - notes_en: full EN legal text for this cn_code
      - notes_de: full DE legal text (supporting context)
      - running_tbox: accumulated new classes/props from this chapter run so far
      - existing_axioms: any currently stored axioms for this cn_code (for stale re-run)
   d. AGENT CALL → propose_axioms tool
      - response: {new_classes, new_properties, restrictions, coverage_score,
                   coverage_explanation}
   e. BUILD scratch graph = base_tbox + running_tbox + proposed axioms
      (remove old axioms for this node first)
   f. KONCLUDE CHECK → pass or fail
      - pass: store in node registry (status=proposed), append new classes/props
              to running_tbox
      - fail (attempt < 3): pass truncated stderr back → agent revises → goto (e)
      - fail (attempt = 3): store with status=failed, coverage_score=0, log warning

4. HARMONIZATION PASS (one LLM call per chapter)
   context: all new IRIs coined in step 3 + their labels/definitions
   task: identify semantic duplicates, propose owl:equivalentClass/Property links
   validate corrections with Konclude
   store corrections in harmonization_registry

5. ASSEMBLE CHAPTER REGISTRY
   flatten all node registries → data/axiom_candidates/ch{N}.jsonl (compatibility alias)
   write per-chapter coverage report → data/reports/ch{N}_coverage.json

6. ABOX DISPATCH (in abox.py)
   if approved node axioms exist: use them (additive to hand-authored)
   else: hand-authored fallback
```

## Output Structure

```
data/
  legal_text/
    ch22/
      notes.jsonl          (existing — snippet texts)
      full/                (NEW — full note texts from PDF fetch)
        {note_id}.txt
  axiom_candidates/
    ch22/                  (NEW — per-node directory)
      node_22.jsonl
      node_2201.jsonl
      node_220110.jsonl
      ...
    ch22.jsonl             (compatibility alias — generated, not hand-edited)
  reports/
    ch22_coverage.json     (NEW)

src/
  agent/
    context_builder.py     (NEW — assembles static context + running TBox)
    llm_axiom_agent.py     (REPLACE llm_agent.py stub — real implementation)
    node_registry.py       (NEW — per-node registry, replaces candidate_registry usage)
    harmonizer.py          (NEW — chapter harmonization pass)
    coverage_reporter.py   (NEW — aggregates coverage metrics)
  schema/
    node_axiom_set.py      (NEW — replaces AxiomCandidate for agent-generated output)
  fetcher/
    class_api.py           (MODIFY — add fetch_full_note_text using /getNotesById)
```

## Implementation Units

- [ ] **IU1: Static context builder (`src/agent/context_builder.py`)**

**Goal:** Serialize the BFO excerpt + current TBox as a compact Turtle string suitable for
embedding in the LLM system prompt. Assemble the per-node dynamic context (hierarchy path,
full notes, running TBox).

**Requirements:** R2, R3

**Dependencies:** `src/ontology/core.py`, `src/ontology/tbox.py`, `src/ontology/bfo_stubs.py`

**Files:**
- Create: `src/agent/context_builder.py`
- Test: `tests/unit/test_context_builder.py`

**Approach:**
- `build_static_context(chapter: int) -> str`: serialize BFO stubs + core TBox + chapter
  TBox into compact Turtle. Cap at 500 triples; log a warning if exceeded.
- `build_node_context(cn_code, legal_sections, wizard_nodes, running_tbox_ttl) -> dict`:
  return a structured dict with keys `hierarchy_path`, `notes_en`, `notes_de`,
  `running_tbox`, `existing_axioms`.
- The BFO excerpt must include: label, definition, and parent for each BFO class
  referenced in the current TBox.
- `compute_tbox_hash(chapter: int) -> str`: SHA256 over the serialized TBox string.

**Test scenarios:**
- Happy path: `build_static_context(22)` returns valid Turtle parseable by rdflib, length
  under 500 triples.
- Edge case: chapter with no chapter-specific props still returns valid context.
- Happy path: `build_node_context` for `cn_code="2204"` includes ancestors `"22"` in
  `hierarchy_path`, includes EN and DE notes where available.
- Edge case: node with no notes returns empty note fields, not an error.

**Verification:** `build_static_context` output parses without error; triple count logged.

---

- [ ] **IU2: Node axiom schema + propose_axioms tool definition (`src/schema/node_axiom_set.py`)**

**Goal:** Define the Pydantic schema for agent output and the JSON schema for the
`propose_axioms` tool that enforces BFO-aligned structured output.

**Requirements:** R2, R7, R8

**Dependencies:** IU1

**Files:**
- Create: `src/schema/node_axiom_set.py`
- Test: `tests/unit/test_node_axiom_set.py`

**Approach:**
- `NewClass`: `iri_local_name: str`, `label_en: str`, `label_de: str`, `definition_en: str`,
  `bfo_parent_iri: str` (must be a BFO or existing EUCN IRI), `class_type: Literal["material_entity", "process", "quality", "other"]`.
- `NewProperty`: `iri_local_name: str`, `label_en: str`, `property_type: Literal["object", "data"]`,
  `domain_iri: str`, `range_iri: str`, `is_functional: bool`.
- `NodeRestriction`: `owl_class_iri: str`, `restriction_type: Literal["someValuesFrom", "hasValue", "decimalRange", "complement"]`,
  `property_iri: str`, `value: str`, `facet: str | None`.
- `NodeAxiomSet`: `cn_code: str`, `new_classes: list[NewClass]`, `new_properties: list[NewProperty]`,
  `restrictions: list[NodeRestriction]`, `coverage_score: float` (0–1),
  `coverage_explanation: str`, `source_note_ids: list[str]`, `source_text_hash: str`,
  `tbox_hash: str`, `status: Literal["proposed", "approved", "failed"]`,
  `agent_model: str`, `generated_at: str`.
- `candidate_id` auto-computed from `SHA256(cn_code + source_text_hash + tbox_hash)`.
- `PROPOSE_AXIOMS_TOOL_SCHEMA`: the Anthropic tool definition (name, description,
  input_schema matching NodeAxiomSet).

**Test scenarios:**
- Happy path: valid `NodeAxiomSet` with one class, one property, one restriction
  round-trips through JSON serialization.
- Edge case: `coverage_score` outside [0, 1] raises `ValidationError`.
- Edge case: empty `new_classes` and empty `restrictions` is valid (agent found nothing
  to axiomatize).
- Happy path: `candidate_id` is deterministic for the same inputs.

**Verification:** `NodeAxiomSet.model_validate_json(NodeAxiomSet(...).model_dump_json())` is identity.

---

- [ ] **IU3: Node registry (`src/agent/node_registry.py`)**

**Goal:** Per-node JSONL registry: load, upsert, staleness check (source hash + TBox hash),
save. Replace chapter-level `CandidateRegistry` usage for agent-generated axioms.

**Requirements:** R5, R8

**Dependencies:** IU2

**Files:**
- Create: `src/agent/node_registry.py`
- Test: `tests/unit/test_node_registry.py`

**Approach:**
- `NodeRegistry(chapter_dir: Path)`: directory-per-chapter, one `node_{cn_code}.jsonl` per
  code. Load lazily.
- `is_stale(cn_code, source_text_hash, tbox_hash) -> bool`: returns True if no entry
  exists OR either hash differs from stored.
- `upsert(axiom_set: NodeAxiomSet)`: atomic write (tmp + rename pattern from existing
  `CandidateRegistry`).
- `get_approved(cn_code) -> NodeAxiomSet | None`.
- `iter_all() -> Iterator[NodeAxiomSet]`: iterate all stored sets across all node files.
- `flatten_to_candidates(out_path: Path)`: write compatibility `ch{N}.jsonl` in
  `AxiomCandidate` format from approved sets.

**Test scenarios:**
- Happy path: upsert then load returns same object.
- Staleness: `is_stale` returns True when source hash differs; False when both hashes match.
- Staleness: `is_stale` returns True when tbox_hash differs even if source hash matches.
- Edge case: `get_approved` for unknown cn_code returns None.
- Happy path: atomic save — if process dies mid-write, no corrupt partial file.

**Verification:** round-trip upsert/load for 10 nodes, all recoverable; staleness logic verified
against all four hash-match combinations.

---

- [ ] **IU4: Full note text fetcher (`src/fetcher/class_api.py` extension)**

**Goal:** Fetch the complete legal text for a note via `/getNotesById`, cache to
`data/legal_text/ch{N}/full/{note_id}.txt`, skip if cached.

**Requirements:** R1

**Dependencies:** existing `class_api.py`

**Files:**
- Modify: `src/fetcher/class_api.py`
- Test: `tests/unit/test_class_api.py` (extend existing)

**Approach:**
- `fetch_full_note_text(note_id: str, out_dir: Path, *, force: bool = False) -> str`: checks
  `out_dir/{note_id}.txt`; if present and not forced returns cached content; else calls
  `/classification/getNotesById?referenceId={note_id}`, decodes base64 PDF bytes, extracts
  plain text with `pdfminer.six` or returns raw text if API returns plain text. Writes to
  cache file. Rate-limit: 0.5s between calls.
- `fetch_all_full_notes(chapter, out_dir, note_ids, *, force) -> dict[str, str]`: batch
  wrapper.

**Test scenarios:**
- Happy path: cached file returned without HTTP call (mock filesystem).
- Happy path: uncached file fetched, decoded, written, and returned (mock HTTP).
- Error path: HTTP 4xx raises `ValueError` with note_id in message.
- Edge case: empty response body returns empty string, does not raise.

**Verification:** `data/legal_text/ch22/full/` populated for all note_ids in ch22 notes.jsonl.

---

- [ ] **IU5: LLM axiom agent (`src/agent/llm_axiom_agent.py`)**

**Goal:** Core agent: build prompt, call Claude with `propose_axioms` tool, validate output,
run Konclude feedback loop (max 3 iterations), return `NodeAxiomSet`.

**Requirements:** R1, R2, R4, R7

**Dependencies:** IU1, IU2, `src/reasoning/konclude.py`

**Files:**
- Create: `src/agent/llm_axiom_agent.py`
- Test: `tests/unit/test_llm_axiom_agent.py`

**Approach:**
- `LLMAxiomAgent(model: str, static_context: str)`: initialises `anthropic.Anthropic` client
  once; `static_context` embedded in system prompt.
- `run(cn_code, node_context, base_tbox_path, running_tbox_path, existing_axioms_ttl) -> NodeAxiomSet`:
  - Build user message from node_context (hierarchy path, notes EN/DE, running TBox summary).
  - Call `client.messages.create` with `tools=[PROPOSE_AXIOMS_TOOL_SCHEMA]`,
    `tool_choice={"type": "any"}`.
  - Parse `ToolUseBlock` from response.
  - Build scratch TTL: base_tbox + running_tbox + proposed axioms.
  - Call `check_consistency(scratch_ttl)`.
  - On `KoncludeConsistencyError`: extract first 2000 chars of stderr (strip `[INFO]` lines),
    send as tool result with `is_error=True`, request revision. Increment attempt counter.
  - After 3 failures: return `NodeAxiomSet` with `status="failed"`, `coverage_score=0`.
  - On success: return `NodeAxiomSet` with `status="proposed"`.
- System prompt template: in `src/agent/prompts/axiom_agent_system.txt` — not hardcoded
  in Python.
- System prompt must instruct the agent to:
  - Reuse existing EUCN classes/properties rather than coining duplicates.
  - Use BFO_0000030 as parent for material entities, BFO_0000015 for processes.
  - Declare `owl:FunctionalProperty` for single-valued object properties.
  - Use `owl:disjointWith` between process classes that discriminate the same CN branch.
  - Set `coverage_score=0` and explain what was not covered if the note is purely
    administrative (e.g., cross-references only).
  - Prefer narrow axioms over broad ones when uncertain.

**Test scenarios:**
- Happy path (mocked API + mocked Konclude): first attempt consistent, returns `proposed`.
- Retry: first attempt inconsistent, second attempt consistent → `proposed` after 2 calls.
- Max retries: 3 inconsistent attempts → `failed`, `coverage_score=0`.
- Edge case: node with no legal text (empty notes) → `NodeAxiomSet` with empty lists,
  `coverage_score=0.0`, `coverage_explanation="No legal text available"`.
- Happy path: `propose_axioms` tool use block is parsed correctly.

**Verification:** unit tests pass with mocked Anthropic client and mocked Konclude.

---

- [ ] **IU6: Chapter run orchestrator (`src/agent/chapter_runner.py`)**

**Goal:** Orchestrate the topological per-node loop for a chapter: assemble static context,
load nodes in depth order, check staleness, call the agent, accumulate running TBox,
write node registries.

**Requirements:** R1, R3, R5, R8, R10

**Dependencies:** IU1–IU5, `src/schema/wizard.py`

**Files:**
- Create: `src/agent/chapter_runner.py`
- Test: `tests/unit/test_chapter_runner.py`

**Approach:**
- `ChapterRunner(chapter: int, model: str, data_root: Path)`.
- `run(wizard_tree: WizardTree, force: bool = False) -> ChapterRunResult`:
  1. Assemble `static_context` and `tbox_hash` via `context_builder`.
  2. Fetch all full note texts (skipping cached).
  3. Load `node_registry`.
  4. Collect all cn_codes from `data/legal_text/ch{N}/notes.jsonl`, sorted by code
     length then lexicographically (topological order).
  5. For each cn_code:
     - Compute `source_text_hash` over all full notes for this code (sorted by note_id).
     - Check `node_registry.is_stale(cn_code, source_text_hash, tbox_hash)`.
     - If not stale: skip, log `[agent] skip {cn_code} (cache hit)`.
     - If stale: call agent, upsert result, append new classes/props to running TBox.
  6. Return `ChapterRunResult` (counts: skipped, proposed, failed, total nodes).
- `running_tbox_path = data_root / "agent_tbox" / f"ch{chapter:02d}" / "running.ttl"`:
  reset at start of each chapter run, built up incrementally.

**Test scenarios:**
- Happy path: two nodes, both stale, both return `proposed` → two upserts, running TBox
  grows.
- Cache hit: node with matching hashes → zero agent calls.
- Topological order: `"22"` processed before `"2204"` before `"220410"`.
- Error path: agent returns `failed` for one node → run continues, failure counted.
- Edge case: chapter with no legal text notes → `ChapterRunResult(total=0, skipped=0,
  proposed=0, failed=0)`.

**Verification:** run against ch22 fixture data with mocked agent; all 79 cn_codes visited
in correct order.

---

- [ ] **IU7: Harmonization pass (`src/agent/harmonizer.py`)**

**Goal:** After the chapter run, call the LLM with all new IRIs coined during the run to
detect semantic duplicates and produce `owl:equivalentClass`/`owl:equivalentProperty` merge
links. Validate with Konclude.

**Requirements:** R6

**Dependencies:** IU5, IU6

**Files:**
- Create: `src/agent/harmonizer.py`
- Test: `tests/unit/test_harmonizer.py`

**Approach:**
- `harmonize(chapter: int, new_iris: list[dict], base_tbox_path, model: str) -> list[HarmonizationCorrection]`:
  - `new_iris` = list of `{iri, label, definition, class_or_property}` for every new
    concept coined in the chapter run.
  - Single LLM call with tool `propose_harmonization` (schema: list of
    `{primary_iri, duplicate_iris, equivalence_type}`).
  - Build correction triples: `owl:equivalentClass` or `owl:equivalentProperty` links.
  - Add corrections to a scratch graph on top of the assembled chapter TBox.
  - Konclude consistency check.
  - On failure: log warning and return empty corrections (do not block chapter completion).
- `HarmonizationCorrection`: `primary_iri`, `duplicate_iri`, `equivalence_type`, `rationale`.
- Corrections stored in `data/axiom_candidates/ch{N}/harmonization.jsonl`.

**Test scenarios:**
- Happy path: two IRIs with identical definitions → one equivalentClass link proposed,
  consistent → correction stored.
- No duplicates: LLM returns empty list → zero corrections, consistent Konclude check.
- Konclude failure: correction is skipped, warning logged, run completes.

**Verification:** harmonizer returns without raising for both duplicate and no-duplicate cases.

---

- [ ] **IU8: Coverage reporter (`src/agent/coverage_reporter.py`)**

**Goal:** Aggregate per-node `coverage_score` and `coverage_explanation` into a per-chapter
report, surface gaps, and write `data/reports/ch{N}_coverage.json`.

**Requirements:** R7

**Dependencies:** IU3, IU6

**Files:**
- Create: `src/agent/coverage_reporter.py`
- Test: `tests/unit/test_coverage_reporter.py`

**Approach:**
- `ChapterCoverageReport`: `chapter`, `total_nodes`, `nodes_with_notes`, `nodes_proposed`,
  `nodes_failed`, `nodes_skipped`, `mean_coverage_score`, `low_coverage_nodes` (list of
  `{cn_code, coverage_score, explanation}` where score < 0.5), `generated_at`.
- `build_report(chapter, node_registry, run_result) -> ChapterCoverageReport`.
- `write_report(report, out_path: Path)`.
- Pipeline prints summary to stdout: total nodes, mean coverage, count with score < 0.5.

**Test scenarios:**
- Happy path: 3 nodes (scores 0.9, 0.3, 0.7) → mean 0.63, one low-coverage node.
- Edge case: all nodes skipped (cache hits) → report reflects prior stored scores.

**Verification:** report JSON written and parseable; low-coverage list correct.

---

- [ ] **IU9: Pipeline integration**

**Goal:** Wire the new `ChapterRunner` into `src/pipeline.py` as a replacement for the
`fetch-legal-text` step. Update `abox.py` dispatch to use `NodeRegistry.get_approved`.
Keep hand-authored fallback.

**Requirements:** R9, R10

**Dependencies:** IU1–IU8

**Files:**
- Modify: `src/pipeline.py`
- Modify: `src/ontology/abox.py`
- Test: `tests/integration/test_pipeline.py` (extend)

**Approach:**
- New `--run-axiom-agent` CLI flag (default off). When set, runs `ChapterRunner` as Step
  2.6. The old `fetch-legal-text` + `rule_extractor` path becomes `--fetch-legal-text`
  (unchanged, for data collection only).
- `abox.py` dispatch: read `NodeRegistry` for chapter; collect all `approved` sets;
  build axiom triples via `axiom_builder`; apply additively on top of hand-authored.
- `src/ontology/abox.py` should NOT import `LLMAxiomAgent` directly — only `NodeRegistry`
  and `axiom_builder`.
- The `--run-axiom-agent` step requires `ANTHROPIC_API_KEY` env var; raises
  `EnvironmentError` with clear message if absent.

**Test scenarios:**
- Integration: pipeline with `--run-axiom-agent` (mocked agent) produces consistent TTL.
- Integration: pipeline without flag uses hand-authored axioms (existing tests pass unchanged).
- Error path: missing `ANTHROPIC_API_KEY` raises before any API call.
- Integration: `abox.py` with a node registry containing approved sets produces axioms
  for those nodes; hand-authored axioms also present.

**Verification:** existing integration tests unchanged; new flag test produces TTL.

---

- [ ] **IU10: Retire chapter-specific hand-authored modules (post-validation)**

**Goal:** Once the LLM agent has been validated for a chapter, retire the corresponding
hand-authored modules by converting them to no-op stubs with a deprecation comment.
Remove chapter-specific entries from `chapter_registry.py`.

**Requirements:** R9

**Dependencies:** IU9, manual validation of agent output quality

**Files:**
- Modify: `src/ontology/equivalence_axioms_beverages.py`
- Modify: `src/ontology/equivalence_axioms_ch23_feed.py`
- Modify: `src/ontology/product_classes_beverages.py`
- Modify: `src/ontology/product_classes_ch23_feed.py`
- Modify: `src/ontology/process_classes_beverages.py`
- Modify: `src/ontology/process_classes_ch23_feed.py`
- Modify: `src/ontology/chapter_registry.py`

**Approach:**
- Each hand-authored module body replaced with: `def add_*(g): pass  # retired YYYY-MM-DD`.
- `chapter_registry.py`: set `add_equivalence_axioms=None` for retired chapters.
- A final Konclude check confirms the chapter ontology remains consistent after retirement.

**Test expectation:** none — this is a mechanical retirement step; existing tests verify
consistency.

**Verification:** Konclude consistency check passes for all retired chapters.

## System-Wide Impact

- **Interaction graph:** `pipeline.py` → `chapter_runner.py` → `llm_axiom_agent.py` →
  Anthropic API + Konclude. `abox.py` → `node_registry.py` → approved axioms.
- **Error propagation:** agent failures are per-node; a failing node logs a warning and
  continues. The chapter run does not abort on individual node failures. Pipeline aborts only
  if Konclude consistency check on the assembled chapter ontology fails at the end.
- **State lifecycle risks:** the running TBox scratch file is reset at chapter run start;
  interrupted runs leave a partial scratch file that will be overwritten on next run.
  Node registry files are atomically written (tmp + rename) so no corruption on interrupt.
- **API surface parity:** `CandidateRegistry` remains for backward compatibility; no changes
  to its public interface. `NodeRegistry` is the new primary store.
- **Integration coverage:** Konclude must be available for IU5 and IU9 integration tests.
  Tests that cannot run Konclude should mock it and document the mock.
- **Unchanged invariants:** TARIC ABox, wizard classification nodes, provenance graph,
  and TARIC measure individuals are not modified by this plan.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| LLM produces malformed Turtle in `propose_axioms` response | Structured tool use enforces JSON schema; Turtle serialization from schema, not from free-form LLM text |
| Running TBox exceeds context window (>500 triples) | Hard cap + warning; prune to only classes/properties (no restrictions) in running TBox |
| Anthropic API rate limits during chapter run (79 nodes × 2 languages) | 1s delay between calls; exponential backoff on 429; parallel across chapters not within a chapter |
| Harmonization introduces new inconsistencies | Konclude check before committing corrections; skip on failure |
| `fetch_note_pdf` PDF text extraction quality | Evaluate `pdfminer.six` on sample notes; if extraction is poor, fall back to `noteDescrSnippet` |
| TBox hash drift invalidating large cache | Log invalidation reason; provide `--tbox-unchanged` flag to skip tbox-hash staleness check when developer knows the TBox change is irrelevant |

## Documentation / Operational Notes

- `ANTHROPIC_API_KEY` must be set in the environment for `--run-axiom-agent`.
- The agent run is expensive (API calls + Konclude per node). Run it on schedule or
  explicitly; never as a default CI step.
- `data/legal_text/` remains gitignored (regenerable). `data/axiom_candidates/` and
  `data/reports/` are tracked.
- Coverage reports in `data/reports/ch{N}_coverage.json` should be reviewed before
  retiring hand-authored modules (IU10).

## Sources & References

- Related code: `src/agent/candidate_registry.py`, `src/agent/rule_extractor.py`,
  `src/ontology/bfo_stubs.py`, `src/reasoning/konclude.py`
- Supersedes: `docs/plans/2026-06-08-006-feat-legal-text-axiom-agent-plan.md`
- BFO 2020: `http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl`
- Anthropic SDK: `pyproject.toml` dependency `anthropic>=0.40`
