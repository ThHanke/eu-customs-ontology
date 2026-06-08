---
date: 2026-06-08
topic: bfo-process-class-architecture
---

# BFO Process Class Architecture for CN Discriminating Axioms

## Problem Frame

The current Ch22 ontology uses `eucn:fermentationBase` (a `DatatypeProperty` with string
literals: `"malt"`, `"grape"`, etc.) to discriminate between product classes. This has two
weaknesses as we expand beyond Ch22:

1. **Non-BFO-aligned.** A beverage is the *output of a production process*, not a carrier of
   a string attribute. All CN chapters share this production-process structure, and string
   literals on a datatype property do not model it.

2. **No shared vocabulary.** String literals are opaque — there is no shared process class
   hierarchy, no disjointness structure between process types, and no connection to
   upper-ontology process concepts.

The fix: replace `fermentationBase` with a `eucn:producedBy` object property whose values are
named process singleton individuals typed as `bfo:Process` subclasses. Ch22 becomes the
reference implementation for all future chapters.

**OWL 2 DL world-closure note.** Complement-based discrimination (`NOT producedBy some
ProcessA`) requires world-closure on the discriminating property. Under OWA, no OWL 2 DL
reasoner can prove a negative without closure — this is not a reasoner limitation, it is
fundamental OWL semantics. The chosen closure mechanism is `owl:FunctionalProperty` on
`eucn:producedBy` combined with named singleton process individuals (Unique Name Assumption
on named individuals proves `eucn:MALT ≠ eucn:GRAIN_DIST`). Mixed products (requiring two
simultaneous production values) cannot be classified via inference under this pattern; they
receive explicit `rdf:type` assertions in the ABox.

## Requirements

**Core property and BFO alignment**

- R1. Declare `bfo:Process` (BFO_0000015) stub in `src/ontology/bfo_stubs.py`, parallel to
  the existing `bfo:Object` (BFO_0000030) stub.
- R2. Declare `obo:RO_0002234` (`has output`) stub in `src/ontology/bfo_stubs.py` as an
  `owl:ObjectProperty`.
- R3. Declare `eucn:producedBy` as an `owl:ObjectProperty` and `owl:FunctionalProperty`
  with `owl:inverseOf obo:RO_0002234`, `rdfs:range bfo:Process`, and EN/DE labels and
  `skos:definition`. This property replaces `eucn:fermentationBase`.
- R4. Remove `eucn:fermentationBase` from `src/ontology/discriminating_props.py`.

**Process class vocabulary (Ch22)**

- R5. Declare Ch22 process singleton individuals and their classes in `src/ontology/product_classes.py`
  (or a new parallel `src/ontology/process_classes_ch22.py`). Each class is a named
  `owl:Class` subclass of `bfo:Process` with EN/DE labels and `skos:definition`. Each
  singleton is a `owl:NamedIndividual` typed as its process class. Required for Ch22:

  | Class IRI | Singleton IRI | Discriminates |
  |---|---|---|
  | `eucn:MaltFermentation` | `eucn:malt-fermentation` | Beer (CN 2203) |
  | `eucn:GrapeFermentation` | `eucn:grape-fermentation` | Wine (CN 2204) |
  | `eucn:GrapeFlavouringProcess` | `eucn:grape-flavouring` | Flavoured Wine (CN 2205) |
  | `eucn:FruitFermentation` | `eucn:fruit-fermentation` | Fermented Beverage (CN 2206) |
  | `eucn:GrainDistillation` | `eucn:grain-distillation` | Spirit (CN 2208), EthylAlcohol (CN 2207) |
  | `eucn:AceticFermentation` | `eucn:acetic-fermentation` | Vinegar (CN 2209) |
  | `eucn:SweetenedWaterProcess` | `eucn:sweetened-water-process` | Non-Alco Bev (CN 2202) |

- R6. All Ch22 process singleton classes are declared pairwise `owl:disjointWith` each other.
  `GrainDistillation` is disjoint from `MaltFermentation` — for CN classification purposes,
  spirits and beer are discriminated at the process-type level even though real-world whisky
  production involves a malt fermentation step. The singleton model uses one process type per
  CN heading, not a full multi-step process chain.
- R7. A `_proc()` helper handles the process class declaration boilerplate (label, definition,
  `rdfs:subClassOf bfo:Process`), and a `_proc_singleton()` helper declares the named
  individual, parallel to the existing `_cls()` helper.

**Equivalence axioms (Ch22 migration)**

- R8. Replace all `_has_value_restr(g, ferm, Literal("..."), ...)` calls in
  `src/ontology/equivalence_axioms.py` with `_has_value_restr(g, produced_by, eucn.malt_fermentation, ...)`
  — `owl:hasValue` now takes a named process singleton IRI as the value (object property).
  The `_has_value_restr` builder is unchanged; only the property and value arguments change.
- R9. The `_neg_hasvalue_from_disjoint_equiv` function is **unchanged** in structure — it
  already walks `owl:hasValue` restrictions generically. After migration the values it reads
  are process singleton IRIs instead of string literals; the complement pattern
  `NOT(producedBy hasValue eucn:malt-fermentation)` is structurally identical to the current
  `NOT(fermentationBase hasValue "malt")`. No new complement derivation function is needed.
- R10. `eucn:fermentationBase` is removed from all `equivalence_axioms.py` calls.

**ABox and demo individuals**

- R11. Update `tests/fixtures/beverages_demo.ttl`: replace
  `eucn:fermentationBase "..."^^xsd:string` with `eucn:producedBy eucn:xxx-process` for all
  individuals.
- R12. All existing acceptance tests in `tests/acceptance/test_classification_demo.py` must
  continue to pass after the migration with no relaxation of assertions.

**Mixed product handling**

- R13. Mixed products (two simultaneous production processes) cannot be classified via
  inference under `owl:FunctionalProperty`. When a mixed product individual is required,
  it receives an explicit `rdf:type` assertion in the ABox. No mixed product class is added
  for Ch22; this requirement documents the policy for future chapters.

**Pattern documentation**

- R14. Add `docs/ontology-patterns.md` documenting the canonical OWL 2 DL classification
  pattern used across all CN chapters:
  - **Production-process restriction** (`hasValue` singleton): how to express "produced by
    MaltFermentation", why `owl:FunctionalProperty` is required, and the ABox counterpart.
  - **Graph-derived complement restriction**: how `_neg_hasvalue_from_disjoint_equiv` derives
    `NOT(producedBy hasValue eucn:malt-fermentation)` generically; when Phase 2 is needed.
  - **OWA note**: why `someValuesFrom` anonymous instances do not work without closure, and
    why `FunctionalProperty` + named singletons is the chosen solution.
  - **Mixed products**: why they require explicit ABox type assertions.
- R15. Add an "Ontology Architecture" section to `README.md` summarising the pattern with
  concise Turtle examples and a pointer to `docs/ontology-patterns.md`.

## Success Criteria

- All existing tests continue to pass after migration.
- Konclude correctly classifies all ten `beverages_demo.ttl` individuals (Beer, Spirit,
  EthylAlcohol, Water, Wine, SparklingWine, StillWine, FlavouredWine, FermentedBeverage,
  Vinegar) using the new `eucn:producedBy` property.
- `eucn:fermentationBase` does not appear in the built ontology TTL.
- `docs/ontology-patterns.md` is complete enough that a future chapter author can add a new
  chapter's process classes and equivalence axioms without reading the source code.

## Scope Boundaries

- Ch22 is the only chapter migrated in this work; subsequent chapters use the new pattern
  from the start.
- Full import of the RO/BFO ontology files is not in scope; stubs for the used IRIs suffice.
- No mixed product CN class is added for Ch22.
- The wizard axioms (`wizard_axioms.py`) boolean complement restrictions are out of scope —
  they address a different set of properties (`eucn:isCarbonated` etc.) and do not use
  `fermentationBase`.

## Key Decisions

- **Named process singletons + `owl:FunctionalProperty`:** OWA requires world-closure for
  complement-based classification. Named individuals + FunctionalProperty is the only OWL 2
  DL pattern that proves `NOT(producedBy X)` without explicit negative assertions.
  `someValuesFrom` + anonymous instances was rejected because no OWL 2 DL reasoner can
  classify under OWA without closure, regardless of reasoner capability.
- **`_neg_hasvalue_from_disjoint_equiv` retained unchanged:** Switching to named individual
  singleton values means the complement derivation function still walks `owl:hasValue`
  restrictions — no structural change needed. The graph-derived two-phase pattern carries
  forward as-is.
- **`eucn:producedBy owl:inverseOf obo:RO_0002234`:** Full BFO/RO alignment via `inverseOf`.
  OWL entails both directions. Using the named inverse `eucn:producedBy` in axioms (rather
  than explicit inverse-role syntax) is equivalent and simpler for reasoners.
- **`GrainDistillation owl:disjointWith MaltFermentation`:** Spirits and beer use disjoint
  process types even though real-world whisky involves malt fermentation. The singleton model
  captures CN-heading-level discrimination, not a full multi-step production chain.
- **Mixed products use explicit ABox type assertion:** Accepted limitation of the
  FunctionalProperty approach. Mixed products are edge-cases in CN and sufficiently rare to
  handle manually.

## Dependencies / Assumptions

- `obo:RO_0002234` is the correct IRI for `has output` in the Relations Ontology.
  To be verified during planning.
- Named individuals with distinct IRIs are treated as `owl:differentFrom` each other
  (Unique Name Assumption) by all OWL 2 DL reasoners — required for FunctionalProperty
  exclusion to work.

## Outstanding Questions

### Resolve Before Planning

- None.

### Deferred to Planning

- **[Affects R5][Technical]** Whether process classes and singletons live in
  `product_classes.py` (co-location with product classes) or a separate
  `process_classes_ch22.py`. Choose based on file size and readability.
- **[Affects R3][Needs research]** Confirm `obo:RO_0002234` is the current canonical IRI
  for `has output` in the RO release used by the project.

## Next Steps

-> `/ce-plan`

---

```
OWL 2 DL Production-Process Pattern (all CN chapters)

  TBox — process vocabulary
  ┌────────────────────────────────────────────────────────────────────────┐
  │ eucn:MaltFermentation  rdfs:subClassOf  bfo:Process                   │
  │ eucn:GrainDistillation rdfs:subClassOf  bfo:Process                   │
  │ eucn:MaltFermentation  owl:disjointWith eucn:GrainDistillation        │
  │ eucn:malt-fermentation  rdf:type  eucn:MaltFermentation               │  ← singleton
  │ eucn:grain-distillation rdf:type  eucn:GrainDistillation              │  ← singleton
  └────────────────────────────────────────────────────────────────────────┘

  TBox — equivalence axioms
  ┌────────────────────────────────────────────────────────────────────────┐
  │ eucn:Beer owl:equivalentClass [                                        │
  │   owl:intersectionOf (                                                 │
  │     [onProperty producedBy ; hasValue eucn:malt-fermentation]         │
  │     [ABV > 0.5%]                                                       │
  │   )                                                                    │
  │ ]                                                                      │
  │                                                                        │
  │ eucn:Spirit owl:equivalentClass [                                      │
  │   owl:intersectionOf (                                                 │
  │     [ABV > 0.5%] [ABV < 80%]                                          │
  │     [complementOf [hasValue eucn:malt-fermentation]]  ← graph-derived │
  │     [complementOf [hasValue eucn:grape-fermentation]] ← graph-derived │
  │     ...                                                                │
  │   )                                                                    │
  │ ]                                                                      │
  └────────────────────────────────────────────────────────────────────────┘

  ABox
  ┌──────────────────────────────────────────────────────────────────────┐
  │ demo:czech-lager  eucn:producedBy  eucn:malt-fermentation .          │
  │ demo:whisky-12y   eucn:producedBy  eucn:grain-distillation .         │
  └──────────────────────────────────────────────────────────────────────┘

  eucn:producedBy  owl:inverseOf  obo:RO_0002234 (has output, Relations Ontology)
  eucn:producedBy  rdf:type       owl:FunctionalProperty   ← world-closure
  FunctionalProperty + Unique Name Assumption → eucn:malt-fermentation ≠ eucn:grain-distillation
  → NOT(producedBy hasValue eucn:malt-fermentation) provable for whisky-12y
```
