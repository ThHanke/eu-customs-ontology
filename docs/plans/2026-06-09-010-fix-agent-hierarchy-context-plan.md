---
title: "fix: Wire heading classes into Beverage hierarchy and fix agent CN context"
type: fix
status: active
date: 2026-06-09
---

# fix: Wire heading classes into Beverage hierarchy and fix agent CN context

## Overview

Agent-generated OWL classes for chapter-level CN headings (e.g. `VermouthWineFreshGrapesFlavouredPlants2205`, `CiderPerryMeadSakFermentedBeverages2206`) are disconnected from the `eucn:Beverage` hierarchy — they have `rdfs:subClassOf bfo:BFO_0000030` instead of a meaningful EUCN parent. Two independent bugs cause this:

1. `heading_classes.py` hardcodes `BFO_0000030` as parent instead of a chapter-specific root class.
2. The agent's `_compute_hierarchy_path` always returns empty (wrong dict, wrong direction check), so the agent never sees the wizard ancestor question chain — it has to guess parent classes from the running TBox alone.
3. The agent static context excludes heading class IRIs (`heading_labels=None`), so when it generates terminal-node classes it cannot use existing heading classes as `bfo_parent_iri`.

## Problem Frame

The pipeline has two parallel class-creation tracks that do not know about each other:

- **Track A** (`src/ontology/heading_classes.py`): creates 4-digit heading classes from `tariffnumber_ch22.json` labels. Parent is always `BFO_0000030` — these classes float disconnected from `eucn:Beverage`.
- **Track B** (LLM axiom agent): creates semantically-named product classes from legal text and the running TBox. When a suitable parent is in the running TBox it wires correctly; when not, it also falls back to `BFO_0000030`.

Result: 93 EUCN classes with no EUCN superclass, including all chapter-level product groupings.

## Requirements Trace

- R1. All product class IRIs in chapter 22 must be reachable from `eucn:Beverage` via `rdfs:subClassOf` transitivity.
- R2. The LLM agent must receive the structural CN hierarchy (ancestor heading descriptions) as node context so it can make informed parent-class choices.
- R3. The agent static context must expose existing heading class IRIs so terminal-node classes use heading classes as parents rather than creating a parallel hierarchy.
- R4. `_compute_hierarchy_path` must return the correct ancestor chain for any CN code.

## Scope Boundaries

- Only chapter 22 (`eucn:Beverage` as root). Other chapters are out of scope; the fix must be parameterisable.
- Does not change the fundamental two-track design — Track A (heading_classes) and Track B (agent) continue to coexist.
- Does not rename existing agent-generated classes (no ontology identity churn).
- Does not modify the `data/axiom_candidates/` JSONL files or rerun the agent.

### Deferred to Separate Tasks

- Merging/aliasing the two parallel class names (e.g. `FlavouredWineOfFreshGrapes` and `VermouthWineFreshGrapesFlavouredPlants2205`) into a single class: separate refactor after hierarchy is connected.
- Applying the same fix to other chapters (ch23, etc.): follow-on once ch22 is verified.

## Context & Research

### Relevant Code and Patterns

- `src/ontology/heading_classes.py:64` — `g.add((iri, RDFS.subClassOf, BFO_OBJECT))` — hardcoded wrong parent
- `src/ontology/tbox.py` — `build_tbox(g, chapter, heading_labels=None)` — passes labels to `add_heading_classes`; chapter root class not currently a parameter
- `src/agent/context_builder.py` — `build_static_context` calls `build_tbox(g, chapter=chapter, heading_labels=None)` (deliberate exclusion); `_compute_hierarchy_path` uses `wizard_nodes_by_cn` (terminal-only keys, wrong direction check)
- `src/agent/chapter_runner.py:98–101` — `wizard_nodes_by_cn` built from terminal nodes only; intermediate nodes excluded
- `src/agent/llm_axiom_agent.py:72–101` — "Hierarchy path" section not rendered when `hierarchy_path` is empty
- `src/agent/prompts/axiom_agent_system.txt` — instructs agent to use existing EUCN IRIs as `bfo_parent_iri`; cannot do so without seeing heading class IRIs
- `data/intermediate/tariffnumber_ch22.json` — 9 four-digit heading keys + 137 eight-digit terminal keys, format `{"en": "...", "de": "..."}`

### Key Structural Finding

Zero-padding lookup: any wizard node_id can be derived from a CN code prefix by `cn_code.ljust(8, '0')`. For ch22:
- `'2205'` → node_id `'22050000'` (intermediate, path `['22000000']`)
- `'220600'` → node_id `'22060000'` (intermediate, path `['22000000']`)
- All intermediate nodes have `cn_code = None` and are excluded from `wizard_nodes_by_cn`.

## Key Technical Decisions

- **Chapter root class as parameter**: `add_heading_classes` gains an optional `chapter_root_iri: URIRef | None = None` parameter. When `None`, falls back to `BFO_OBJECT` (preserving backward compat for chapters not yet migrated). `build_tbox` passes the correct IRI for known chapters.
- **Chapter root registry**: Use `src/ontology/chapter_registry.py` to expose a per-chapter root class IRI constant (e.g. `CHAPTER_ROOT = "https://w3id.org/eucn/Beverage"` for ch22). `build_tbox` looks it up via `get_chapter(chapter).ROOT_CLASS_IRI`.
- **Fix `_compute_hierarchy_path`**: Replace `wizard_nodes_by_cn` (terminal-only) with `wizard_tree.nodes` (all nodes) in the call site. Fix the lookup to use `node_id = cn_code.ljust(8, '0')` directly, then walk `path_from_root` to collect ancestors. This is O(path_length), not O(all_nodes).
- **Re-enable heading labels in agent context**: Revert `heading_labels=None` to pass actual heading labels in `build_static_context`. The comment cited performance concerns; the cap is 500 triples and the 9 heading labels add only ~18 triples.
- **No prompt change needed**: The system prompt already instructs the agent to prefer existing EUCN IRIs as parents. Providing the IRIs via TBox is sufficient.

## Open Questions

### Resolved During Planning

- **Why was `heading_labels=None` chosen?** Comment said "per-heading taxonomy triples aren't relevant to axiom generation." Research shows this was incorrect — the agent needs heading class IRIs to make correct parent choices. Reverting.
- **Does fixing heading parent break existing approved axioms?** The 79 approved ch22 node axioms use `bfo_parent_iri` values that are EUCN class IRIs already properly chained. The heading class fix adds a `subClassOf Beverage` edge but does not change any existing triple. No re-approval needed.
- **Will re-enabling heading labels push static context over the 500-triple cap?** 9 headings × ~2 triples each = ~18 triples. Current static context is 488 triples. 488 + 18 = 506. The cap is a warning threshold only; it does not block execution. The warning can be raised to 550 or removed.

### Deferred to Implementation

- Exact `ROOT_CLASS_IRI` constant placement — chapter_registry module attribute or separate config dict in tbox.py. Either works; implementer chooses based on existing module shape.
- Whether `_compute_hierarchy_path` should return the question_text from intermediate nodes (currently empty for chapter/heading nodes) or just the code. Implementer decides based on what the agent prompt makes useful.

## Implementation Units

- [ ] **IU1: Fix `add_heading_classes` to accept and use a chapter root class IRI**

**Goal:** 4-digit heading classes gain `rdfs:subClassOf eucn:Beverage` (or chapter-specific root) instead of `BFO_0000030`.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `src/ontology/heading_classes.py`
- Modify: `src/ontology/tbox.py`
- Modify: `src/ontology/chapter_registry.py` (or chapter modules under `src/ontology/chapters/`)
- Test: `tests/unit/test_heading_classes.py`

**Approach:**
- Add `chapter_root_iri: URIRef | None = None` to `add_heading_classes` signature
- Replace `g.add((iri, RDFS.subClassOf, BFO_OBJECT))` with `g.add((iri, RDFS.subClassOf, chapter_root_iri or BFO_OBJECT))`
- Expose a `CHAPTER_ROOT_IRI` attribute (or equivalent) on the ch22 chapter module; `build_tbox` retrieves it via `get_chapter(chapter)` and passes to `add_heading_classes`
- For chapters with no `CHAPTER_ROOT_IRI`, fall back to `BFO_OBJECT` to avoid breaking existing chapters

**Patterns to follow:**
- Existing `get_chapter()` pattern in `src/ontology/chapter_registry.py`
- How `add_equivalence_axioms` is retrieved per chapter

**Test scenarios:**
- Happy path: `add_heading_classes(g, 22, labels, chapter_root_iri=EUCN.Beverage)` — each 4-digit heading class has `rdfs:subClassOf eucn:Beverage`
- Backward compat: `add_heading_classes(g, 22, labels)` (no `chapter_root_iri`) — heading classes have `rdfs:subClassOf BFO_0000030`
- Integration: `build_tbox(g, chapter=22, heading_labels=labels)` — heading classes reachable from `eucn:Beverage` via `rdfs:subClassOf`

**Verification:**
- `python3 -c "from rdflib import Graph, Namespace, RDFS; ..."` query on built TBox confirms `VermouthWineFreshGrapesFlavouredPlants2205` has `eucn:Beverage` as superclass (direct or transitive)

---

- [ ] **IU2: Fix `_compute_hierarchy_path` to use all wizard nodes and correct ancestor lookup**

**Goal:** Agent sees the correct ancestor chain (chapter → heading → subheading) for any CN code being processed.

**Requirements:** R2, R4

**Dependencies:** None (independent of IU1)

**Files:**
- Modify: `src/agent/context_builder.py`
- Modify: `src/agent/chapter_runner.py`
- Test: `tests/unit/test_context_builder.py`

**Approach:**
- In `chapter_runner.py`: pass `wizard_tree.nodes` (all nodes, not just terminal) as a second argument to `build_node_context`. Currently only `wizard_nodes_by_cn` (terminal-only) is passed.
- In `context_builder.py`: update `build_node_context` signature to accept `all_wizard_nodes: dict[str, ClassificationNode]`. Rewrite `_compute_hierarchy_path(cn_code, all_wizard_nodes)` to:
  1. Compute `node_id = cn_code.ljust(8, '0')` and look it up in `all_wizard_nodes`
  2. Walk `node.path_from_root` to collect ancestor node_ids
  3. For each ancestor node_id, return its `question_text` (or heading EN label if `question_text` is empty)
- Keep the `wizard_nodes_by_cn` parameter for the existing legal-text lookup (unchanged use)

**Patterns to follow:**
- `ClassificationNode.path_from_root` field structure
- Existing `_compute_hierarchy_path` contract (returns `list[dict]`)

**Test scenarios:**
- Happy path: cn_code `'22041013'` → ancestor chain includes chapter 22 and heading 2204 ancestor node question_texts
- Edge case: cn_code `'22'` (chapter root) → empty ancestor list
- Edge case: cn_code not in `all_wizard_nodes` after padding → empty list, no exception
- Regression: cn_code `'2205'` → ancestor list contains node for `'22050000'`

**Verification:**
- `build_node_context` called with a 2205 code returns non-empty `hierarchy_path`

---

- [ ] **IU3: Re-enable heading labels in agent static context**

**Goal:** Agent TBox includes 4-digit heading class IRIs so the LLM can select heading classes as `bfo_parent_iri` when proposing terminal-node classes.

**Requirements:** R3

**Dependencies:** IU1 (heading classes should have correct parents before being included in agent context)

**Files:**
- Modify: `src/agent/context_builder.py`
- Test: `tests/unit/test_context_builder.py`

**Approach:**
- In `build_static_context(chapter, extract_date)`: load heading labels from `data/intermediate/tariffnumber_ch{chapter:02d}.json` using existing `_load_heading_labels(chapter)` helper (already present in the file)
- Pass loaded labels to `build_tbox(g, chapter=chapter, heading_labels=labels)` instead of `None`
- Raise or remove the 500-triple warning cap (or increase to 600) to avoid noisy warnings; the heading label triples are intentional
- No change to the prompt system text needed — agent already instructed to prefer existing EUCN IRIs

**Patterns to follow:**
- `_load_heading_labels(chapter)` already in `context_builder.py`
- Existing `build_static_context` structure

**Test scenarios:**
- Happy path: `build_static_context(22)` serialized Turtle contains `eucn:VermouthWineFreshGrapesFlavouredPlants2205` as an OWL class
- Happy path: `build_static_context(22)` Turtle contains `rdfs:subClassOf eucn:Beverage` for heading classes (requires IU1)
- Edge case: heading label file absent (`tariffnumber_ch22.json` missing) → `_load_heading_labels` returns `{}` → `build_tbox` called with empty dict → no heading classes in TBox, no error
- Hash stability: `compute_tbox_hash` uses `extract_date=date(2000,1,1)` — heading labels are deterministic for a given `tariffnumber_ch{nn}.json`, so hash is stable across runs on the same data

**Verification:**
- `build_static_context(22)` returns Turtle with all 9 chapter 22 heading class IRIs present and each connected to `eucn:Beverage`

## System-Wide Impact

- **Interaction graph:** `build_tbox` → `add_heading_classes` chain affected. `build_static_context` → `build_tbox` chain affected. No ABox code changes.
- **TBox hash change:** adding heading labels to `build_static_context` changes `compute_tbox_hash(22)`. All 79 approved ch22 node axioms will appear as "tbox bump only" skippable on next pipeline run — they will NOT be re-proposed. The skip logic preserves approved nodes across TBox bumps.
- **State lifecycle:** No persistent data deleted. No axiom_candidates files modified. Pipeline re-runs pick up new heading class triples automatically.
- **API surface parity:** `add_heading_classes` signature gains an optional kwarg — backward-compatible for all callers.
- **Unchanged invariants:** All 79 approved ch22 axioms remain valid. Konclude consistency check still runs. Demo TTL unaffected (demo uses EUCN class IRIs not BFO IRIs).

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| TBox hash change forces manual re-review of 79 approved axioms | Skip logic preserves `approved` status across TBox bumps — no re-review needed |
| Heading labels file absent on first run | `_load_heading_labels` returns `{}` gracefully; pipeline logs warning |
| 506-triple static context exceeds warning cap | Raise cap to 600 or remove — heading triples are intentional, not noise |
| Fixing heading parent may reveal inconsistency via Konclude | Run `konclude-check` after rebuild; fix any new inconsistency in a follow-up |

## Sources & References

- Related code: `src/ontology/heading_classes.py:64`
- Related code: `src/agent/context_builder.py` (`_compute_hierarchy_path`, `build_static_context`)
- Related code: `src/agent/chapter_runner.py:98–101`
- Related code: `src/ontology/tbox.py` (`build_tbox` signature)
