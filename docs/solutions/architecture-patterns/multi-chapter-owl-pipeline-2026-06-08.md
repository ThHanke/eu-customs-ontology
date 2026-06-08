---
title: Multi-Chapter Generic OWL Pipeline Architecture
date: 2026-06-08
category: architecture-patterns
module: ontology pipeline
problem_type: architecture_pattern
component: tooling
severity: medium
applies_when:
  - Adding a new CN chapter to the pipeline
  - Extending the ontology beyond Ch22 (Beverages)
  - Deciding where chapter-specific OWL logic belongs
tags: [ontology, owl, pipeline, chapter-registry, multi-module, rdflib, konclude]
---

# Multi-Chapter Generic OWL Pipeline Architecture

## Context

The Ch22 (Beverages) ontology pipeline had all chapter-specific OWL logic hardcoded
in `pipeline.py` and flat module files (`discriminating_props.py`, `product_classes.py`,
etc.). Adding Ch23 would have required modifying `pipeline.py` with `if chapter == 23:`
guards — a pattern the design explicitly prohibits.

Refactoring goal: zero `pipeline.py` changes when adding any new chapter; all
chapter-specific logic in chapter modules registered in `chapter_registry.py`.

## Guidance

### Module structure

Each chapter has four modules, each exposing a single `add_*` function:

```
src/ontology/
  core.py                          # chapter-agnostic TBox (producedBy, cnHeadingCode, BFO stubs)
  owl_helpers.py                   # shared idempotent OWL builder helpers
  chapter_registry.py              # ChapterModule dataclass + CHAPTERS dict + get_chapter()
  discriminating_props_beverages.py  # Ch22 data properties
  product_classes_beverages.py       # Ch22 product class hierarchy
  process_classes_beverages.py       # Ch22 BFO process classes + singletons
  equivalence_axioms_beverages.py    # Ch22 owl:equivalentClass axioms
```

### ChapterModule registry

```python
@dataclass
class ChapterModule:
    label: str
    slug: str                                            # used in filenames
    add_discriminating_props: Callable[[Graph], None]
    add_product_classes: Callable[[Graph], None]
    add_process_classes: Callable[[Graph], None]
    add_equivalence_axioms: Callable[[Graph], None]

CHAPTERS: dict[int, ChapterModule] = {
    22: ChapterModule(
        label="Beverages, spirits and vinegar",
        slug="beverages",
        add_discriminating_props=add_discriminating_props_beverages,
        ...
    ),
}

def get_chapter(n: int) -> ChapterModule:
    if n not in CHAPTERS:
        raise ValueError(f"Chapter {n} not yet implemented. ...")
    return CHAPTERS[n]
```

`get_chapter()` raises `ValueError` immediately for unregistered chapters — no silent
partial output, no empty ontology.

### Multi-module OWL file layout

The pipeline produces three files per chapter run:

| File | Contents | Purpose |
|------|----------|---------|
| `eucn-core-{date}.ttl` + `eucn-core-latest.ttl` | Core TBox only (`producedBy`, `cnHeadingCode`, BFO stubs) | Imported by chapter TTL; stable across chapters |
| `eucn-ch{N}-{slug}-{date}.ttl` + `eucn-ch{N}-{slug}-latest.ttl` | Chapter TBox + ABox + `owl:imports <core>` | Human-readable; CI change detection; Widoco docs input |
| `eucn-ch{N}-{slug}-{date}-flat.ttl` | Core + chapter merged, all `owl:imports` stripped | **Konclude input only** — Konclude WASM cannot resolve remote IRIs |

### CRITICAL: Konclude flat TTL constraint

```python
# Strip owl:imports before passing to Konclude
flat_g = Graph()
for s, p, o in g:
    if p != OWL.imports:
        flat_g.add((s, p, o))
flat_g.serialize(destination=str(flat_ttl_out), format="longturtle")
```

Never pass a TTL with `owl:imports` triples to Konclude — it will fail or silently
ignore the imported ontology.

### Stable alias pattern for CI/CD

```python
# After serializing dated file, write stable alias
shutil.copy(str(ttl_out), str(ttl_latest))       # eucn-ch22-beverages-latest.ttl
shutil.copy(str(core_ttl_out), str(core_ttl_latest))  # eucn-core-latest.ttl
```

CI (`build-release.yml`) uses the stable alias for SHA256 change detection.
`docs.yml` uses it as the Widoco input. Dated files accumulate as history.

### CRITICAL: `_neg_hasvalue_from_disjoint_equiv` — never modify

This function in `owl_helpers.py` auto-derives `NOT(producedBy someValuesFrom C)`
complement restrictions from disjoint sibling `equivalentClass` axioms. It is the
**only** mechanism that enables Spirit/EthylAlcohol discrimination under OWA.
Moving it to `owl_helpers.py` was safe; any logic change breaks the classification.

### Shared OWL helpers must be idempotent

All helpers in `owl_helpers.py` must be safe to call multiple times on the same graph.
`rdflib.Graph.add()` is a set operation — adding the same triple twice is a no-op.
Verify new helpers: `assert len(g) == len(g)` after second call on same graph.

### Bilingual label invariant

Every OWL class and property must have:
- `rdfs:label@en` + `rdfs:label@de`
- `skos:definition@en` + `skos:definition@de`

Konclude and Widoco both surface these. Existing label wording must not change.

## Why This Matters

- `pipeline.py` has a test (`test_pipeline_no_chapter_guard.py`) that fails if
  `if chapter ==` appears anywhere in the source. Chapter guards are permanently
  prohibited.
- Adding Ch23 requires only: 4 new module files + 1 registry entry. Zero changes
  to `pipeline.py`, `tbox.py`, or `abox.py`.
- `eucn:producedBy` is declared in `core.py` only — never in chapter modules.
  Declaring it twice creates duplicate triples that can confuse reasoners.

## When to Apply

- Creating a new chapter: implement all four `add_*` functions, register in
  `CHAPTERS`, choose a `slug` (used in filenames and ontology IRIs).
- Ch23 note (from investigation `docs/plans/2026-06-08-005-iu7-ch23-investigation.md`):
  composition-ratio properties (`crudeProteinPercent`, etc.) replace `producedBy` as the
  primary discriminating mechanism; process pattern still applicable for drying/pelletizing.
- Adding a new shared helper: add to `owl_helpers.py`, verify idempotency, add a
  unit test in `tests/unit/test_owl_helpers.py`.

## Examples

### Adding Ch23

```python
# 1. Create src/ontology/discriminating_props_ch23_feed.py
def add_discriminating_props_ch23_feed(g: Graph) -> None:
    _data_prop(g, EUCN.crudeProteinPercent, XSD.decimal,
               label_en="Crude protein content (%)", label_de="Rohproteingehalt (%)")
    # ...

# 2-4. Create product_classes, process_classes, equivalence_axioms modules

# 5. Register in chapter_registry.py
from src.ontology.discriminating_props_ch23_feed import add_discriminating_props_ch23_feed
CHAPTERS[23] = ChapterModule(
    label="Residues and waste from the food industries; prepared animal fodder",
    slug="residues-feed",
    add_discriminating_props=add_discriminating_props_ch23_feed,
    ...
)
```

Running `python -m src.pipeline --chapter 23 --force` now produces:
- `eucn-core-{date}.ttl`
- `eucn-ch23-residues-feed-{date}.ttl` (with `owl:imports` to core)
- `eucn-ch23-residues-feed-{date}-flat.ttl` (for Konclude)

### Before/After: tbox.py chapter dispatch

**Before (hardcoded):**
```python
def build_tbox(g, extract_date=None):
    add_discriminating_props_ch22(g)   # Ch22 only
    add_product_classes_ch22(g)
```

**After (generic):**
```python
def build_tbox(g, extract_date=None, chapter: int = 22):
    build_core_tbox(g, extract_date=extract_date)
    ch = get_chapter(chapter)
    ch.add_discriminating_props(g)
    ch.add_product_classes(g)
    ch.add_process_classes(g)
```

## Related

- `docs/plans/2026-06-08-005-feat-multi-chapter-generic-ontology-plan.md` — implementation plan
- `docs/plans/2026-06-08-005-iu7-ch23-investigation.md` — Ch23 static analysis
- OWL classification singleton pattern: `docs/solutions/` (see `project_owl_classification_pattern` in memory)
