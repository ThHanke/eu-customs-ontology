---
id: 2026-06-08-005
title: Multi-Chapter Generic Ontology Pipeline
status: active
created: 2026-06-08
tags: [pipeline, multi-chapter, architecture, modularisation]
---

# Multi-Chapter Generic Ontology Pipeline

## Problem Frame

Ch22 (Beverages) is the sole implemented chapter. All chapter-specific Python
functions and TBox content are hardcoded: product classes, process classes,
discriminating properties, and equivalence axioms are all Ch22-only. The goal is
a **generic pipeline** where adding a new chapter requires only:

1. A new content module (Python file with standard function signature)
2. Registration in a chapter registry
3. No changes to `tbox.py`, `abox.py`, or `pipeline.py`

Simultaneously, the ontology must be **modular at the OWL level**:
- A shared core TBox (`eucn-core.ttl`) holds chapter-agnostic concepts
- Each chapter module (`eucn-ch22-beverages.ttl`) declares `owl:imports` on core
- Any chapter module is usable **standalone** (imports resolve to core)
- All chapter modules are loadable **together** (shared core is imported once;
  no IRI conflicts because all content lives in the `eucn:` namespace)

## Scope

**In scope:**
- Extract shared core OWL module from current monolithic TBox
- Rename Ch22 Python modules + ontology slugs to content-descriptive names
- Chapter registry pattern for zero-hardcoding dispatch
- Shared OWL builder helper library
- Pipeline output of `eucn-core` + chapter TTL with `owl:imports`
- Remove `if chapter == 22` guards from `pipeline.py`
- Attempt Ch23 to validate generality; document what breaks
- CI/CD update for multi-module build

**Out of scope:**
- Full coverage of all 99 chapters (iterative, chapter-by-chapter)
- Combined multi-chapter TTL (each chapter file ships separately; consumers load
  what they need)
- NLP-based wizard fallback handling

## Architecture

### OWL Module Hierarchy

```
eucn-core-latest.ttl
│  Ontology IRI: https://w3id.org/eucn/core
│  Contains: BFO/RO stubs, eucn:producedBy, eucn:cnHeadingCode,
│            ontology metadata
│
├── eucn-ch22-beverages-latest.ttl
│     Ontology IRI: https://w3id.org/eucn/ch22-beverages
│     owl:imports eucn-core (raw GitHub URL for standalone/Ontosphere use)
│     Contains: discriminating props (ABV%, isCarbonated, …),
│               product classes, process classes, equivalence axioms
│
├── eucn-ch23-{slug}-latest.ttl
│     Ontology IRI: https://w3id.org/eucn/ch23-{slug}
│     owl:imports eucn-core
│     …
```

**Standalone use:** Load any single chapter TTL — its `owl:imports` pulls in core
automatically via HTTP (Ontosphere, Protégé, any OWL-imports-aware tool).

**Combined use:** Load `eucn-core` + any set of chapter TTLs. Reasoner deduplicates
the shared core import. No IRI collisions because all named classes live in `eucn:`
and no two chapters define the same class name.

**Konclude pipeline use:** The Python pipeline merges core + chapter graphs into one
flat TTL before invoking Konclude. No reasoner-side `owl:imports` resolution needed.

### Python Module Layout (target state)

```
src/ontology/
  owl_helpers.py          ← shared builder helpers (extracted, no Ch-specific logic)
  core.py                 ← build_core_tbox(g) — chapter-agnostic TBox
  chapter_registry.py     ← ChapterModule dataclass + registry dict
  discriminating_props_beverages.py
  product_classes_beverages.py
  process_classes_beverages.py
  equivalence_axioms_beverages.py
  tbox.py                 ← build_tbox(g, chapter) — dispatches via registry
  abox.py                 ← build_abox(data, tree, g, chapter) — dispatches via registry
  bfo_stubs.py            ← unchanged (already part of core)
  namespaces.py           ← unchanged
  iri.py                  ← unchanged
  wizard_axioms.py        ← unchanged (already generic)
  provenance.py           ← unchanged
```

### Chapter Registry Pattern

```python
# src/ontology/chapter_registry.py
from dataclasses import dataclass
from typing import Callable
from rdflib import Graph

@dataclass
class ChapterModule:
    label: str          # human name, e.g. "Beverages, spirits and vinegar"
    slug: str           # kebab-case, e.g. "beverages"
    add_discriminating_props: Callable[[Graph], None]
    add_product_classes:      Callable[[Graph], None]
    add_process_classes:      Callable[[Graph], None]
    add_equivalence_axioms:   Callable[[Graph], None]

CHAPTERS: dict[int, ChapterModule] = {
    22: ChapterModule(
        label="Beverages, spirits and vinegar",
        slug="beverages",
        add_discriminating_props=add_discriminating_props_beverages,
        add_product_classes=add_product_classes_beverages,
        add_process_classes=add_process_classes_beverages,
        add_equivalence_axioms=add_equivalence_axioms_beverages,
    ),
    # 23: ChapterModule(slug="hops-malt", …),
}

def get_chapter(n: int) -> ChapterModule:
    if n not in CHAPTERS:
        raise ValueError(f"Chapter {n} not yet implemented. Add a module and register it.")
    return CHAPTERS[n]
```

`tbox.py` calls `get_chapter(chapter).add_product_classes(g)` etc.
`abox.py` calls `get_chapter(chapter).add_equivalence_axioms(g)`.

## Key Decisions

| Decision | Rationale |
|---|---|
| `owl:imports` raw GitHub URL (not w3id.org redirect) | Simpler; w3id.org redirect setup is non-trivial and adds failure mode. Revisit when repo is stable. |
| Core IRI `https://w3id.org/eucn/core` separate from `https://w3id.org/eucn` | Allows chapter TTLs to declare themselves as distinct ontologies while importing the shared base. Avoids circular import if someone loads chapter TTL into a tool that also fetches the main IRI. |
| Chapter slug in TTL filename and ontology IRI (`ch22-beverages`) | Content-descriptive; survives CN structure changes; both chapter number and content visible. |
| Shared helpers in `owl_helpers.py`, not inline in each module | DRY; helper bugs fixed once; new chapter authors start from known-good primitives. |
| Discriminating properties stay chapter-specific (not in core) | Premature to share; if a property appears in 2+ chapters, move it to core at that point. |
| Flat merged TTL for Konclude (no `owl:imports` in reasoner input) | Konclude WASM cannot resolve HTTP `owl:imports`; merging in Python is reliable and already tested. |
| `get_chapter(n)` raises on unknown chapter | Fail loudly; avoid silently building an empty/broken ontology for unknown chapters. |

## Implementation Units

### IU-1 — Extract `owl_helpers.py`

**Files changed:**
- `src/ontology/owl_helpers.py` (new)
- `src/ontology/product_classes_beverages.py` (import from helpers)
- `src/ontology/process_classes_beverages.py` (import from helpers)
- `src/ontology/equivalence_axioms_beverages.py` (import from helpers)

**What moves to helpers:**
- `_bnode(key)` — deterministic BNode from SHA256
- `_cls(g, iri, label_en, label_de, def_en, def_de)` — OWL class declaration
- `_sub(g, child, parent)` — `rdfs:subClassOf`
- `_cn_heading(g, cls_iri, code)` — `subClassOf [hasValue code]` restriction
- `_disjoint_pairs(g, classes)` — pairwise `owl:disjointWith`
- `_proc(g, iri, label_en, label_de, def_en, def_de)` — process class declaration
- `_dp(g, iri, …)` / `_op(g, iri, …)` — data/object property declaration
- `_equiv(g, cls, restrictions)` — `owl:equivalentClass` intersection
- `_decimal_range_restr(g, prop, min_excl, max_incl)` — datatype range restriction
- `_has_value_restr(g, prop, value, key_hint)` — `owl:hasValue` restriction
- `_some_values_class_restr(g, prop, cls, key_hint)` — `owl:someValuesFrom` restriction
- `_neg_hasvalue_from_disjoint_equiv(g, target_cls, prop, all_classes)` — auto-derive complement restrictions

**Tests:**
- `tests/unit/test_owl_helpers.py` (new)
- Scenarios: `_bnode` determinism; `_cls` emits exactly 4 triples; `_cn_heading` produces correct restriction shape; `_disjoint_pairs` count for N classes = N*(N-1); `_neg_hasvalue_from_disjoint_equiv` skips BNode values

**Constraints:**
- All helper functions must be idempotent (calling twice on same graph = same triple count)
- `_neg_hasvalue_from_disjoint_equiv` logic must not change (see plan 004 constraint)

---

### IU-2 — Create `src/ontology/core.py`

**Files changed:**
- `src/ontology/core.py` (new)
- `src/ontology/bfo_stubs.py` — no change; `core.py` calls `add_bfo_stubs(g)`
- `src/ontology/tbox.py` — calls `build_core_tbox(g)` before chapter dispatch

**`build_core_tbox(g)` declares:**
- Ontology header: `<https://w3id.org/eucn/core> a owl:Ontology` with `owl:versionIRI`, bilingual labels, `dcterms:creator`, `dcterms:license`, `dcterms:source`
- BFO stubs: `bfo:Process` (BFO_0000015), `bfo:Object` (BFO_0000030) — calls `add_bfo_stubs(g)`
- `obo:RO_0002234` stub (`has_output`) with bilingual label
- `eucn:producedBy` — ObjectProperty, FunctionalProperty, `inverseOf obo:RO_0002234`, bilingual label + definition
- `eucn:cnHeadingCode` — DatatypeProperty, range `xsd:string`, bilingual label + definition

**Not in core:**
- Chapter-specific discriminating properties
- Product/process class hierarchies

**Tests:**
- `tests/unit/test_core.py` (new)
- Scenarios: all 5 core entities present; `eucn:producedBy` is FunctionalProperty; `eucn:cnHeadingCode` has range `xsd:string`; idempotency; core graph is valid when loaded standalone into rdflib

---

### IU-3 — Rename Ch22 Modules to Content-Descriptive Names

**Files renamed/created:**
- `src/ontology/discriminating_props.py` → `src/ontology/discriminating_props_beverages.py`
  - Function: `add_discriminating_props` → `add_discriminating_props_beverages`
  - Remove `eucn:producedBy` and `eucn:cnHeadingCode` declarations (moved to IU-2 core)
  - Keep: `alcoholByVolumePercent`, `isCarbonated`, `isDenatured`, `maxContainerVolumeL`
- `src/ontology/product_classes.py` → `src/ontology/product_classes_beverages.py`
  - Function: `add_product_classes_ch22` → `add_product_classes_beverages`
  - Import helpers from `owl_helpers` (IU-1)
- `src/ontology/process_classes_ch22.py` → `src/ontology/process_classes_beverages.py`
  - Function: `add_process_classes_ch22` → `add_process_classes_beverages`
  - Import helpers from `owl_helpers` (IU-1)
- `src/ontology/equivalence_axioms.py` → `src/ontology/equivalence_axioms_beverages.py`
  - Function: `add_ch22_equivalence_axioms` → `add_equivalence_axioms_beverages`
  - Import helpers from `owl_helpers` (IU-1)

**Ontology metadata updates:**
- Ontology IRI slug changes: `eucn-ch22-latest.ttl` → `eucn-ch22-beverages-latest.ttl`
- `owl:versionIRI` pattern: `https://w3id.org/eucn/ch22-beverages/{YYYY}/{MM}/{DD}`
- Chapter ontology label: `"EU CN Chapter 22 — Beverages, spirits and vinegar"@en`

**Tests updated:**
- Rename `test_discriminating_props.py` → `test_discriminating_props_beverages.py`
- Rename `test_product_classes.py` → `test_product_classes_beverages.py`
- Rename `test_process_classes_ch22.py` → `test_process_classes_beverages.py`
- Rename `test_equivalence_axioms.py` → `test_equivalence_axioms_beverages.py`
- Update all imports in test files and `tests/integration/`

**Scenario check:**
- `test_tbox.py` `TestIntegration.test_tbox_has_all_7_process_classes` still passes via registry dispatch
- Acceptance tests in `tests/acceptance/test_chapter22_*.py` filenames unchanged (they test Ch22, not "beverages" concept)

---

### IU-4 — Chapter Registry

**Files changed:**
- `src/ontology/chapter_registry.py` (new)
- `src/ontology/tbox.py` — imports `get_chapter` instead of Ch22 modules directly
- `src/ontology/abox.py` — imports `get_chapter` instead of `add_ch22_equivalence_axioms`

**Registry entry for Ch22:**
- `label`: `"Beverages, spirits and vinegar"`
- `slug`: `"beverages"`
- Four callable fields pointing to renamed functions from IU-3

**`tbox.py` changes:**
- Remove direct imports of `add_discriminating_props`, `add_product_classes_ch22`, `add_process_classes_ch22`
- `build_tbox(g, chapter: int = 22)` — call `build_core_tbox(g)` then dispatch via `get_chapter(chapter)`
- Signature change: `build_tbox` gains a `chapter` parameter (currently it has none)

**`abox.py` changes:**
- Remove direct import of `add_ch22_equivalence_axioms`
- `build_abox(chapter_data, wizard_tree, g, chapter: int)` — dispatch via `get_chapter(chapter)`

**Tests:**
- `tests/unit/test_chapter_registry.py` (new)
- Scenarios: `get_chapter(22)` returns module with slug `"beverages"`; `get_chapter(99)` raises `ValueError`; all four callables are callable; `slug` is kebab-case

---

### IU-5 — Pipeline Output: Core + Chapter TTL with `owl:imports`

**Files changed:**
- `src/pipeline.py` — output file naming + core build step
- `src/ontology/tbox.py` — ontology header declaration updated (see IU-3)

**Pipeline changes:**
- New Step 2.5 (before ontology build): `build_core` — builds `eucn-core` graph, serializes to `data/ontology/eucn-core-latest.ttl` and `eucn-core-{date}.ttl`
- Output file names for chapter: `eucn-ch{N}-{slug}-{date}.ttl` (e.g. `eucn-ch22-beverages-2026-06-08.ttl`)
- `latest` symlink/copy: `eucn-ch{N}-{slug}-latest.ttl`
- Chapter TTL ontology header includes:
  ```turtle
  <https://w3id.org/eucn/ch22-beverages> a owl:Ontology ;
      owl:imports <https://raw.githubusercontent.com/ThHanke/eu-customs-ontology/refs/heads/main/data/ontology/eucn-core-latest.ttl> .
  ```
- For Konclude: merge core graph + chapter graph into single in-memory graph before writing the flat TTL passed to Konclude (no `owl:imports` in that file)

**Demo file update:**
- `demo/ch22-beverages-demo.ttl` — `owl:imports` updated to `eucn-ch22-beverages-latest.ttl`

**Tests:**
- `tests/unit/test_pipeline_output.py` — update TTL filename assertions
- `tests/integration/test_pipeline.py` — update expected filenames

---

### IU-6 — Remove `if chapter == 22` Guard from `pipeline.py`

**File changed:** `src/pipeline.py`

**What to do:**
- Remove lines 187–217 (the `if chapter == 22:` Step 5 block)
- The SPARQL acceptance test belongs in the test suite, not the pipeline
- Pipeline ends after Step 4.5 (Konclude classify)
- `tests/acceptance/test_chapter22_sparql.py` is unchanged — it runs as a pytest test, not from the pipeline

**Rationale:** The acceptance test depends on knowing Ch22 expected MFN rates.
Embedding this in the pipeline creates a chapter-specific branch that can never
be made generic. The test suite is the right place.

**Tests:**
- `tests/unit/test_pipeline.py` — verify no `if chapter ==` branches remain in pipeline source

---

### IU-7 — Investigate Ch23 (Residues, Waste, Animal Feed)

**Objective:** Run the full pipeline on Ch23 with zero code changes (other than IU-1
through IU-6). Document what works, what falls to fallback tier, and what requires
new discriminating properties or process classes.

**Steps (execution-time, not plan-time):**
1. `python -m src.pipeline --chapter 23 --force`
2. Review `data/intermediate/wizard_axiom_coverage_ch23.json`
3. Check Konclude consistency result
4. Count fallback-tier wizard questions
5. Identify any new quantitative units or comparator patterns not in `_QUANT_RE`
6. Determine whether BFO process pattern applies to Ch23 (food manufacturing processes vs. residue characterisation)
7. Propose Ch23-specific discriminating properties and process classes if needed

**Deliverable from IU-7:** A brief markdown note (committed to `docs/plans/` or inline
in the next iteration plan) documenting:
- Wizard coverage percentage for Ch23
- New regex patterns needed (if any)
- Whether a `ChapterModule` for Ch23 was successfully wired

**Expected challenges for Ch23:**
- Ch23 contains many product types defined by composition ratios (protein %, fat %, moisture %)
  rather than production processes — the BFO process pattern may need augmentation
- Quantitative wizard questions may use units (`%`) already in `_QUANT_RE`; dry-matter
  and energy content units (`MJ/kg`, `kcal`) are likely not yet handled
- The root wizard question for Ch23 determines whether the product is a residue/waste vs.
  a prepared compound feed — a structural tree difference from Ch22

---

### IU-8 — CI/CD Update for Multi-Module Build

**Files changed:**
- `.github/workflows/build-release.yml`
- `.github/workflows/docs.yml`
- `.github/cache/core-ttl.sha256` (new, initially empty)

#### `build-release.yml` — `setup` job
No change. Matrix stays as zero-padded chapter numbers. The build job resolves
the slug at runtime from the pipeline's stable output filename.

#### `build-release.yml` — `build` job: `Detect output change` step

Current (fragile — picks arbitrary dated file):
```bash
TTL=$(ls -t data/ontology/eucn-ch${CH}-*.ttl 2>/dev/null | head -1)
```

Replace with (uses stable filename written by pipeline):
```bash
TTL="data/ontology/eucn-ch${CH}-latest.ttl"
if [ ! -f "$TTL" ]; then
  echo "ERROR: pipeline produced no TTL for chapter $CH" >&2; exit 1
fi
CURRENT=$(sha256sum "$TTL" | awk '{print $1}')
CACHED=$(cat .github/cache/ch${CH}-ttl.sha256 2>/dev/null || true)
```

Add core detection after existing chapter check:
```bash
# Core is identical across all parallel chapter jobs — upload same hash from each
CORE_CURRENT=$(sha256sum data/ontology/eucn-core-latest.ttl | awk '{print $1}')
echo "$CORE_CURRENT" > /tmp/core-ttl.sha256
```

Note: `.github/cache/ch${CH}-ttl.sha256` filename is unchanged — it still hashes
`eucn-ch${CH}-latest.ttl` (stable alias written by pipeline alongside slug-named file).

#### `build-release.yml` — `build` job: `Upload ontology files` step

Add core files to the artifact path:
```yaml
path: |
  data/ontology/eucn-ch${{ matrix.chapter }}-*.ttl
  data/ontology/eucn-ch${{ matrix.chapter }}-*.trig
  data/ontology/eucn-core-*.ttl
  data/ontology/eucn-core-*.trig
```

The release job's `merge-multiple: true` deduplicates identical core files from
parallel chapter uploads.

#### `build-release.yml` — `build` job: `Upload updated SHA256` step

Add core hash to the artifact:
```yaml
path: |
  /tmp/ch${{ matrix.chapter }}-ttl.sha256
  /tmp/core-ttl.sha256
if-no-files-found: error
```

The release job's `merge-multiple: true` merges identical `/tmp/core-ttl.sha256`
files from parallel chapter uploads — last-writer-wins, but content is identical.

#### `build-release.yml` — `release` job: `Commit updated SHA256 cache` step

Unchanged. The `git add .github/cache/` sweep picks up the new
`core-ttl.sha256` file automatically.

#### `build-release.yml` — `release` job: `Trigger documentation build` step

Current (single dispatch, broken for multi-chapter):
```yaml
client-payload: >-
  {"version": "...", "chapter": "${{ inputs.chapters || '22' }}"}
```

Replace with a bash loop over all chapter TTLs in the release directory:
```bash
TAG="ontology-${{ steps.date.outputs.value }}-r${{ github.run_number }}"
for LATEST in release-files/eucn-ch*-latest.ttl; do
  # Extract zero-padded chapter number from filename
  CH=$(basename "$LATEST" | grep -oP 'eucn-ch\K\d+')
  gh api repos/${{ github.repository }}/dispatches \
    --method POST \
    --field event_type=trigger-docs \
    --field client_payload="{\"version\":\"$TAG\",\"chapter\":\"$CH\"}"
done
```

This dispatches `trigger-docs` once per released chapter. The docs workflow
`check` job handles the `client_payload.chapter` field unchanged.

#### `docs.yml` — `Resolve TTL file` step

Current (fragile `ls -t` glob):
```bash
TTL=$(ls -t data/ontology/eucn-ch${CH}-*.ttl 2>/dev/null | head -1)
# ...
gh release download "$VERSION" --pattern "eucn-ch${CH}-*.ttl" ...
TTL=$(ls -t /tmp/release-ttl/eucn-ch${CH}-*.ttl 2>/dev/null | head -1)
```

Replace with stable-name lookup:
```bash
# dev build: use committed stable name
TTL="data/ontology/eucn-ch${CH}-latest.ttl"

# release build: download all matching, prefer stable alias
gh release download "$VERSION" --pattern "eucn-ch${CH}-*.ttl" --dir /tmp/release-ttl/
TTL="/tmp/release-ttl/eucn-ch${CH}-latest.ttl"
if [ ! -f "$TTL" ]; then
  # fallback: any slug-named file (older release without stable alias)
  TTL=$(ls -t /tmp/release-ttl/eucn-ch${CH}-*.ttl 2>/dev/null | head -1)
fi
```

Widoco reads title/version metadata from the TTL itself via
`-getOntologyMetadata` — the input filename does not affect HTML output.

**Tests:**
- Manual: trigger `docs.yml` after build; verify `/dev/doc/` updates with new chapter slug in ontology metadata
- Verify release assets contain both `eucn-ch22-beverages-2026-06-08.ttl` and `eucn-ch22-latest.ttl` and `eucn-core-*.ttl`

---

### IU-9 — README and Demo File Updates

**Files changed:**
- `README.md`
- `demo/ch22-beverages-demo.ttl`

**`README.md` changes:**
- Repository layout: update `data/ontology/` entry to show `eucn-ch{N}-{slug}-{date}.ttl`, `eucn-ch{N}-latest.ttl` (stable alias), and new `eucn-core-latest.ttl`
- Pipeline output table: add row `Build core TBox | eucn-core-{date}.ttl`
- CI/CD section: mention core SHA256 cache file `.github/cache/core-ttl.sha256`
- Live Demo `owl:imports` URL: update from `eucn-ch22-latest.ttl` → `eucn-ch22-beverages-latest.ttl`
- Ontosphere link: update raw URL fragment from `eucn-ch22-latest.ttl` → `eucn-ch22-beverages-latest.ttl`
- Ontology Architecture section: update code example and description to reflect `someValuesFrom` (already done in prior session) and note the core/chapter module split

**`demo/ch22-beverages-demo.ttl` changes** (already noted in IU-5 — make explicit):
```turtle
# Before:
owl:imports <.../eucn-ch22-latest.ttl> .
# After:
owl:imports <.../eucn-ch22-beverages-latest.ttl> .
```

**Tests:**
- Verify Ontosphere demo link still resolves (public repo + correct raw URL)

---

## Dependencies and Sequencing

```
IU-1 (helpers)  ─┐
IU-2 (core.py)  ─┤
                  ├→ IU-3 (rename ch22) → IU-4 (registry) → IU-5 (pipeline output)
                  │                                         → IU-6 (remove if-guard)
                  │
                  └→ IU-7 (Ch23 investigation) — unblocked after IU-4+IU-5+IU-6
IU-8 (CI) + IU-9 (README/demo) — after IU-5 and IU-6
```

IU-1 and IU-2 can be done in parallel. IU-3 requires IU-1. IU-4 requires IU-3.
IU-7 requires IU-4 through IU-6 (all pipeline changes) to be meaningful.
IU-8 and IU-9 require IU-5 (new filenames and `owl:imports`) to be complete first.

---

## Test Scenarios Summary

| Unit | Key scenarios |
|---|---|
| `owl_helpers` | `_bnode` determinism; `_cls` triple count; `_cn_heading` restriction shape; `_disjoint_pairs` N*(N-1) triples; `_neg_hasvalue_from_disjoint_equiv` skips BNode values; all helpers idempotent |
| `core.py` | 5 core entities present; `producedBy` FunctionalProperty; `cnHeadingCode` range xsd:string; idempotent; standalone rdflib load valid |
| `chapter_registry` | `get_chapter(22)` returns slug `"beverages"`; `get_chapter(99)` raises; all callables callable |
| `tbox.py` | `build_tbox(g, 22)` graph has core entities + beverages entities; `build_tbox(g, 99)` raises |
| `pipeline_output` | output filename contains slug; `owl:imports` triple present in chapter TTL; Konclude input TTL has no `owl:imports`; `eucn-ch{N}-latest.ttl` stable alias written |
| `core_output` | `eucn-core-latest.ttl` written; contains `producedBy` FunctionalProperty; no chapter-specific triples |
| CI/workflows | release assets include `eucn-core-*.ttl`; `.github/cache/core-ttl.sha256` committed; docs triggered per-chapter |
| Existing acceptance tests | All pass unchanged after rename — `test_chapter22_*.py` filenames need no change |

---

## Risks

| Risk | Mitigation |
|---|---|
| `tbox.py` callers that pass no `chapter` arg break when signature gains `chapter` param | Add `chapter: int = 22` default; all existing callers continue to work |
| Konclude gets the `owl:imports` triple in the merged flat TTL and tries to resolve it | Strip `owl:imports` triples from merged TTL before writing for Konclude (add one-line filter in pipeline) |
| Raw GitHub URL for core changes (branch rename, repo move) | Single constant `CORE_RAW_URL` in `src/ontology/core.py`; update one place |
| Ch23 BFO process pattern does not apply | Document in IU-7 findings; wizard-only axioms (no process classes needed) are valid; `add_process_classes` can be a no-op |
| Two chapter modules define the same `eucn:Foo` class name | Both define it identically (same IRI) — OWL semantics merge them; add a lint check that catches non-identical redefinitions |

---

## Out-of-Scope Deferral

- **Shared discriminating properties across chapters:** Only move to core when a second chapter actually uses the same property. No premature generalisation.
- **Combined multi-chapter ontology file:** Each chapter ships separately. A consumer-facing combined file (`eucn-all-latest.ttl`) that `owl:imports` all chapters is a future deliverable.
- **w3id.org content negotiation for `owl:imports`:** Current raw GitHub URL is sufficient. Revisit after stable public release.
- **Wizard fallback NLP:** Coverage gaps addressed per-chapter by extending `_QUANT_RE` or adding curated equivalence axioms.
