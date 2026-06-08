---
title: "feat: OWL 2 DL product classes with BFO alignment and automated wizard-to-axiom transform"
type: feat
status: active
date: 2026-06-08
origin: docs/plans/2026-06-05-001-feat-eu-customs-ontology-pilot-plan.md
---

# OWL 2 DL Product Classes, BFO Alignment, and Automated Wizard-to-Axiom Transform

## Overview

The current ontology is an RDFS schema with OWL decoration: six classes, no restrictions,
no disjointness, no equivalence axioms. Konclude finds everything consistent vacuously.

This plan redesigns the TBox and the pipeline so that:

1. **Physical goods are OWL classes** (Beer, StillWine, Spirits…) rooted in BFO 2020 via
   shallow subclass stubs — no `owl:imports`, just IRI alignment.
2. **CN code individuals are forced by equivalence axioms**: a named product class carries
   `owl:equivalentClass` restrictions so the reasoner can entail which CN code applies to any
   individual described only by physical properties.
3. **Wizard questions become OWL axioms automatically** via a dedicated, purely functional
   transformer that requires no NLP or LLM. Each path from root to a terminal CN-code node in
   the EZT-Online decision tree is an intersectionOf restriction. The transformer reports a
   **coverage metric** for each chapter: which questions it parsed successfully, which fell back
   to a string-value property, and why.
4. **BFO property alignment is phased**: shallow `rdfs:subClassOf BFO:Object` is implemented
   now; a deeper survey of `bfo:has_part`, `bfo:has_quality`, and RO relations needed for CN
   discrimination is deferred to a separate design pass (see Deferred to Separate Tasks).
5. **Konclude classify mode** does real work: inferred subclass hierarchy is parsed and stored
   in a named graph `eucn:inferred/{date}`.

## Problem Frame

The honest assessment: the current implementation is an annotated triple store, not an
ontology. A reasoner adds zero inferential value. The design described here changes that by
encoding the legal classification logic — which lives in the EZT-Online wizard — directly as
OWL 2 DL axioms, making the classification procedure machine-executable and the coverage
of that encoding measurable.

## Requirements Trace

- R1. Product categories are OWL classes, not individuals, rooted in BFO 2020.
- R2. CN code individuals remain individuals; product classes carry `owl:equivalentClass`
  axioms that force CN code membership.
- R3. The wizard-to-axiom transform is a dedicated, purely functional module with no NLP
  dependency. It outputs both axioms and a structured coverage report.
- R4. The coverage report enumerates every wizard question, the type of property it
  produced (boolean, quantitative, fallback), and which CN codes it affects.
- R5. Disjointness between sibling product classes is declared using pairwise
  `owl:disjointWith` (not `owl:AllDisjointClasses` — see Konclude constraint below).
- R6. Konclude classify output is parsed and stored in a named graph after the
  consistency check passes.
- R7. All new TBox terms carry bilingual rdfs:label (en + de) and skos:definition (en + de).
- R8. Pipeline and all existing tests continue to pass.

## Scope Boundaries

- Only Chapter 22 (Beverages) is in scope for the product class hierarchy in this plan.
  The transformer is chapter-agnostic.
- No `owl:imports` of BFO — shallow stub declarations only.
- No SWRL rules (OWL 2 DL profile constraint).
- No LLM or NLP for any transformation step.
- Trade-political distinctions (MFN vs. GSP/preference) are carried by existing
  `eucn:geographicScope` on `eucn:TARICMeasure`. They are NOT encoded in product classes.
- Packaging-size distinctions (≤2 L vs. >2 L containers) are encoded as `owl:onDataRange`
  facet restrictions on a `eucn:maxContainerVolumeL` data property — they do NOT produce
  separate product classes.
- BFO quality hierarchy (`bfo:has_quality`, `bfo:has_part`, RO property alignment) is
  surveyed in this plan as a design question but implemented in a follow-on task.

### Deferred to Separate Tasks

- Full BFO property alignment (bfo:has_part, bfo:has_quality, RO:0000086): separate design
  survey task — a dedicated curation document must first map each discriminating criterion
  (alcohol content, carbonation, fermentation base, container volume) to a BFO/RO property
  type before implementation.
- Full EZT-Online wizard scrape for Chapter 22: wizard scrape currently has only 1 node;
  all units here will work against the stub, but the full axiom coverage only materialises
  once the wizard is fully scraped.
- Chapter-agnostic product class library (Chapters 01–98): separate planning task.

## Context & Research

### Relevant Code and Patterns

- `src/ontology/namespaces.py` — EUCN namespace, ONTOLOGY_IRI, VANN; add BFO here.
- `src/ontology/tbox.py` — `build_tbox(graph, extract_date)`: idempotent, all class/property
  declarations. New modules hook into the same graph; `build_tbox` calls them.
- `src/ontology/abox.py` — `build_abox(chapter_data, wizard_tree, graph)`: ABox population.
  Wizard-to-axiom output is added here, driven by `WizardTree`.
- `src/ontology/iri.py` — `mint_iri(key)` via uuid5. New wizard-property IRIs use
  `mint_iri(f"wizardQ:{question_text_stripped}")`.
- `src/reasoning/konclude.py` — `classify(ttl_path) -> str` already implemented but not
  called by the pipeline. Step 4.5 adds the call.
- `src/pipeline.py` — orchestration: fetch → scrape → build → consistency → classify → SPARQL.
- `tests/integration/test_konclude.py` — uses `owl:disjointWith` to test inconsistency
  detection. Confirms pairwise disjointness works through Konclude CLI.
- `data/intermediate/taric_ch22.json` — 3,992 measures across 30 distinct 6-digit
  subheadings (220000–220900).

### Institutional Learnings (from existing plan)

- **No `owl:FunctionalProperty` on ABox-populated properties** — Konclude WASM CLI has a
  known issue with FunctionalProperty over large ABoxes. Avoid.
- **No `owl:AllDisjointClasses`** — use pairwise `owl:disjointWith` instead (AllDisjointClasses
  can hang in Konclude WASM's materialize path, though it is safe in consistency-check mode;
  consistency check is what the pipeline uses, so pairwise is the safe choice).
- **TTL file input only** — always pass `--input file.ttl` to Konclude; never pipe.
- **Turtle input to Konclude, Turtle output from classify** — output is `stdout`, already
  captured in `konclude.classify()`.
- **pyoxigraph for all SPARQL** — rdflib is I/O only. Named-graph queries need
  `use_default_graph_as_union=True` or explicit FROM NAMED clauses.
- **UUID5 minting is stable** — existing IRIs must not change; new IRIs for wizard-question
  properties use the same `mint_iri` function with a `wizardQ:` key prefix.

### CN Chapter 22 Heading Structure (for named product class hierarchy)

| Heading | Subheadings | Product |
|---|---|---|
| 2200 | 220000 | Chapter residual / catch-all |
| 2201 | 220100, 220110 | Water (natural, mineral, aerated), ice, snow |
| 2202 | 220210, 220291, 220299 | Sweetened/flavoured water; non-alcoholic beverages |
| 2203 | 220300 | Beer made from malt |
| 2204 | 220410 (sparkling), 220421/29 (still ≤/>2L), 220422 (>10L), 220430 (grape must) | Wine of fresh grapes |
| 2205 | 220510, 220590 | Vermouth and other flavoured wines |
| 2206 | 220600 | Other fermented beverages (cider, perry, mead, mixtures) |
| 2207 | 220710, 220720 | Undenatured/denatured ethyl alcohol ≥80% vol |
| 2208 | 220820–220890 | Spirits, liqueurs <80% vol (whisky, brandy, gin, vodka, rum…) |
| 2209 | 220900 | Vinegar and substitutes |

Key discriminating criteria visible from the subheading structure:
- **Carbonation** (sparkling vs. still): 220410 vs 220421/29
- **Container volume** (≤2L / >2L / >10L): 220421 vs 220429/422
- **Alcohol by volume** (ABV): separates 2201/2202 (non-alcoholic) from 2203–2208;
  ≥80% separates 2207 from 2208; fermented vs. distilled from 2206
- **Fermentation base** (malt, grape, fruit, grain): separates 2203/2204/2205/2206/2208
- **Denaturant presence**: 220710 (denatured) vs 220720 (undenatured) for 2207

## Key Technical Decisions

- **Wizard questions as OWL DatatypeProperties, IRIs from content hash**: Each unique
  question text is hashed via `uuid5(PIPELINE_NS_UUID, "wizardQ:{stripped_text}")` to a
  deterministic IRI. The question text becomes `rdfs:label` + `skos:definition`. This
  requires zero curation, is reproducible across runs, and aligns question IRIs across
  chapters if the same question appears in multiple chapter wizards.

- **Three property type tiers for wizard questions**:
  1. **Boolean** (yes/no questions): `owl:DatatypeProperty`, range `xsd:boolean`,
     restriction `owl:hasValue true/false`. Detection: answer is exactly "Ja"/"Nein"
     (or "Yes"/"No").
  2. **Quantitative** (threshold questions): `owl:DatatypeProperty`, range `xsd:decimal`.
     Regex extraction of comparator (`mehr als` / `höchstens` / `mindestens` / `weniger
     als`) and numeric value. Restriction: `owl:onDataRange [xsd:decimal +
     xsd:minExclusive/maxInclusive facet]`. This is valid OWL 2 DL.
  3. **Fallback** (regex failed): `owl:AnnotationProperty` with `owl:hasValue
     "answer_text"^^xsd:string`. Logged in coverage report as failure with reason.

- **Path-to-intersectionOf**: For each terminal ClassificationNode with a `cn_code`, walk
  from root collecting `(parent_question_property_iri, answer_restriction)` pairs. Build
  `owl:intersectionOf` of all restrictions. Assert `cn_code_individual owl:equivalentClass
  [intersectionOf ...]`. This is the core equivalence axiom.

- **Named product classes**: Manually declared for Ch22 headings in
  `src/ontology/product_classes.py`. Each gets `rdfs:subClassOf eucn:Beverage` (or a
  subclass thereof). Wizard-derived equivalence axioms at the 6-digit subheading level
  link back to these named classes via additional `rdfs:subClassOf` declared in the same
  module. The two layers are separate: named classes are curated, wizard axioms are auto-generated.

- **BFO attachment**: `eucn:Beverage rdfs:subClassOf <http://purl.obolibrary.org/obo/BFO_0000030>`
  (BFO:Object). The BFO IRI is declared as `owl:Class` with `rdfs:isDefinedBy` pointing to
  the BFO ontology URI. No `owl:imports`. All BFO class stubs go in `src/ontology/bfo_stubs.py`.

- **Pairwise disjointness**: `owl:disjointWith` between sibling heading-level classes
  (Beer disjointWith Wine, Beer disjointWith Spirits, etc.). Avoids AllDisjointClasses
  Konclude WASM hang risk.

- **Coverage metric is a Pydantic model + JSON output**: `WizardAxiomCoverage` has fields
  `total_terminal_nodes`, `covered_boolean`, `covered_quantitative`, `fallback_count`,
  `coverage_pct`, and a list of `QuestionAnalysis` records. Written to
  `data/intermediate/wizard_axiom_coverage_ch{N}.json` and summarised in pipeline output.

- **Classify output in named graph**: `eucn:inferred/{date}` holds inferred triples from
  Konclude classify stdout (parsed via `rdflib.Graph.parse`). Serialized only to `.trig`
  (not `.ttl` which is single-graph only).

## Open Questions

### Resolved During Planning

- **Which BFO class for goods?** BFO:Object (BFO_0000030). Physical trade goods are
  discrete, spatially self-connected material entities. BFO:MaterialEntity (BFO_0000040)
  would also work but Object is the more specific and conventional choice.
- **AllDisjointClasses vs. pairwise?** Pairwise `owl:disjointWith`. AllDisjointClasses
  is safe in consistency-check mode but risky in classify/materialize. Pairwise is always
  safe (see institutional learnings).
- **Wizard-to-axiom: NLP required?** No. Three tiers: boolean (exact string match),
  quantitative (regex on fixed German regulatory vocabulary), fallback (annotation with
  string value). The regulatory vocabulary is closed; the same patterns recur throughout
  the CN nomenclature.
- **Packaging (≤2L) as class vs. restriction?** OWL 2 DL data facet restriction on
  `eucn:maxContainerVolumeL` (xsd:decimal). Cleaner than packaging individuals; valid DL.

### Deferred to Implementation

- Exact regex patterns for German regulatory comparators (`mehr als`, `höchstens`,
  `mindestens`, `weniger als`, `mindestens … bis unter …`): to be finalised against
  the full scraped wizard text.
- Whether the classify output adds enough inferred subclass triples to be useful with
  only the heading-level hierarchy and stub wizard: confirm at runtime.

### Deferred to Separate Tasks (BFO Property Survey)

The following is a design survey question, not an implementation question:

> For each discriminating criterion in Chapter 22 (ABV, carbonation, fermentation base,
> container volume, denaturation), which BFO/RO property type best represents it?
> - ABV: BFO:Quality (BFO_0000019) instantiated by the beverage, measured by a
>   BFO:MeasurementInformationContentEntity? Or a plain xsd:decimal data property?
> - Container volume: BFO:has_part (RO_0000051) a container individual with a volume Quality?
>   Or a plain data property on the beverage individual?
> - Fermentation base: a BFO:Process (BFO_0000015) that is part of the manufacturing history?
>
> This survey should produce a curation document `docs/brainstorms/bfo-property-alignment-ch22.md`
> before deeper BFO integration is planned.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not
> implementation specification.*

### Three-layer architecture

```
Layer 1: BFO stubs (bfo_stubs.py)
  BFO_0000030 (Object) — owl:Class stub, rdfs:isDefinedBy BFO ontology URI

Layer 2: Named product classes (product_classes.py)
  eucn:Beverage  ⊑  BFO:Object
  eucn:Beer      ⊑  eucn:Beverage    ⊥  eucn:Wine
  eucn:Wine      ⊑  eucn:Beverage    ⊥  eucn:Beer
  eucn:StillWine ⊑  eucn:Wine
  eucn:SparklingWine ⊑ eucn:Wine     ⊥  eucn:StillWine
  … (full Ch22 hierarchy, see Unit 3)

Layer 3: Wizard-derived equivalence axioms (wizard_axioms.py)
  For each terminal node T with cn_code C:
    path = [(Q1, "Ja"), (Q2, "Nein"), (Q3, "mehr als 0,5 % vol")]
    property_Q1 = mint_iri("wizardQ:stripped(Q1.question_text)")   → boolean DatatypeProperty
    property_Q3 = mint_iri("wizardQ:stripped(Q3.question_text)")   → quantitative DatatypeProperty
                                                                       with xsd:minExclusive 0.5
    cn_code_individual owl:equivalentClass
      [ owl:intersectionOf (
          [ owl:Restriction owl:onProperty property_Q1  owl:hasValue true ]
          [ owl:Restriction owl:onProperty property_Q2  owl:hasValue false ]
          [ owl:Restriction owl:onProperty property_Q3
            owl:someValuesFrom [ a rdfs:Datatype
                                 owl:onDatatype xsd:decimal
                                 owl:withRestrictions ([ xsd:minExclusive "0.5"^^xsd:decimal ]) ]
          ]
      ) ]
```

### Coverage metric data flow

```
WizardTree
  └─► wizard_axioms.transform(tree) → (axioms: list[Triple], coverage: WizardAxiomCoverage)
        ├─► per question: classify as boolean | quantitative | fallback
        ├─► per terminal node: build intersectionOf
        └─► coverage.json written to data/intermediate/
```

### Pipeline sequence (updated)

```
Step 1  fetch-taric
Step 2  scrape-wizard
Step 3  build-ontology   ← calls bfo_stubs, product_classes, discriminating_props,
                            wizard_axioms, equivalence_axioms, abox, tbox, provenance
Step 4  konclude-check   (consistency — exits 1 if inconsistent)
Step 4.5 konclude-classify ← NEW: runs --mode classify, parses stdout TTL,
                              stores inferred triples in eucn:inferred/{date} named graph,
                              re-serialises .trig only (not .ttl)
Step 5  sparql-acceptance ← extended with inferred-graph queries
```

## Implementation Units

- [ ] **Unit 1: BFO stubs and namespace extension**

**Goal:** Declare BFO:Object (BFO_0000030) as a minimal `owl:Class` stub with correct
IRI, label, and `rdfs:isDefinedBy`. Add BFO namespace to `namespaces.py`.

**Requirements:** R1, R7

**Dependencies:** None

**Files:**
- Create: `src/ontology/bfo_stubs.py`
- Modify: `src/ontology/namespaces.py`
- Modify: `src/ontology/tbox.py` (call `add_bfo_stubs(graph)`)
- Test: `tests/unit/test_bfo_stubs.py`

**Approach:**
- `BFO = Namespace("http://purl.obolibrary.org/obo/")` in namespaces.py.
- `BFO_OBJECT = BFO["BFO_0000030"]` — the only BFO class needed for now.
- `add_bfo_stubs(graph)`: adds `BFO_OBJECT rdf:type owl:Class`, `rdfs:label "object"@en`,
  `rdfs:isDefinedBy <http://purl.obolibrary.org/obo/bfo/2020/bfo-core.owl>`. Idempotent.
- Called from `build_tbox()` before product class declarations so the stub is available
  when subClassOf is asserted.

**Test scenarios:**
- Happy path: `add_bfo_stubs(Graph())` produces a graph containing `BFO_0000030 rdf:type owl:Class`.
- Idempotency: calling twice produces the same triple count.
- IRI correctness: `BFO_OBJECT` starts with `http://purl.obolibrary.org/obo/BFO_`.
- Integration: TBox built via `build_tbox()` contains the BFO stub triple.

**Verification:** `build_tbox()` serialised TTL passes Konclude consistency check and
contains `<http://purl.obolibrary.org/obo/BFO_0000030> a owl:Class`.

---

- [ ] **Unit 2: Discriminating property layer**

**Goal:** Declare the named physical/chemical data properties needed for CN Chapter 22
classification. These are the *canonical*, human-curated properties. Auto-generated
wizard question properties (Unit 5) are separate and may eventually be mapped to these.

**Requirements:** R7

**Dependencies:** Unit 1

**Files:**
- Create: `src/ontology/discriminating_props.py`
- Modify: `src/ontology/tbox.py` (call `add_discriminating_props(graph)`)
- Test: `tests/unit/test_discriminating_props.py`

**Approach:**
Properties to declare (all `owl:DatatypeProperty`, ranges as noted, all with EN+DE
label and skos:definition):

| IRI | Range | Purpose |
|---|---|---|
| `eucn:alcoholByVolumePercent` | xsd:decimal | ABV % (e.g., 13.5) |
| `eucn:isCarbonated` | xsd:boolean | sparkling vs. still |
| `eucn:isDenatured` | xsd:boolean | denatured ethyl alcohol |
| `eucn:maxContainerVolumeL` | xsd:decimal | container ≤ value (litres) |
| `eucn:fermentationBase` | xsd:string | "malt", "grape", "fruit", "grain" |

No `owl:FunctionalProperty` (Konclude WASM constraint, see institutional learnings).
No domain assertions on these properties (they apply to any BFO:Object in principle).

**Test scenarios:**
- Happy path: all five properties present in graph with correct `rdf:type owl:DatatypeProperty`.
- EN+DE label and skos:definition on every property.
- Correct `rdfs:range` for each (xsd:decimal / xsd:boolean / xsd:string).
- No `owl:FunctionalProperty` assertion present (regression guard against Konclude bug).
- Turtle roundtrip: serialise and re-parse, triple count matches.

**Verification:** Konclude consistency check still passes after adding these properties.

---

- [ ] **Unit 3: Named product class hierarchy for Chapter 22**

**Goal:** Declare the Chapter 22 named product class hierarchy under `eucn:Beverage`,
with pairwise `owl:disjointWith` between siblings and `rdfs:subClassOf BFO:Object` at
the root.

**Requirements:** R1, R2, R5, R7

**Dependencies:** Units 1, 2

**Files:**
- Create: `src/ontology/product_classes.py`
- Modify: `src/ontology/tbox.py` (call `add_product_classes_ch22(graph)`)
- Test: `tests/unit/test_product_classes.py`

**Approach:**

Hierarchy (all with EN+DE label + skos:definition):
```
eucn:Beverage  ⊑  BFO:Object
  eucn:Water         ⊑  eucn:Beverage   (2201)
  eucn:NonAlcoholicBeverage ⊑ eucn:Beverage  (2202)
  eucn:Beer          ⊑  eucn:Beverage   (2203)
  eucn:Wine          ⊑  eucn:Beverage   (2204)
    eucn:SparklingWine ⊑ eucn:Wine      (220410)
    eucn:StillWine     ⊑ eucn:Wine      (220421/29)
    eucn:GrapeMust     ⊑ eucn:Wine      (220430)
  eucn:FlavouredWine ⊑  eucn:Beverage   (2205)
  eucn:FermentedBeverage ⊑ eucn:Beverage  (2206, non-wine fermented)
  eucn:EthylAlcohol  ⊑  eucn:Beverage   (2207)
  eucn:Spirit        ⊑  eucn:Beverage   (2208)
  eucn:Vinegar       ⊑  eucn:Beverage   (2209)
```

Pairwise disjointness between all heading-level siblings (Water, NonAlcoholicBeverage,
Beer, Wine, FlavouredWine, FermentedBeverage, EthylAlcohol, Spirit, Vinegar). Between
direct sub-siblings: SparklingWine ⊥ StillWine ⊥ GrapeMust.

The SKOS definitions must use ISO 704 intensional form (genus + differentia) referencing
the legal CN heading text as source.

**Test scenarios:**
- Happy path: `eucn:Beer rdf:type owl:Class` present.
- Subclass chain: `eucn:StillWine rdfs:subClassOf eucn:Wine rdfs:subClassOf eucn:Beverage
  rdfs:subClassOf BFO_0000030` all present.
- Disjointness: `eucn:Beer owl:disjointWith eucn:Wine` present (and symmetric).
- No `owl:AllDisjointClasses` in graph (regression guard).
- Every class has EN+DE rdfs:label.
- Every class has EN+DE skos:definition.
- Class count: ≥12 (`owl:Class` triples).
- Konclude consistency check passes with this TBox alone.
- Konclude consistency check raises `KoncludeConsistencyError` when an individual is typed
  both `eucn:Beer` and `eucn:Wine` (disjointness is enforced).

**Verification:** The `test_inconsistent_ontology_raises` test in
`tests/integration/test_konclude.py` passes adapted for Beer ⊥ Wine. Konclude classify
returns a non-empty inferred hierarchy.

---

- [ ] **Unit 4: Wizard-to-axiom transformer with coverage metric**

**Goal:** Implement a dedicated, purely functional module that takes a `WizardTree` and
produces (a) OWL equivalence axioms as a list of rdflib triples, and (b) a structured
`WizardAxiomCoverage` report. No NLP, no LLM, no side effects. The function is called
during ontology build in Step 3 and again standalone for reporting.

**Requirements:** R3, R4

**Dependencies:** Units 1, 2, 3 (needs graph with BFO stubs and discriminating properties)

**Files:**
- Create: `src/ontology/wizard_axioms.py`
- Modify: `src/schema/wizard.py` (no schema changes needed; confirm `path_from_root` is
  accessible on every node)
- Modify: `src/ontology/abox.py` (call `add_wizard_axioms(wizard_tree, graph)` and
  receive the coverage report)
- Modify: `src/pipeline.py` (write coverage JSON after build step; log summary)
- Test: `tests/unit/test_wizard_axioms.py`
- Test: `tests/integration/test_wizard_axioms_integration.py`

**Approach:**

Core function signature:
```
transform(tree: WizardTree) -> tuple[list[Triple], WizardAxiomCoverage]
```

Step-by-step logic (directional, not implementation specification):
1. For each terminal node T in `tree.nodes` where `T.is_terminal and T.cn_code is not None`:
   a. Walk from root to T using `path_from_root` to recover the sequence of
      `(parent_node, answer_text)` pairs.
   b. For each `(parent_node, answer_text)` pair, call `_classify_question(question_text,
      answer_text)` → `QuestionAnalysis`.
   c. Build one `owl:Restriction` per question analysis (see tiers below).
   d. Assert `cn_code_iri(T.cn_code) owl:equivalentClass [owl:intersectionOf restrictions]`.
2. Collect all `QuestionAnalysis` objects → `WizardAxiomCoverage`.

**Three question-type tiers** (detection in order, first match wins):

*Tier 1 — Boolean*: `answer_text.strip().lower()` in `{"ja", "nein", "yes", "no"}`.
  Property: `DatatypeProperty`, range `xsd:boolean`.
  Restriction: `owl:hasValue "true"^^xsd:boolean` for Ja/Yes, `"false"` for Nein/No.

*Tier 2 — Quantitative*: regex over `question_text` for German/English numeric patterns:
  - Pattern group: `r"(mehr als|mindestens|höchstens|weniger als|bis unter|über|unter)\s*([\d,]+)\s*(%\s*vol|vol\.?-?%|%|[lL]iter|Liter|kg)"`.
  - On match: extract comparator → OWL facet (`xsd:minExclusive`, `xsd:minInclusive`,
    `xsd:maxExclusive`, `xsd:maxInclusive`); extract value (replace "," with ".").
  - Restriction: `owl:onDataRange [rdfs:Datatype; owl:onDatatype xsd:decimal;
    owl:withRestrictions ([facet value])]` with `owl:someValuesFrom`.

*Tier 3 — Fallback*: `owl:AnnotationProperty`, `owl:hasValue "answer_text"^^xsd:string`.
  Logged to `WizardAxiomCoverage` with `success: false` and `failure_reason`.

**IRI minting for question properties:**
- `mint_iri(f"wizardQ:{question_text.strip()}")` → consistent IRI across chapters and runs.
- Property label: question text (DE) → `rdfs:label`; translate/annotate EN if available.

**`WizardAxiomCoverage` Pydantic model** (fields):
```
chapter: int
total_terminal_nodes: int
covered_boolean: int        # questions that produced Tier 1 restrictions
covered_quantitative: int   # questions that produced Tier 2 restrictions
fallback_count: int         # questions that fell through to Tier 3
coverage_pct: float         # (covered_boolean + covered_quantitative) / total_questions * 100
questions: list[QuestionAnalysis]
```

**`QuestionAnalysis` fields:**
```
question_text: str
property_iri: str
tier: "boolean" | "quantitative" | "fallback"
regex_match: str | None
extracted_threshold: float | None
extracted_facet: str | None   # "minExclusive" etc.
cn_codes_affected: list[str]
success: bool
failure_reason: str | None
```

Coverage JSON written to `data/intermediate/wizard_axiom_coverage_ch{chapter:02d}.json`.
Pipeline logs one summary line: `[wizard-axioms] 22/22 terminal nodes covered: 18 boolean,
3 quantitative, 1 fallback (coverage 95.5%)`.

**Execution note:** Implement test-first. Write failing tests for the transform function
against a hand-crafted minimal WizardTree fixture before implementing the classifier.

**Test scenarios:**
- Happy path boolean: a terminal node reached via "Ja" answer produces
  `owl:hasValue "true"^^xsd:boolean` restriction on the question property.
- Happy path boolean Nein: produces `owl:hasValue "false"^^xsd:boolean`.
- Happy path quantitative: question "mehr als 0,5 % vol", answer "Ja" → extracts 0.5,
  `xsd:minExclusive`, `xsd:decimal` restriction.
- Quantitative: "höchstens 2 Liter" → `xsd:maxInclusive 2.0`.
- Fallback: question with no numeric pattern and non-yes/no answer → tier 3, `success: false`.
- Multi-step path: root → Q1(Ja) → Q2(Nein) → terminal produces `intersectionOf` with
  two restrictions.
- Idempotency: calling transform twice on the same tree yields identical triple lists
  (sorted by subject/predicate/object).
- IRI stability: same question text on two different runs produces the same property IRI.
- Coverage report: `total_terminal_nodes` matches the count of terminal nodes in the tree.
- Coverage report: `coverage_pct` equals (tier1+tier2 questions / total questions) * 100.
- Empty tree (root only, no terminal nodes): returns empty list + coverage report with
  `total_terminal_nodes=0`, `coverage_pct=100.0` (vacuously covered).
- CN code IRI: the subject of the equivalence axiom is the same IRI as `cn_code_iri(T.cn_code)`.
- Integration: transformed axioms pass Konclude consistency check when added to a graph
  with the full TBox (product classes + BFO stubs).

**Verification:** Running `transform(stub_wizard_tree)` against the current 1-node wizard
produces an empty coverage report (0 terminal nodes), confirming the function is ready
for when the full wizard is scraped.

---

- [ ] **Unit 5: Named-class equivalence axioms for Chapter 22**

**Goal:** Manually declare the `owl:equivalentClass` linkages between named product classes
(Beer, Wine, etc.) and their corresponding CN code individuals, using the discriminating
properties from Unit 2. This is the human-curated complement to the wizard-derived axioms
from Unit 4.

**Requirements:** R2

**Dependencies:** Units 2, 3

**Files:**
- Create: `src/ontology/equivalence_axioms.py`
- Modify: `src/ontology/abox.py` (call `add_ch22_equivalence_axioms(graph)`)
- Test: `tests/unit/test_equivalence_axioms.py`
- Test: `tests/integration/test_equivalence_axioms_integration.py`

**Approach:**

Example axiom pattern for Beer (directional sketch):
```
eucn:Beer owl:equivalentClass [
    owl:intersectionOf (
        eucn:Beverage
        [ owl:Restriction; owl:onProperty eucn:fermentationBase;
          owl:hasValue "malt"^^xsd:string ]
        [ owl:Restriction; owl:onProperty eucn:alcoholByVolumePercent;
          owl:someValuesFrom [ rdfs:Datatype; owl:onDatatype xsd:decimal;
                               owl:withRestrictions ([ xsd:minExclusive "0.5"^^xsd:decimal ]) ] ]
    )
]
```

For container-size subheadings (StillWine ≤2L → CN 220421):
```
[ owl:intersectionOf (
    eucn:StillWine
    [ owl:Restriction; owl:onProperty eucn:maxContainerVolumeL;
      owl:someValuesFrom [ rdfs:Datatype; owl:onDatatype xsd:decimal;
                           owl:withRestrictions ([ xsd:maxInclusive "2.0"^^xsd:decimal ]) ] ]
) ]  owl:equivalentClass  eucn_ind:cn_220421
```

The full mapping (all Chapter 22 headings and key subheadings) is implemented in
`add_ch22_equivalence_axioms(graph)`. Initially covers headings 2201–2209 and the main
2204 subheading split (sparkling/still/grape-must, container-size split).

**Test scenarios:**
- Happy path: `eucn:Beer owl:equivalentClass` triple present in graph.
- Integration: Konclude classify, given an individual with `fermentationBase "malt"` and
  ABV > 0.5%, infers `rdf:type eucn:Beer`.
- Integration: individual typed `eucn:Beer` and `eucn:Wine` simultaneously → Konclude
  consistency check raises `KoncludeConsistencyError` (disjointness enforced).
- Structural: every `owl:equivalentClass` subject in the axioms is a known product class
  IRI (regression guard against typos).
- OWL 2 DL profile: no anonymous individual appears as the object of `owl:equivalentClass`
  outside an intersection (would violate DL profile).

**Verification:** Konclude classify invoked on the full TBox + these axioms produces
inferred subclass relations between named product classes. `rdflib.Graph` with OWL RL
reasoner (`owlrl`) can also exercise the axioms for quick local checks.

---

- [ ] **Unit 6: Konclude classify pipeline integration**

**Goal:** Add Step 4.5 to the pipeline: after the consistency check passes, run
`konclude.classify(ttl_out)`, parse the returned Turtle, and store the inferred triples
in the named graph `eucn:inferred/{date}` within the Dataset. Re-serialise only `.trig`
(which supports named graphs); `.ttl` is the single-graph TBox+ABox output and unchanged.

**Requirements:** R6

**Dependencies:** Units 1–5 (pipeline calls this after the full ontology is built)

**Files:**
- Modify: `src/pipeline.py` (add Step 4.5)
- Modify: `src/reasoning/konclude.py` (verify `classify()` captures stdout correctly;
  add error handling for empty stdout)
- Test: `tests/integration/test_pipeline.py` (add classify step assertion)

**Approach:**
- `classify(ttl_out) -> str` already exists in `konclude.py`. Verify it returns the
  inferred Turtle (stdout) when classify mode produces output.
- Parse the returned string as a `rdflib.Graph`. If the string is empty or the graph
  is empty, log a warning and skip (not a hard failure — classify may produce empty
  output for trivial TBoxes before the full wizard is scraped).
- Add the parsed triples to `ds.graph(URIRef(f"https://w3id.org/eucn/inferred/{date_str}"))`.
- Re-serialise the `.trig` file; do NOT rewrite `.ttl` (it is single-graph).
- Add `--no-classify` flag to the pipeline CLI to skip this step (mirrors `--no-reasoner`).

**Test scenarios:**
- Happy path: after consistency check, `classify()` is called; an empty result does not
  raise an exception.
- Integration: if classify returns valid Turtle, the inferred named graph in the Dataset
  contains at least the `rdf:type owl:Class` triples from the input TBox (Konclude
  echoes back at minimum).
- CLI flag: `--no-classify` causes Step 4.5 to be skipped; `.trig` still written (from
  Step 3 output).
- Error path: if `classify()` raises `subprocess.TimeoutExpired`, pipeline logs a warning
  and continues (Step 5 acceptance tests run without inferred graph).

**Verification:** Pipeline with full TBox runs end-to-end; `.trig` contains a named graph
with IRI `eucn:inferred/{date}`.

---

- [ ] **Unit 7: Extended SPARQL acceptance tests**

**Goal:** Add acceptance tests that exploit the new equivalence axioms and inferred graph:
(a) query the main graph for product class individuals, (b) query the inferred graph for
subclass relations, (c) confirm that an individual described only by physical properties
can be matched to its product class via SPARQL.

**Requirements:** R8 (existing tests pass), R6

**Dependencies:** Units 4, 5, 6

**Files:**
- Modify: `tests/acceptance/test_chapter22_sparql.py`
- Create: `tests/acceptance/test_chapter22_classification.py`

**Approach:**
New test: build a minimal ontology graph containing the TBox (with product classes and
equivalence axioms), add one ABox individual typed `eucn:Beer`, load into pyoxigraph,
and query for it by class. Then add an individual described only by
`eucn:fermentationBase "malt"` and `eucn:alcoholByVolumePercent 5.0`, and verify that
the correct CN code is present via a SPARQL query over the main graph (equivalence
axioms are materialized by the Konclude classify step and stored in the named graph).

Note: pyoxigraph is a SPARQL 1.1 engine with no OWL reasoner. Inferred triples must be
explicitly asserted (they come from the classify step) for SPARQL to return them.
Tests that exercise inference must load the classify output alongside the main TTL.

**Test scenarios:**
- Happy path: `eucn:Beer rdf:type owl:Class` present in queried graph.
- Named product class count: `SELECT (COUNT(?c) AS ?n) WHERE { ?c a owl:Class }` returns
  ≥12 (heading-level product classes + existing 6 TBox classes).
- Disjoint classes in SPARQL: no individual is typed both `eucn:Beer` and `eucn:Wine`
  (query using `FILTER EXISTS` both types; expect 0 rows).
- Equivalence axiom present: `eucn:Beer owl:equivalentClass ?anon` returns ≥1 row
  (blank node intersection is in the graph).
- Inferred graph: after loading classify output, `FROM NAMED <eucn:inferred/...>
  SELECT ?sub ?super WHERE { ?sub rdfs:subClassOf ?super }` returns at least the
  declared subclass pairs (consistency sanity check, not novel inference until full
  wizard is scraped).
- Coverage report: `wizard_axiom_coverage_ch22.json` exists and its `total_terminal_nodes`
  field matches the count of terminal nodes in `wizard_ch22.jsonl`.

**Verification:** `pytest tests/acceptance/ -q` passes with 0 failures. Coverage JSON
is present in `data/intermediate/`.

## System-Wide Impact

- **Interaction graph:** `build_tbox()` now calls four sub-builders (`add_bfo_stubs`,
  `add_discriminating_props`, `add_product_classes_ch22`, `add_ch22_equivalence_axioms`).
  `build_abox()` calls `add_wizard_axioms()` and receives the coverage report back.
  All functions write to the same `rdflib.Graph` — idempotency is each function's
  responsibility.
- **Error propagation:** `wizard_axioms.transform()` never raises on a Tier 3 fallback;
  it records the failure in the coverage report and continues. The only hard failure in
  the build step is a duplicate-triple inconsistency (which Konclude catches in Step 4).
- **State lifecycle risks:** wizard coverage JSON is overwritten each run (not appended).
  If the pipeline is interrupted between Step 3 and the classify step, the `.trig` may
  lack the inferred graph until the next `--force` run.
- **API surface parity:** The `run()` function signature gains `no_classify: bool = False`.
  All integration tests that call `pipeline_mod.run()` may need to pass
  `no_classify=True` to skip the Konclude classify subprocess in fast test runs.
- **Unchanged invariants:** `cn_code_iri()`, `taric_measure_iri()`, `classification_node_iri()`
  mint the same IRIs as before (UUID5 keys unchanged). Existing ABox individuals are
  unaffected. `eucn:TARICMeasure`, `eucn:CNCode`, `eucn:ClassificationNode` classes are
  retained; new product classes are additions, not replacements.
- **Integration coverage:** The equivalence axiom ↔ Konclude classify ↔ SPARQL acceptance
  chain cannot be proven by unit tests alone. `tests/integration/test_equivalence_axioms_integration.py`
  must exercise the full Konclude subprocess.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Wizard scrape is still only 1 node | All units are tested against the stub; full coverage only materialises after scraping. Transformer handles empty tree gracefully. |
| Quantitative regex misses regulatory patterns | Tier 3 fallback always fires; coverage report exposes misses. Regex patterns refined iteratively against real wizard text once fully scraped. |
| Konclude classify hangs on large ABox | Classify step has `timeout=300`. `--no-classify` flag lets pipeline proceed without it. |
| BFO property alignment unclear | Deferred to explicit survey task. Current plan encodes only `rdfs:subClassOf BFO:Object` — shallow, always safe. |
| `owl:equivalentClass` with quantitative facets and large ABox may trigger unsound classification | Test with Konclude classify on a non-trivial ABox before treating inferred results as authoritative. Known OWL 2 DL limitation: open-world assumption means the reasoner only infers when conditions are asserted, not absent. |
| Pairwise disjointWith grows as O(n²) for n sibling classes | For Ch22, n≤9 at heading level = 36 axioms. Acceptable. For a full CN library this needs revisiting. |

## Documentation / Operational Notes

- When the wizard is fully scraped, re-run the pipeline with `--force`. The coverage
  metric will report actual coverage. Any Tier 3 fallbacks become targets for regex
  pattern extension.
- The BFO property survey document (`docs/brainstorms/bfo-property-alignment-ch22.md`)
  is a prerequisite for the follow-on plan that replaces `eucn:fermentationBase xsd:string`
  with proper BFO quality individuals.

## Sources & References

- **Existing pilot plan:** `docs/plans/2026-06-05-001-feat-eu-customs-ontology-pilot-plan.md`
- **BFO 2020 IRI base:** `http://purl.obolibrary.org/obo/` (BFO_0000030 = Object)
- **OWL 2 DL profile spec (data ranges):** https://www.w3.org/TR/owl2-syntax/#Datatype_Restrictions
- **Konclude WASM CLI:** `/home/hanke/rdf-reasoner-konclude/dist/cli.js`
- **CN Chapter 22 legal text:** Official Journal supplement — CN 2026 (Implementing Regulation EU 2025/2578)
- **EZT-Online wizard:** `https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do`
