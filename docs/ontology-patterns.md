# OWL 2 DL Classification Patterns

Canonical reference for the production-process restriction pattern used in the EU Customs Ontology.

---

## 1. Production-process restriction pattern

Each CN heading that can be identified by its production process is defined by an `owl:equivalentClass` axiom that combines a `hasValue` restriction on `eucn:producedBy` with one or more datatype restrictions (e.g. ABV range).

The pattern has three moving parts:

- **Process class** — a named `owl:Class` that is a subclass of `bfo:Process` (BFO 2020, `obo:BFO_0000015`). The class represents the *type* of production process (e.g. malt fermentation).
- **Singleton individual** — a single `owl:NamedIndividual` that is typed as that process class and is the *unique named instance* referenced in equivalence axioms. There is exactly one singleton per process class.
- **`eucn:producedBy`** — an `owl:ObjectProperty` declared `owl:FunctionalProperty`. `FunctionalProperty` means each beverage individual has *at most one* production-process value. This is the world-closure device: the reasoner knows there is no other production process for the individual.
- **`owl:hasValue` restriction** — pins the `producedBy` filler to the specific singleton IRI (not to an anonymous individual or a class).

```turtle
@prefix eucn: <https://w3id.org/eucn/> .
@prefix obo:  <http://purl.obolibrary.org/obo/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# Process class (BFO Process subclass)
eucn:MaltFermentation a owl:Class ;
    rdfs:subClassOf obo:BFO_0000015 ;      # bfo:Process
    rdfs:label "malt fermentation"@en .

# Singleton individual
eucn:malt-fermentation a owl:NamedIndividual, eucn:MaltFermentation ;
    rdfs:label "malt fermentation process"@en .

# producedBy property
eucn:producedBy a owl:ObjectProperty, owl:FunctionalProperty ;
    owl:inverseOf obo:RO_0002234 ;         # inverseOf RO has_output
    rdfs:range obo:BFO_0000015 .

# Equivalence axiom (Beer must have malt fermentation process)
eucn:Beer owl:equivalentClass [
    owl:intersectionOf (
        [ owl:onProperty eucn:producedBy ; owl:hasValue eucn:malt-fermentation ]
        [ owl:onProperty eucn:alcoholByVolumePercent ;
          owl:someValuesFrom [ a rdfs:Datatype ;
            owl:onDatatype xsd:decimal ;
            owl:withRestrictions ([ xsd:minExclusive 0.5 ]) ] ]
    )
] .

# ABox assertion
demo:czech-lager a owl:NamedIndividual ;
    eucn:producedBy eucn:malt-fermentation ;
    eucn:alcoholByVolumePercent "5.0"^^xsd:decimal .
```

When the reasoner processes `demo:czech-lager`, it finds `producedBy eucn:malt-fermentation` (satisfying the `hasValue` restriction) and ABV 5.0 > 0.5 % (satisfying the datatype restriction), and infers `demo:czech-lager rdf:type eucn:Beer`.

---

## 2. Graph-derived complement restriction

Classification is divided into two phases:

- **Phase 1** — classes for which a unique production process exists. Each gets an unconditional `hasValue` restriction: `producedBy = <singleton>`. Examples: `Beer` (malt fermentation), `Wine` (grape fermentation), `FlavouredWine` (grape flavouring), `FermentedBeverage` (fruit fermentation), `Vinegar` (acetic fermentation), `NonAlcoholicBeverage` (sweetened water process).

- **Phase 2** — classes that are identified by *exclusion* rather than by a unique production process. The build step `_neg_hasvalue_from_disjoint_equiv` walks the Phase 1 equivalence axioms of all `owl:disjointWith` siblings of the target class, extracts their `hasValue` fillers, and generates a `NOT(producedBy = X)` complement restriction for each one.

`eucn:Spirit` is a Phase 2 class. It has no unique production process (whisky, brandy, vodka, rum … are all spirits), but it *cannot* be produced by any of the Phase 1 production processes. Its equivalence axiom is therefore built from ABV range restrictions plus a set of complement restrictions:

```turtle
eucn:Spirit owl:equivalentClass [
    owl:intersectionOf (
        # ABV range
        [ owl:onProperty eucn:alcoholByVolumePercent ;
          owl:someValuesFrom [ owl:onDatatype xsd:decimal ;
            owl:withRestrictions ([ xsd:minExclusive 0.5 ]) ] ]
        [ owl:onProperty eucn:alcoholByVolumePercent ;
          owl:someValuesFrom [ owl:onDatatype xsd:decimal ;
            owl:withRestrictions ([ xsd:maxExclusive 80.0 ]) ] ]
        # NOT conditions derived from disjoint siblings (Beer, Wine, ...)
        [ owl:complementOf [ owl:onProperty eucn:producedBy ;
                              owl:hasValue eucn:malt-fermentation ] ]
        [ owl:complementOf [ owl:onProperty eucn:producedBy ;
                              owl:hasValue eucn:grape-fermentation ] ]
        [ owl:complementOf [ owl:onProperty eucn:producedBy ;
                              owl:hasValue eucn:grape-flavouring ] ]
        [ owl:complementOf [ owl:onProperty eucn:producedBy ;
                              owl:hasValue eucn:fruit-fermentation ] ]
        [ owl:complementOf [ owl:onProperty eucn:producedBy ;
                              owl:hasValue eucn:acetic-fermentation ] ]
        [ owl:complementOf [ owl:onProperty eucn:producedBy ;
                              owl:hasValue eucn:sweetened-water-process ] ]
        # ... more NOT conditions for other disjoint siblings
    )
] .
```

Note that `grain-distillation` does **not** appear as a Phase 1 `hasValue` restriction; it belongs to no Phase 1 class. `demo:whisky-12y` (grain-distillation, ABV 43 %) is inferred as `eucn:Spirit` because:

1. ABV 43 % satisfies both range bounds (> 0.5 % and < 80.0 %).
2. `producedBy eucn:grain-distillation` is provably distinct from all six NOT-condition singletons (see §3).
3. No Phase 1 `hasValue` restriction matches `grain-distillation`.

---

## 3. OWA and world-closure

OWL uses the **Open World Assumption (OWA)**: the absence of a triple does not mean it is false — it means it is unknown. Under OWA, a complement restriction `NOT(producedBy = eucn:malt-fermentation)` does **not** follow merely from the absence of a `producedBy eucn:malt-fermentation` assertion. The reasoner must be able to *prove* distinctness.

This project achieves world-closure for `producedBy` through three cooperating mechanisms:

1. **`owl:FunctionalProperty`** — each individual has at most one `producedBy` value. Once the value is known (e.g. `grain-distillation`), no other value is possible.
2. **Named singleton individuals** — the `producedBy` value is a *named individual* with a specific IRI. Anonymous individuals (blank nodes) or class-level `someValuesFrom` restrictions would leave the filler unspecified and defeat complement reasoning.
3. **`owl:disjointWith` between process classes + `owl:differentFrom` between singletons** — together these prove that `eucn:grain-distillation ≠ eucn:malt-fermentation`, which is the key step enabling a complement restriction to fire.

**Critical implementation note for Konclude v0.7.0:** `owl:differentFrom` between singleton individuals alone is NOT sufficient for Konclude to infer membership in complement-`hasValue` restrictions. The reasoner requires `owl:disjointWith` between the process *classes*, combined with class membership of the singletons (each singleton is typed as its class), to prove individual distinctness. Both `differentFrom` (between individuals) and `disjointWith` (between classes) are declared in the ontology. The `disjointWith` between classes is the load-bearing mechanism that enables Spirit and EthylAlcohol realization in Konclude.

---

## 4. Mixed products

`eucn:producedBy` is an `owl:FunctionalProperty`, which means each individual has **at most one** production-process value. This is intentional and reflects the CN single-heading rule: a product belongs to exactly one CN heading.

Products that are genuinely produced by more than one process (e.g. a fortified wine that involves both grape fermentation and distilled spirit addition) cannot be classified by the `producedBy` pattern alone, because no single singleton IRI can represent both processes simultaneously.

For such **mixed products**, the ABox must contain an explicit `rdf:type` assertion:

```turtle
demo:port-wine a owl:NamedIndividual, eucn:FlavouredWine ;
    eucn:producedBy eucn:grape-fermentation ;
    eucn:alcoholByVolumePercent "19.0"^^xsd:decimal .
```

This is a feature, not a limitation. CN classification of mixed products requires human judgment (the classifier must decide which heading the product "essentially" belongs to). The ontology models this correctly: the reasoner handles unambiguous cases automatically; ambiguous cases require a human-asserted `rdf:type` in the ABox.

---

## 5. Adding a new chapter

Follow this checklist to add classification support for a new CN chapter (replace `NN` with the two-digit chapter number):

1. **Create `src/ontology/process_classes_chNN.py`**
   - Declare process classes: each as `owl:Class`, `rdfs:subClassOf obo:BFO_0000015`, with bilingual (`@en`, `@de`) `rdfs:label` and `skos:definition`.
   - Declare singleton individuals: typed as both `owl:NamedIndividual` and their process class, with bilingual labels.
   - Declare **pairwise `owl:differentFrom`** between all singleton individuals (21 pairs for 7 singletons, etc.).
   - Declare **pairwise `owl:disjointWith`** between all process classes — this is required for Konclude realization (see §3).

2. **Wire into `src/ontology/tbox.py`**: add `from src.ontology.process_classes_chNN import add_process_classes_chNN` and call `add_process_classes_chNN(g)` after `add_product_classes_chNN(g)`.

3. **Add Phase 1 axioms in `src/ontology/equivalence_axioms.py`**: for each CN heading with a unique production process, add one `_has_value_restr(g, produced_by, EUCN["singleton-iri"], "key")` call.

4. **Add Phase 2 axioms** (classes without a unique production process) using `_neg_hasvalue_from_disjoint_equiv`. These axioms are derived automatically from the Phase 1 axioms of disjoint sibling classes.

5. **Update ABox fixtures** (`tests/fixtures/beverages_demo.ttl` or a new fixture): add `eucn:producedBy eucn:singleton-iri` assertions for demo individuals so that realization tests cover the new chapter.

6. **Run the test suite** to confirm no regressions:
   ```bash
   python3 -m pytest tests/unit/ tests/acceptance/ -q
   ```
