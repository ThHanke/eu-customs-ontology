---
id: 2026-06-08-005-iu7
title: IU-7 Ch23 Investigation Findings
status: partial
created: 2026-06-08
parent: 2026-06-08-005
---

# IU-7: Ch23 (Residues, Waste, Animal Feed) Investigation

## Summary

Full pipeline run for Ch23 was not executed — no intermediate data (TARIC XML or wizard JSONL)
was available in the development environment. Network scraping was not performed.

Findings are based on static code analysis and the chapter description.

## Pipeline Dispatch Verification

`get_chapter(23)` correctly raises `ValueError`:
```
Chapter 23 not yet implemented. Add a module and register it.
```

The generic pipeline (IU-1 through IU-6) handles Ch23 cleanly at the dispatch layer: the
error is deterministic and descriptive. No silent failure or empty ontology.

## Ch23 Characteristics (from CN structure)

Chapter 23: Residues and waste from the food industries; prepared animal fodder.

| Aspect | Assessment |
|--------|-----------|
| Primary discriminating criteria | Composition ratios (protein %, fat %, moisture %, fibre %) — NOT production processes |
| BFO process pattern | Limited applicability. Ch23 products are classified by their chemical composition, not by the process that produced them. `eucn:producedBy` will not be the primary discriminating property. |
| Quantitative wizard questions | Likely use `%` unit (already in `_QUANT_RE`). Energy content (`MJ/kg`, `kcal/kg`) probably needed for compound feeds. |
| Root wizard structure | Binary split: residue/waste (by-product of food industries) vs. prepared compound feed |
| New discriminating properties needed | Likely: `eucn:crudeProteinPercent`, `eucn:crudeFatPercent`, `eucn:crudeAshPercent`, `eucn:moisturePercent` as DatatypeProperties with `xsd:decimal` range |

## What Breaks With Zero Code Changes

Running `python -m src.pipeline --chapter 23 --force` would fail at Step 3 (build-ontology)
with `ValueError: Chapter 23 not yet implemented.` — before any file is written.

This is the intended behavior. No silent partial output.

## Proposed Ch23 Module Skeleton

To add Ch23:
1. Create `src/ontology/discriminating_props_ch23_feed.py` with composition properties
2. Create `src/ontology/product_classes_ch23_feed.py` (residue vs. feed vs. premix hierarchy)
3. Create `src/ontology/process_classes_ch23_feed.py` — likely a no-op or minimal (drying, pelletizing)
4. Create `src/ontology/equivalence_axioms_ch23_feed.py`
5. Register in `chapter_registry.py` with `slug="residues-feed"`

The BFO process pattern from Ch22 may augment rather than replace composition-based
classification for Ch23: `eucn:producedBy someValuesFrom DryingProcess` can coexist with
`eucn:crudeProteinPercent` range restrictions.

## Regex Patterns Likely Needed

| Unit | Example wizard text | `_QUANT_RE` status |
|------|--------------------|--------------------|
| `%` | "crude protein content ≥ 15 %" | already present |
| `MJ/kg` | "metabolisable energy ≥ 9 MJ/kg" | probably missing |
| `kcal/kg` | "energy content > 3000 kcal/kg" | probably missing |

## Next Steps

1. Scrape Ch23 wizard and fetch Ch23 TARIC XML in a connected environment
2. Review `wizard_axiom_coverage_ch23.json` coverage percentage
3. Implement `discriminating_props_ch23_feed.py` and related modules
4. Register Ch23 in `chapter_registry.py`
