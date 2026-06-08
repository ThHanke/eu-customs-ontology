---
title: "feat: BFO process class architecture for CN discriminating axioms"
type: feat
status: active
date: 2026-06-08
origin: docs/brainstorms/2026-06-08-004-feat-bfo-process-class-architecture-requirements.md
---

# feat: BFO Process Class Architecture for CN Discriminating Axioms

## Overview

Replace `eucn:fermentationBase` (a `DatatypeProperty` with string literal values) with
`eucn:producedBy` (an `ObjectProperty`, `owl:inverseOf obo:RO_0002234`) whose values are
**named process singleton individuals** typed as `bfo:Process` subclasses. Ch22 becomes the
reference implementation for all future CN chapters.

The world-closure mechanism is unchanged in kind: `owl:FunctionalProperty` on `eucn:producedBy`
combined with `owl:differentFrom` assertions between all process singletons enables complement-
based exclusion inference identically to the current string-literal approach. Structurally,
`_has_value_restr` and `_neg_hasvalue_from_disjoint_equiv` are generic over RDF nodes and
require no code changes — only the property IRI and value nodes passed to them change.

## Problem Frame

String literals on a datatype property (`fermentationBase "malt"`) are non-BFO-aligned and
create a typed vocabulary with no shared class hierarchy, no inter-class disjointness, and
no connection to upper-ontology process semantics. As the ontology expands to all CN chapters,
every chapter repeats this opaque string pattern. The fix models each product's CN-level
production process as a named `bfo:Process` subclass with a singleton individual, enabling
BFO/RO alignment, inter-chapter vocabulary sharing, and consistent axiom structure across all
chapters. (See origin: `docs/brainstorms/2026-06-08-004-feat-bfo-process-class-architecture-requirements.md`)

## Requirements Trace

- R1–R4. Core property: `eucn:producedBy` with `owl:inverseOf obo:RO_0002234`, `FunctionalProperty`, BFO stubs.
- R5–R7. Ch22 process class vocabulary: 7 classes, 7 singletons, pairwise disjoint, `_proc()` helper.
- R8–R10. Equivalence axioms migration: replace property/value references; `_neg_hasvalue_from_disjoint_equiv` unchanged.
- R11–R13. ABox migration: `beverages_demo.ttl` updated; acceptance tests pass; mixed products noted as explicit-ABox-only.
- R14–R15. Pattern documentation: `docs/ontology-patterns.md` + README section.

## Scope Boundaries

- Only Ch22 is migrated; subsequent chapters use the new pattern from the start.
- Full import of BFO/RO ontology files is out of scope — stubs for used IRIs only.
- No mixed product CN class is added for Ch22.
- `wizard_axioms.py` boolean complement restrictions are out of scope (different property set).

### Deferred to Separate Tasks

- Future chapters' process class declarations: each chapter adds its own `process_classes_chNN.py`.
- `docs/solutions/` seeding for this repo: run `/ce-compound` after this work lands.

## Context & Research

### Relevant Code and Patterns

- `src/ontology/bfo_stubs.py` — existing `BFO_0000030` stub pattern to mirror for Process and RO.
- `src/ontology/discriminating_props.py` — `_dp()` helper and `add_discriminating_props()`; the
  `_op()` helper mirrors this for ObjectProperty. Remove `fermentationBase` entirely here.
- `src/ontology/product_classes.py` — `_cls()` and `_disjoint_pairs()` helpers; `_proc()` mirrors
  `_cls()`, `_proc_singleton()` declares the named individual.
- `src/ontology/equivalence_axioms.py` — `_has_value_restr(g, prop, value, key)` takes any RDF
  node as `value`; no change needed. `_neg_hasvalue_from_disjoint_equiv` checks
  `(member, OWL.hasValue, None) in g` — type-agnostic, works with `URIRef` values unchanged.
- `src/ontology/tbox.py` — `build_tbox()` call chain; new `add_process_classes_ch22(g)` call
  must be added after `add_product_classes_ch22(g)`.
- `src/reasoning/konclude.py` — passes TTL directly to WASM CLI; FP stripping is in the CLI
  itself (`rdf-reasoner-konclude`), not here. Existing `fermentationBase FunctionalProperty`
  already passes the WASM consistency check; new `producedBy FunctionalProperty` follows
  the same path with no changes needed to `konclude.py`.

### Institutional Learnings

- **`owl:differentFrom` is required between named singletons** — without explicit differentFrom,
  OWL 2 DL's open-world assumption allows the reasoner to unify distinct individuals, defeating
  FunctionalProperty exclusion. Pairwise `owl:differentFrom` (not `owl:AllDifferent`) is used
  for consistency with the pairwise `owl:disjointWith` convention in `product_classes.py`.
- **`owl:inverseOf` passes through the mapper unchanged** — confirmed in rdf-reasoner-konclude
  docs; safe to declare without workarounds.
- **No `graph.remove()` needed** — we are removing the `fermentationBase` declaration entirely,
  not converting its IRI. The builder is called fresh; no stale DatatypeProperty triple persists.
- **Bilingual labels are a hard invariant** — `test_tbox.py` asserts every class and property
  has `rdfs:label@en`, `rdfs:label@de`, `skos:definition@en`, `skos:definition@de`.

### External References

- OBO Relations Ontology — `obo:RO_0002234` is `has output`: process → material entity it produces.
- BFO 2020 — `BFO_0000015` is `Process`.
- OBO namespace: `http://purl.obolibrary.org/obo/` — already the `BFO` namespace in `namespaces.py`.

## Key Technical Decisions

- **Named singletons + FunctionalProperty** over `someValuesFrom` + anonymous instances:
  `someValuesFrom` + anonymous instances cannot be classified under OWA without world-closure.
  `FunctionalProperty` + named singletons + `owl:differentFrom` provides closure in standard
  OWL 2 DL. (See origin decisions.)
- **`_neg_hasvalue_from_disjoint_equiv` unchanged**: it is already generic over any `hasValue`
  restriction. Post-migration the values it reads are `URIRef` singletons instead of `Literal`
  strings — no structural change required.
- **New file `src/ontology/process_classes_ch22.py`** (not extending `product_classes.py`):
  keeps the Ch22 process vocabulary isolated, matching the future per-chapter pattern.
  `tbox.py` calls `add_process_classes_ch22(g)` after `add_product_classes_ch22(g)`.
- **`eucn:GrainDistillation` singleton shared by Spirit and EthylAlcohol ABox individuals**:
  both `demo:whisky-12y` and `demo:grain-spirit-96` assert `producedBy eucn:grain-distillation`.
  Neither Spirit nor EthylAlcohol has a positive `producedBy` condition in their equivalentClass
  (Phase 2 only). The complement exclusions from siblings (NOT malt, NOT grape, …) combined with
  FunctionalProperty + differentFrom prove `grain-distillation ≠ malt-fermentation`, etc.,
  enabling correct classification.
- **No process class/singleton for Water (CN 2201)** — Water is discriminated by ABV ≤ 0 only;
  `demo:still-water` has no `producedBy` assertion now or after migration.

## Open Questions

### Resolved During Planning

- **Does `_has_value_restr` work with `URIRef` values?** Yes — it takes `value` as any RDF node;
  rdflib's `graph.add()` handles `URIRef` identically to `Literal`.
- **Does `_neg_hasvalue_from_disjoint_equiv` work with `URIRef` values?** Yes — the check
  `(member, OWL.hasValue, None) in g` is type-agnostic.
- **FunctionalProperty on ObjectProperty through WASM?** The FP strip lives in the WASM CLI
  (rdf-reasoner-konclude), not in `konclude.py`. The current `fermentationBase FP` already
  passes; new ObjectProperty FP follows the same path.
- **`obo:RO_0002234` IRI**: confirmed — `RO_0002234` is `has output` in the Relations Ontology;
  IRI `http://purl.obolibrary.org/obo/RO_0002234` follows the existing OBO namespace in the repo.

### Deferred to Implementation

- Exact EN/DE label and definition wording for each process class and singleton — follow the
  pattern in `product_classes.py` but tailor to production-process semantics.
- Whether `add_process_classes_ch22` and `add_bfo_stubs` are tested in the same test file or
  separate ones — follow the existing one-file-per-module test convention.

## High-Level Technical Design

> *Illustrates intended approach; directional guidance for review, not implementation specification.*

```
namespaces.py
  + BFO_PROCESS = BFO["BFO_0000015"]
  + RO_HAS_OUTPUT = BFO["RO_0002234"]

bfo_stubs.py  add_bfo_stubs(g):
  existing: BFO_0000030 (Object)
  + BFO_0000015 (Process)  ← owl:Class, bilingual labels/defs, rdfs:isDefinedBy
  + RO_0002234 (has output) ← owl:ObjectProperty, bilingual labels/defs, rdfs:isDefinedBy

discriminating_props.py  add_discriminating_props(g):
  remove: eucn:fermentationBase (DatatypeProperty + FunctionalProperty)
  + _op(g, iri, …)  ← new ObjectProperty helper parallel to _dp()
  + eucn:producedBy  ← ObjectProperty, FunctionalProperty, inverseOf RO_0002234, range BFO_PROCESS

process_classes_ch22.py  add_process_classes_ch22(g):
  Process classes (each rdfs:subClassOf BFO_PROCESS, bilingual):
    eucn:MaltFermentation, eucn:GrapeFermentation, eucn:GrapeFlavouringProcess,
    eucn:FruitFermentation, eucn:GrainDistillation, eucn:AceticFermentation,
    eucn:SweetenedWaterProcess
  Singletons (each rdf:type OWL.NamedIndividual + process class):
    eucn:malt-fermentation, eucn:grape-fermentation, eucn:grape-flavouring,
    eucn:fruit-fermentation, eucn:grain-distillation, eucn:acetic-fermentation,
    eucn:sweetened-water-process
  Pairwise owl:differentFrom between all 7 singletons (21 pairs)

tbox.py  build_tbox(g):
  existing: add_bfo_stubs, add_discriminating_props, add_product_classes_ch22
  + add_process_classes_ch22(g)  ← inserted after add_product_classes_ch22

equivalence_axioms.py  add_ch22_equivalence_axioms(g):
  ferm → produced_by  (EUCN.fermentationBase → EUCN.producedBy)
  Literal("malt", …) → EUCN["malt-fermentation"]
  Literal("grape", …) → EUCN["grape-fermentation"]
  Literal("grape-flavoured", …) → EUCN["grape-flavouring"]
  Literal("fruit", …) → EUCN["fruit-fermentation"]
  Literal("acetic", …) → EUCN["acetic-fermentation"]
  Literal("sweetened-water", …) → EUCN["sweetened-water-process"]
  All helpers (_has_value_restr, _neg_hasvalue_from_disjoint_equiv) unchanged

beverages_demo.ttl:
  eucn:fermentationBase "malt"^^xsd:string → eucn:producedBy eucn:malt-fermentation
  (one singleton IRI per individual; whisky-12y and grain-spirit-96 both → eucn:grain-distillation)
```

## Implementation Units

- [ ] **IU1: Namespace constants**

**Goal:** Add `BFO_PROCESS` and `RO_HAS_OUTPUT` constants so downstream modules can import
named references rather than constructing BFO IRIs inline.

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Modify: `src/ontology/namespaces.py`

**Approach:**
- Add `BFO_PROCESS = BFO["BFO_0000015"]` and `RO_HAS_OUTPUT = BFO["RO_0002234"]` following
  the existing `BFO_OBJECT = BFO["BFO_0000030"]` convention.
- The `BFO` namespace (`http://purl.obolibrary.org/obo/`) already covers both BFO and RO IRIs.

**Test scenarios:**
- Test expectation: none — pure constant declaration; no behavior to test.

**Verification:** `BFO_PROCESS` and `RO_HAS_OUTPUT` importable from `src.ontology.namespaces`.

---

- [ ] **IU2: BFO Process and RO stubs**

**Goal:** Extend `add_bfo_stubs` to declare `bfo:Process` (BFO_0000015) as an `owl:Class` and
`obo:RO_0002234` (`has output`) as an `owl:ObjectProperty`, with bilingual labels and definitions.

**Requirements:** R1, R2

**Dependencies:** IU1

**Files:**
- Modify: `src/ontology/bfo_stubs.py`
- Modify: `tests/unit/test_bfo_stubs.py`

**Approach:**
- Add triples for `BFO_PROCESS` in the same pattern as `BFO_OBJECT`: `OWL.Class`,
  `RDFS.label@en/de`, `SKOS.definition@en/de`, `RDFS.isDefinedBy BFO_ONTOLOGY_URI`.
- Add triples for `RO_HAS_OUTPUT` as `OWL.ObjectProperty` with `RDFS.label@en/de`,
  `SKOS.definition@en/de`, `RDFS.isDefinedBy` (point to the RO ontology URI).
- `add_bfo_stubs` remains one function; no second entry point needed.

**Test scenarios:**
- Happy path: after `add_bfo_stubs`, `(BFO_PROCESS, RDF.type, OWL.Class)` is in graph.
- Happy path: after `add_bfo_stubs`, `(BFO_PROCESS, RDFS.label, ...)` has both `@en` and `@de` literals.
- Happy path: `(RO_HAS_OUTPUT, RDF.type, OWL.ObjectProperty)` is in graph.
- Happy path: `(RO_HAS_OUTPUT, RDFS.label, ...)` has `@en` and `@de` literals.
- Edge case (idempotency): calling `add_bfo_stubs` twice produces same triple count.

**Verification:** Test file passes; `add_bfo_stubs` idempotency test still passes.

---

- [ ] **IU3: Replace `fermentationBase` with `producedBy`**

**Goal:** Remove `eucn:fermentationBase` (DatatypeProperty) from `discriminating_props.py`
and add `eucn:producedBy` as an `ObjectProperty` + `FunctionalProperty` with
`owl:inverseOf obo:RO_0002234` and `rdfs:range bfo:Process`.

**Requirements:** R3, R4

**Dependencies:** IU1, IU2

**Files:**
- Modify: `src/ontology/discriminating_props.py`
- Modify: `tests/unit/test_discriminating_props.py`

**Approach:**
- Add `_op(g, iri, label_en, label_de, def_en, def_de, range_=None)` helper that emits
  `OWL.ObjectProperty`, bilingual labels, and `RDFS.range`. (Mirrors `_dp()` but for
  object properties.)
- Call `_op()` for `eucn:producedBy` with `rdfs:range BFO_PROCESS`.
- After `_op()`, add: `(EUCN.producedBy, RDF.type, OWL.FunctionalProperty)` and
  `(EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT)`.
- Remove the `eucn:fermentationBase` block entirely (no `graph.remove()` needed — function
  is called fresh each build; no stale triple persists).
- Update `test_discriminating_props.py`:
  - Remove `EUCN.fermentationBase` from `PROPS` and `EXPECTED_RANGES`.
  - Add `EUCN.producedBy` to an `OBJ_PROPS` list.
  - Replace `test_all_five_are_datatype_properties` check to cover `eucn:producedBy` as `OWL.ObjectProperty`.
  - Rename/adapt `test_fermentation_base_is_functional` → `test_produced_by_is_functional`.
  - Add test: `(EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT) in g`.

**Test scenarios:**
- Happy path: `(EUCN.producedBy, RDF.type, OWL.ObjectProperty) in g`.
- Happy path: `(EUCN.producedBy, RDF.type, OWL.FunctionalProperty) in g`.
- Happy path: `(EUCN.producedBy, OWL.inverseOf, RO_HAS_OUTPUT) in g`.
- Happy path: `(EUCN.producedBy, RDFS.range, BFO_PROCESS) in g`.
- Happy path: `eucn:producedBy` has `RDFS.label@en`, `RDFS.label@de`, `SKOS.definition@en`, `SKOS.definition@de`.
- Happy path: `eucn:fermentationBase` is NOT in graph (property removed).
- Edge case: `test_other_props_not_functional` still passes for remaining datatype properties.
- Edge case (idempotency): calling `add_discriminating_props` twice produces same triple count.

**Verification:** All `test_discriminating_props.py` tests pass.

---

- [ ] **IU4: Ch22 process class vocabulary**

**Goal:** Declare 7 `bfo:Process` subclasses and 7 corresponding named singleton individuals
with pairwise `owl:differentFrom`, in a new `src/ontology/process_classes_ch22.py` module.
Wire into `tbox.py`.

**Requirements:** R5, R6, R7

**Dependencies:** IU1, IU2

**Files:**
- Create: `src/ontology/process_classes_ch22.py`
- Modify: `src/ontology/tbox.py`
- Create: `tests/unit/test_process_classes_ch22.py`

**Approach:**
- `_proc(g, iri, label_en, label_de, def_en, def_de)` helper: emits `OWL.Class`,
  `RDFS.subClassOf BFO_PROCESS`, bilingual labels/defs. Mirrors `_cls()` in `product_classes.py`.
- `_proc_singleton(g, class_iri, ind_iri, label_en, label_de)` helper: emits
  `OWL.NamedIndividual`, `rdf:type class_iri`.
- Declare the 7 process classes and 7 singletons (see table below).
- Declare pairwise `owl:differentFrom` between all 7 singletons using the existing
  `_disjoint_pairs` helper or a new `_different_pairs` helper (same combinatorics, different predicate).
- Add `from src.ontology.process_classes_ch22 import add_process_classes_ch22` to `tbox.py`
  and call it after `add_product_classes_ch22(g)` in `build_tbox`.

Process class table:

| Class | Singleton IRI | CN heading |
|-------|---------------|-----------|
| `eucn:MaltFermentation` | `eucn:malt-fermentation` | 2203 (Beer) |
| `eucn:GrapeFermentation` | `eucn:grape-fermentation` | 2204 (Wine) |
| `eucn:GrapeFlavouringProcess` | `eucn:grape-flavouring` | 2205 (Flavoured Wine) |
| `eucn:FruitFermentation` | `eucn:fruit-fermentation` | 2206 (Fermented Beverage) |
| `eucn:GrainDistillation` | `eucn:grain-distillation` | 2207/2208 (Spirit/EthylAlcohol ABox only) |
| `eucn:AceticFermentation` | `eucn:acetic-fermentation` | 2209 (Vinegar) |
| `eucn:SweetenedWaterProcess` | `eucn:sweetened-water-process` | 2202 (Non-Alco) |

**Test scenarios:**
- Happy path: each of the 7 process classes is in graph as `OWL.Class` subClassOf `BFO_PROCESS`.
- Happy path: each process class has bilingual `RDFS.label` and `SKOS.definition`.
- Happy path: each singleton is typed as `OWL.NamedIndividual` and its process class.
- Happy path: for each pair of singletons, `(s1, OWL.differentFrom, s2) in g`.
- Integration: after `build_tbox(g)`, all 7 classes and 7 singletons are present (tests that
  `add_process_classes_ch22` is wired into the tbox pipeline).
- Edge case (idempotency): calling `add_process_classes_ch22` twice produces same triple count.

**Verification:** `test_process_classes_ch22.py` passes; `build_tbox` integration test passes.

---

- [ ] **IU5: Equivalence axioms migration**

**Goal:** Replace the `fermentationBase` property reference and string literal values in
`equivalence_axioms.py` Phase 1 axioms with `producedBy` and the corresponding process
singleton IRIs. No structural changes to any helper function.

**Requirements:** R8, R9, R10

**Dependencies:** IU3, IU4

**Files:**
- Modify: `src/ontology/equivalence_axioms.py`
- Verify: `tests/unit/test_equivalence_axioms.py` (no changes expected)

**Approach:**
- Replace `ferm = EUCN.fermentationBase` with `produced_by = EUCN.producedBy` (or inline).
- Replace each `_has_value_restr(g, ferm, Literal("...", datatype=XSD.string), "key")` with
  `_has_value_restr(g, produced_by, EUCN["singleton-iri"], "key")`.
  - `"malt"` → `EUCN["malt-fermentation"]`
  - `"grape"` → `EUCN["grape-fermentation"]`  (Wine, SparklingWine, StillWine)
  - `"grape-flavoured"` → `EUCN["grape-flavouring"]`
  - `"fruit"` → `EUCN["fruit-fermentation"]`
  - `"acetic"` → `EUCN["acetic-fermentation"]`
  - `"sweetened-water"` → `EUCN["sweetened-water-process"]`
- Remove the import of `Literal` from the equivalence_axioms.py if it becomes unused (it may
  still be used for `isCarbonated` boolean literals in StillWine/SparklingWine).
- `XSD` import: check if still needed after removing string literals; keep if `xsd:boolean`
  or `xsd:decimal` literals remain.
- Spirit and EthylAlcohol (Phase 2): no `producedBy` conditions; only ABV + graph-derived
  complements. `_neg_hasvalue_from_disjoint_equiv` picks up `hasValue eucn:malt-fermentation`
  etc. from Phase 1 sibling axioms — no code change.

**Test scenarios:**
- Happy path: `test_beer_equivalentclass_present` still passes.
- Happy path: `test_all_product_classes_have_equiv` still passes.
- Happy path: Beer's equivalentClass intersectionOf contains a `hasValue eucn:malt-fermentation` restriction.
- Happy path: Spirit's equivalentClass contains `complementOf [hasValue eucn:malt-fermentation]` (graph-derived).
- Happy path: `test_spirit_neg_hasvalue_covers_all_disjoint_sibling_conditions` still passes.
- Happy path: `test_ethyl_neg_hasvalue_covers_all_disjoint_sibling_conditions` still passes.
- Happy path: No `Literal("malt", …)` etc. in the graph (string sentinel gone).
- Edge case (idempotency): `test_idempotent` still passes (same triple count both calls).

**Verification:** All `test_equivalence_axioms.py` tests pass without modification.

---

- [ ] **IU6: ABox fixtures and acceptance tests**

**Goal:** Replace `eucn:fermentationBase "..."^^xsd:string` with `eucn:producedBy eucn:xxx`
in `beverages_demo.ttl` and verify all acceptance tests pass with native Konclude.

**Requirements:** R11, R12, R13

**Dependencies:** IU4, IU5

**Files:**
- Modify: `tests/fixtures/beverages_demo.ttl`
- Verify: `tests/acceptance/test_classification_demo.py` (no changes expected)

**Approach:**
- Replace `eucn:fermentationBase  "malt"^^xsd:string` → `eucn:producedBy  eucn:malt-fermentation`
- Replace `"grape"` → `eucn:grape-fermentation`
- Replace `"grape-flavoured"` → `eucn:grape-flavouring`
- Replace `"fruit"` → `eucn:fruit-fermentation`
- Replace `"acetic"` → `eucn:acetic-fermentation`
- Replace `"sweetened-water"` → `eucn:sweetened-water-process`
- `demo:whisky-12y` and `demo:grain-spirit-96` both get `eucn:producedBy eucn:grain-distillation`.
- `demo:still-water` had no `fermentationBase` and needs no `producedBy` (Water discriminated by ABV only).
- Update the `@prefix` block: remove `xsd:` if only used for the fermentationBase literals;
  keep if `xsd:decimal` and `xsd:boolean` are still used.
- Run native Konclude realization to confirm all 10 individuals classify correctly.

**Test scenarios:**
- Happy path: `test_champagne_inferred_as_sparkling_wine` passes.
- Happy path: `test_bordeaux_inferred_as_still_wine` passes.
- Happy path: `test_lager_inferred_as_beer` passes.
- Happy path: `test_whisky_inferred_as_spirit` passes.
- Happy path: `test_grain_spirit_inferred_as_ethyl_alcohol` passes.
- Happy path: `test_still_water_inferred_as_water` passes.
- Happy path: `test_all_demo_individuals_inferred_as_beverage` passes.
- Happy path: `test_no_individual_classified_as_nothing` passes (ontology consistent).
- Integration: `test_expected_types_are_superset_of_inferred` passes for all 10 individuals.

**Verification:** All `test_classification_demo.py` tests pass with native Konclude.

---

- [ ] **IU7: Pattern documentation**

**Goal:** Document the canonical OWL 2 DL classification pattern in `docs/ontology-patterns.md`
and add an "Ontology Architecture" section to `README.md`.

**Requirements:** R14, R15

**Dependencies:** IU1–IU6 complete (document the implemented pattern, not a planned one)

**Files:**
- Create: `docs/ontology-patterns.md`
- Modify: `README.md`

**Approach:**
- `docs/ontology-patterns.md` sections:
  1. **Production-process restriction pattern** — Turtle example of a process class, singleton,
     `producedBy FunctionalProperty`, hasValue axiom, and ABox assertion.
  2. **Graph-derived complement restriction** — how `_neg_hasvalue_from_disjoint_equiv` derives
     NOT conditions; two-phase structure; when Phase 2 is needed.
  3. **OWA and world-closure** — why FunctionalProperty + differentFrom is required; why
     `someValuesFrom` + anonymous instances would not classify under OWA.
  4. **Mixed products** — explicit ABox `rdf:type` assertion required; FunctionalProperty
     prevents multi-valued inference.
  5. **Adding a new chapter** — checklist: declare process classes, singletons, differentFrom;
     add Phase 1 axioms; add Phase 2 classes; update tbox pipeline call.
- `README.md` "Ontology Architecture" section: 3–4 sentence summary + brief Turtle snippet
  + pointer to `docs/ontology-patterns.md`.

**Test scenarios:**
- Test expectation: none — documentation; correctness is human-reviewed.

**Verification:** `docs/ontology-patterns.md` exists and contains all five sections;
README contains the new section.

---

## System-Wide Impact

- **Interaction graph:** `build_tbox` adds a new call `add_process_classes_ch22(g)`. All
  downstream pipeline steps (Konclude check, classify, SPARQL acceptance) receive a graph
  with ~100 additional triples (7 classes × ~6 triples + 7 singletons × ~3 triples + 21 differentFrom pairs).
- **Error propagation:** Idempotency contract unchanged — all builder functions use `graph.add()`;
  no new failure modes.
- **State lifecycle risks:** String literals in `beverages_demo.ttl` must be updated before
  acceptance tests run; if IU5 lands without IU6, tests will fail until IU6 is complete.
  Keep IU5 and IU6 in the same commit.
- **API surface parity:** No public API changes — all builder functions keep the same signature.
  `eucn:fermentationBase` will no longer appear in the published TTL; `eucn:producedBy` replaces it.
- **Integration coverage:** Full Konclude realization run (IU6 verification) proves the axiom
  chain across all layers; unit tests alone do not prove ABox inference.
- **Unchanged invariants:** All 10 existing equivalentClass axioms remain structurally identical;
  only the property IRI and value nodes change. Phase 2 complement derivation unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Missing `owl:differentFrom` between singletons breaks FunctionalProperty exclusion | IU4 declares pairwise differentFrom for all 21 pairs; IU6 Konclude realization test catches any silent failure |
| WASM consistency check fails with ObjectProperty FunctionalProperty | Existing fermentationBase FP already passes WASM; the CLI's FP strip is generic. If new FP causes hang, check rdf-reasoner-konclude for a version update |
| `test_tbox.py` bilingual label invariant fails for new process classes/property | Each new class and property must have 4 metadata triples; follow `_cls()` pattern exactly |
| Spirit/EthylAlcohol individuals mis-classified after migration | IU6 acceptance test covers both whisky-12y (Spirit) and grain-spirit-96 (EthylAlcohol) via native Konclude; differentFrom ensures grain-distillation ≠ malt-fermentation |
| `XSD` / `Literal` import left dangling in equivalence_axioms.py | Verify remaining usages (isCarbonated boolean, ABV decimal) before removing import |

## Documentation / Operational Notes

- After this work lands, run `python3 -m src.pipeline --chapter 22 --force --skip-fetch --skip-scrape`
  to rebuild the published ontology artifacts with the new `producedBy` property.
- After pipeline rebuild, commit the updated `data/ontology/eucn-ch22-*.ttl/trig`.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-06-08-004-feat-bfo-process-class-architecture-requirements.md](docs/brainstorms/2026-06-08-004-feat-bfo-process-class-architecture-requirements.md)
- Related code: `src/ontology/equivalence_axioms.py`, `src/ontology/product_classes.py`
- Institutional learnings: `rdf-reasoner-konclude/docs/solutions/capability-gaps/`
- BFO 2020: `http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl`
- OBO RO: `http://purl.obolibrary.org/obo/ro.owl`
