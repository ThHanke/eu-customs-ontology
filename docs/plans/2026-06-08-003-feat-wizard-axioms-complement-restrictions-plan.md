---
title: "feat: owl:complementOf restrictions for boolean Nein paths in wizard_axioms.py"
type: feat
status: active
date: 2026-06-08
origin: docs/plans/2026-06-08-002-feat-owl-product-classes-bfo-alignment-plan.md
---

# OWL complementOf Restrictions for Boolean "Nein" Wizard Paths

## Overview

`wizard_axioms.py` currently emits `owl:hasValue false` for boolean "Nein" answers. This is
logically weak: `hasValue false` matches only an individual that has the property asserted
as false, whereas the correct semantics for "not X" in OWL 2 DL is:

```
owl:complementOf [owl:Restriction owl:onProperty P owl:hasValue true]
```

The practical consequence is an OWL inconsistency: Spirit's ABV range (0.5–80 % vol)
overlaps with Beer's ABV range for any malt-fermented individual. The wizard path to Spirit
passes through "Ist es Bier? → Nein" — if that Nein emitted a complement restriction rather
than `hasValue false`, the Spirit axiom would automatically include `NOT (ferm = "malt")`,
making Beer and Spirit naturally non-overlapping by construction.

After this change: Beer, Spirit, EthylAlcohol, and Water individuals can be added to the
demo fixture and will be correctly realised by Konclude without any inconsistency.

## Problem Frame

The root cause is in `_add_restriction_triples()` at [src/ontology/wizard_axioms.py:202](src/ontology/wizard_axioms.py#L202):

```python
elif tier == "boolean":
    value = RLiteral(is_yes, datatype=XSD.boolean)
    g.add((restr, RDF.type, OWL.Restriction))
    g.add((restr, OWL.onProperty, prop))
    g.add((restr, OWL.hasValue, value))
```

For "Nein", `is_yes=False`, producing `hasValue false`. Correct encoding is:

```
<inner>  rdf:type        owl:Restriction ;
         owl:onProperty  P ;
         owl:hasValue    "true"^^xsd:boolean .

<outer>  rdf:type        owl:Class ;
         owl:complementOf <inner> .
```

The outer BNode replaces the current `restr` BNode in the intersection list.

## Requirements Trace

- R1. Boolean "Nein" paths emit `owl:complementOf [Restriction hasValue true]` rather than
  `hasValue false`.
- R2. Boolean "Ja" paths continue to emit `hasValue true` unchanged.
- R3. BNode keys remain SHA-256-derived and deterministic; a new key scheme for complement
  wrappers must not collide with existing quantitative/fallback keys.
- R4. `_classify_question()` returns the outer complement BNode for Nein; the inner positive
  restriction BNode is created internally by `_add_restriction_triples()`.
- R5. `equivalence_axioms.py` Spirit axiom gains explicit NOT-ferm complement conditions
  (`NOT ferm="malt"`, `NOT ferm="grape"`) alongside the existing ABV range restrictions, so
  the curated class axiom matches the wizard-derived CN-code axiom semantics.
- R6. EthylAlcohol axiom gains `NOT ferm="malt"`, `NOT ferm="grape"` for the same reason.
- R7. Demo fixture `beverages_demo.ttl` gains Beer, Spirit, EthylAlcohol, Water individuals.
- R8. Acceptance tests verify all six new individuals are classified into the correct class.
- R9. All 157 existing passing tests continue to pass.
- R10. README demo section updated to show Beer/Spirit individuals and their inferred types.

## Scope Boundaries

- Only boolean tier is changed. Quantitative `_FLIP_FACET` logic is untouched.
- Fallback tier (non-boolean, non-quantitative) is untouched.
- Only Chapter 22 equivalence axioms are updated. Water axiom (ABV ≤ 0) has no
  fermentation-base complement needed; keep as-is.
- No changes to Konclude integration, pipeline orchestration, or CI.

## Design Decisions

### D1: Complement BNode architecture

Two BNodes per boolean Nein restriction:

| BNode | Type | Key pattern |
|-------|------|-------------|
| inner positive | `owl:Restriction` + `hasValue true` | `restr:bool:{prop}:True:{cn_code}` |
| outer complement | `owl:Class` + `complementOf inner` | `restr:bool:compl:{prop}:{cn_code}` |

The **outer** BNode is what goes into the intersection list. The inner BNode is a private
implementation detail of `_add_restriction_triples()`.

**Rationale:** Konclude requires the intersection members to be typed as `owl:Class` or
`owl:Restriction`. The complement wrapper is `a owl:Class`, which satisfies this.
`owl:Restriction` is a subclass of `owl:Class` in OWL 2 so existing positive restrictions
(for "Ja") already work.

### D2: `_classify_question()` return BNode identity

`_classify_question()` returns the **outer** complement BNode for Nein. This is what the
caller adds to the `restrictions` list. `_add_restriction_triples()` receives this outer
BNode and creates the inner one internally.

`_add_restriction_triples()` signature does not change. The `is_yes` flag derived from
`answer_text` inside that function controls whether to emit a plain restriction or a
complement wrapper. No new parameters needed.

### D3: `_classify_question()` BNode key for Nein

Current boolean Nein key: `restr:bool:{prop}:False:{cn_code}`
New outer key:             `restr:bool:compl:{prop}:{cn_code}`
New inner key:             `restr:bool:{prop}:True:{cn_code}` (same as Ja key for this prop)

This means the inner positive restriction for Spirit's "not malt" Nein path reuses the same
BNode as a "Ja" answer to the same question in a different path — both share `hasValue true`.
This is correct: the content is identical, and BNode sharing is harmless in OWL 2 DL.

### D4: `equivalence_axioms.py` complement helper

Add `_complement_has_value_restr(g, prop, value, key)` alongside the existing
`_has_value_restr()`. It creates the inner restriction then wraps it in an outer BNode typed
`owl:Class` with `owl:complementOf`. Returns the outer BNode for use in `_equiv()`.

Spirit axiom becomes:
```
intersectionOf(
  ABV > 0.5,
  ABV < 80,
  NOT (ferm = "malt"),
  NOT (ferm = "grape"),
)
```

EthylAlcohol axiom becomes:
```
intersectionOf(
  ABV ≥ 80,
  NOT (ferm = "malt"),
  NOT (ferm = "grape"),
)
```

Water axiom stays:
```
intersectionOf(ABV ≤ 0)
```

Beer and Wine axioms stay unchanged (they are the positive classes, not the complement side).

### D5: Demo individuals

| Individual | Properties | Expected class |
|-----------|------------|---------------|
| `demo:czech-lager` | `ferm="malt"`, `abv=5.0` | `eucn:Beer` |
| `demo:whisky-12y` | `abv=43.0`, NOT(malt), NOT(grape) | `eucn:Spirit` |
| `demo:grain-spirit-96` | `abv=96.0`, NOT(malt), NOT(grape) | `eucn:EthylAlcohol` |
| `demo:still-water` | `abv=0.0` | `eucn:Water` |

For Spirit and EthylAlcohol: since the complement conditions fire on `NOT (ferm = "malt")`
and `NOT (ferm = "grape")`, the individuals must assert some other `fermentationBase` value
that is distinct from "malt" and "grape". Using `ferm="grain"` satisfies this in CWA-free
OWL (open world — complement means the individual does not assert malt/grape via hasValue, OR
asserts something else). In practice we assert `ferm="grain"` so the individual is
unambiguously outside the Beer/Wine equivalentClass conditions.

Wait — open world assumption matters here. `owl:complementOf [hasValue true]` fires if
the individual is **not** in the class `∃P.{true}`, which means either the property is
absent or has a different value. So asserting `ferm="grain"` (a value other than "malt")
is the safest approach — it positively excludes "malt" and "grape" under CWA-friendly
reasoning.

### D6: Coverage reporting

No change to `WizardAxiomCoverage` model fields. Complement restrictions count as boolean
covered (`n_bool` increment). `covered_boolean` already reflects whether the question was
structurally handled, not the specific direction of the answer.

## Implementation Units

### IU1: `src/ontology/wizard_axioms.py`

**Files:** `src/ontology/wizard_axioms.py`
**Tests:** `tests/unit/test_wizard_axioms.py`

Changes:

1. In `_classify_question()`, boolean Nein branch: change BNode key to
   `f"restr:bool:compl:{prop}:{cn_code}"` and return that outer BNode.

2. In `_add_restriction_triples()`, boolean branch: when `is_yes=False`, create two BNodes:
   - inner: `_bnode(f"restr:bool:{prop}:True:{cn_code}")` typed `owl:Restriction` +
     `hasValue true`.
   - outer (the `restr` arg): typed `owl:Class` + `owl:complementOf inner`.
   When `is_yes=True`: unchanged (plain `hasValue true` restriction).

   The `restr_key` passed in must be the outer key. Derive inner key as
   `restr_key.replace("compl:", "")` or pass it explicitly.

   Cleaner approach: derive inner key inside `_add_restriction_triples()` from outer key via
   a private convention — e.g., replace `"compl:"` prefix with empty. Or just pass
   `inner_key = f"restr:bool:{prop}:True:{cn_code}"` as a separate arg. Prefer the
   explicit arg to avoid fragile string manipulation.

   Recommended signature change:
   ```python
   def _add_restriction_triples(
       g, restr, prop, tier, answer_text,
       threshold, facet_name, restr_key,
       inner_restr_key: str | None = None,  # only for boolean Nein complement
   ) -> None:
   ```

3. Update the call site in `transform()` to pass `inner_restr_key` when constructing the
   boolean Nein complement restriction.

**Test scenarios** (update existing + add):

- `test_boolean_nein_hasvalue_false` → rename to `test_boolean_nein_complement_restriction`.
  Assert: (a) no `owl:hasValue false` triple exists; (b) a BNode with `owl:complementOf`
  exists pointing to an inner restriction; (c) inner restriction has `owl:hasValue true`.
- `test_boolean_ja_hasvalue_true`: unchanged — still expects `owl:hasValue true`.
- `test_boolean_nein_complement_is_owl_class`: assert outer BNode has `rdf:type owl:Class`.
- `test_boolean_nein_inner_is_owl_restriction`: assert inner BNode has
  `rdf:type owl:Restriction`.
- `test_multi_step_nein_complement_in_intersection`: assert complement BNode appears in
  `owl:intersectionOf` list.
- Idempotency test: still passes (complement BNodes are SHA-derived, stable).

### IU2: `src/ontology/equivalence_axioms.py`

**Files:** `src/ontology/equivalence_axioms.py`
**Tests:** `tests/unit/test_equivalence_axioms.py`, `tests/integration/test_equivalence_axioms_integration.py`

Changes:

1. Add `_complement_has_value_restr(g, prop, value, key) -> BNode`:
   - Creates inner restriction BNode (typed `owl:Restriction`, `hasValue value`).
   - Creates outer BNode (typed `owl:Class`, `owl:complementOf inner`).
   - Returns outer BNode.

2. Spirit axiom: add two complement restrictions — `NOT ferm="malt"` and `NOT ferm="grape"`.
   Remove the NOTE comment about deferral.

3. EthylAlcohol axiom: add complement restrictions — `NOT ferm="malt"` and
   `NOT ferm="grape"`.

**Test scenarios:**

- `test_spirit_has_complement_not_malt`: assert Spirit's equivalentClass intersection
  contains a complement restriction where inner has `hasValue "malt"^^xsd:string`.
- `test_spirit_has_complement_not_grape`: same for "grape".
- `test_ethyl_has_complement_not_malt`, `test_ethyl_has_complement_not_grape`: same pattern.
- `test_complement_bnode_is_owl_class`: outer complement BNode has `rdf:type owl:Class`.
- `test_complement_inner_is_owl_restriction`: inner BNode has `rdf:type owl:Restriction`.
- Existing water/beer/wine/sparkling/still/flavoured/fermented/vinegar/nonalco axiom tests:
  unchanged — these do not involve complement restrictions.

### IU3: `tests/fixtures/beverages_demo.ttl`

**Files:** `tests/fixtures/beverages_demo.ttl`
**Tests:** `tests/acceptance/test_classification_demo.py`

Add four individuals (see D5):

```turtle
# CN 2203 — Beer (eucn:Beer)
demo:czech-lager a owl:NamedIndividual ;
    eucn:fermentationBase       "malt"^^xsd:string ;
    eucn:alcoholByVolumePercent "5.0"^^xsd:decimal .

# CN 2208 — Spirit (eucn:Spirit)
demo:whisky-12y a owl:NamedIndividual ;
    eucn:fermentationBase       "grain"^^xsd:string ;
    eucn:alcoholByVolumePercent "43.0"^^xsd:decimal .

# CN 2207 — Ethyl alcohol (eucn:EthylAlcohol)
demo:grain-spirit-96 a owl:NamedIndividual ;
    eucn:fermentationBase       "grain"^^xsd:string ;
    eucn:alcoholByVolumePercent "96.0"^^xsd:decimal .

# CN 2201 — Water (eucn:Water)
demo:still-water a owl:NamedIndividual ;
    eucn:alcoholByVolumePercent "0.0"^^xsd:decimal .
```

Update the existing header comment to remove the "awaiting wizard_axioms.py enhancement"
note.

### IU4: `tests/acceptance/test_classification_demo.py`

**Files:** `tests/acceptance/test_classification_demo.py`

Add four entries to `EXPECTED`:

```python
"https://w3id.org/eucn/demo/czech-lager": {
    "https://w3id.org/eucn/Beer",
    "https://w3id.org/eucn/Beverage",
},
"https://w3id.org/eucn/demo/whisky-12y": {
    "https://w3id.org/eucn/Spirit",
    "https://w3id.org/eucn/Beverage",
},
"https://w3id.org/eucn/demo/grain-spirit-96": {
    "https://w3id.org/eucn/EthylAlcohol",
    "https://w3id.org/eucn/Beverage",
},
"https://w3id.org/eucn/demo/still-water": {
    "https://w3id.org/eucn/Water",
    "https://w3id.org/eucn/Beverage",
},
```

Add per-individual test methods mirroring the existing six:
- `test_lager_inferred_as_beer`
- `test_whisky_inferred_as_spirit`
- `test_grain_spirit_inferred_as_ethyl_alcohol`
- `test_still_water_inferred_as_water`

The `test_expected_types_are_superset_of_inferred` and
`test_all_demo_individuals_inferred_as_beverage` tests cover the new individuals
automatically because they iterate `EXPECTED`.

The `test_no_individual_classified_as_nothing` test is the critical regression guard —
it must pass with the new individuals included.

### IU5: `README.md`

**Files:** `README.md`

Update "Product Classification Demo":
1. Add `demo:czech-lager` and `demo:whisky-12y` to the "Describe a product" Turtle block.
2. Add rows to "What the reasoner infers" table for all four new individuals.
3. In "Current limitations": remove the Beer/Spirit overlap paragraph; replace with one
   sentence noting that complement restrictions eliminate ABV overlap by construction.
4. Show the Spirit equivalentClass axiom (with complement conditions) alongside the
   SparklingWine axiom in "How it works".

## Sequencing

```
IU1 (wizard_axioms.py — algorithm fix)
  └─▶ IU2 (equivalence_axioms.py — complement conditions)
        └─▶ IU3 (beverages_demo.ttl — new individuals)
              └─▶ IU4 (acceptance tests — new assertions)
                    └─▶ IU5 (README update)
```

IU1 must land before IU2 because `equivalence_axioms.py` uses the same OWL complement
pattern; having the wizard emit it confirms the pattern works end-to-end before curating it
manually.

IU3 and IU4 are gated on IU1+IU2 landing and a passing Konclude realization run on the
new individuals.

## Test Scenarios Summary

| Unit | Key scenario | Pass condition |
|------|-------------|----------------|
| IU1 | Boolean Nein → complement | `owl:complementOf` triple present, no `hasValue false` |
| IU1 | Boolean Ja → hasValue true | `owl:hasValue true` triple present, no `complementOf` |
| IU1 | Multi-step with Nein → complement in intersection | complement BNode in `intersectionOf` list |
| IU1 | Idempotency | Same triples both calls |
| IU2 | Spirit axiom has NOT-malt, NOT-grape | Two `owl:complementOf` BNodes in intersection |
| IU2 | EthylAlcohol axiom has NOT-malt, NOT-grape | Same |
| IU3+IU4 | czech-lager → eucn:Beer | Konclude realization asserts Beer |
| IU3+IU4 | whisky-12y → eucn:Spirit | Konclude realization asserts Spirit |
| IU3+IU4 | grain-spirit-96 → eucn:EthylAlcohol | Konclude realization asserts EthylAlcohol |
| IU3+IU4 | still-water → eucn:Water | Konclude realization asserts Water |
| IU3+IU4 | no owl:Nothing | None of the 10 individuals in owl:Nothing |
| IU3+IU4 | all → eucn:Beverage | All 10 individuals inferred as Beverage |

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Open-world semantics: Spirit individual with no `ferm` property might still match malt-based Beer if OWA applies | Assert an explicit `ferm` value that is neither "malt" nor "grape" (e.g. "grain") — this positively excludes the alternative under hasValue semantics |
| BNode key collision: `compl:` prefix collides with another tier | All existing keys use `restr:bool:`, `restr:quant:`, `restr:fallback:` — the new `restr:bool:compl:` prefix is distinct |
| Konclude complement support | Assume full OWL 2 DL parity (native Konclude v0.7.0-1138 is a complete OWL 2 DL reasoner) |
| EthylAlcohol + Spirit both match `abv > 0.5` | EthylAlcohol has `abv ≥ 80` which excludes Spirit's `abv < 80` by disjoint facets; no complement needed between them |
| Beer disjoint from Wine but ferm="malt" vs ferm="grape" already different | `owl:disjointWith` declarations in product_classes.py reinforce non-overlap at class level |

## Deferred

- Updating `WizardAxiomCoverage` with a separate `covered_complement` counter (current
  `covered_boolean` count includes both Ja and Nein; separating is a cosmetic enhancement).
- ABV-based discrimination for Beer/Spirit/Water at the wizard-derived CN code level (the
  wizard uses numeric thresholds; those already generate quantitative restrictions via the
  existing `_FLIP_FACET` logic — no new work needed for quantitative Nein paths).
- Testing WASM Konclude realization: defer until rdf-reasoner-konclude ships a WASM release
  with `realization` mode. Note in memory: test on new WASM release when available.
