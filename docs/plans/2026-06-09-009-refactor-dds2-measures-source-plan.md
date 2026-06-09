---
title: "refactor: replace UK Trade Tariff API with EU TARIC DDS2 + XLSX-only measures"
type: refactor
status: active
date: 2026-06-09
---

# refactor: replace UK Trade Tariff API with EU TARIC DDS2 + XLSX-only measures

## Overview

The `fetch-commodity-details` pipeline step currently calls the UK Trade Tariff API v2 to enrich
TARIC measure records with rich entity sub-graphs (MeasureType descriptions, GeographicArea names,
footnotes, conditions). Post-Brexit, this source diverges from EU TARIC: 78% of returned ch22
measures are UK-only (type 305/306 VAT/Excise, S.I. regulations, adapted sanction coverage).
The ontology should only contain EU-applicable measures.

This plan (a) replaces the UK API with EU TARIC DDS2 as the measure source, (b) populates the
previously-declared-but-empty `TARICSection` ABox using the DDS2 nomenclaturetree static JS
file, and (c) removes the `is_uk_only` divergence flag that is no longer needed.

**Legal text discipline preserved**: The EU CLASS API remains the sole source for CN classification
guidance notes. DDS2 is for regulatory measures and nomenclature hierarchy only. These layers
must never be conflated.

## Problem Frame

- UK API returns 78% UK-only measures for ch22 (VAT type 305, Excise type 306, S.I. regulations)
- UK API returns HTTP 404 for ~5% of ch22 codes that post-Brexit the UK has dropped from its CN
- `TARICSection` class is declared in TBox (lines 177-182 of `src/ontology/tbox.py`) and
  `belongsToSection` property (line 292) exist but are never instantiated in the ABox
- `isUKOnlyMeasure` data property (TBox line 500) and `is_uk_only: bool` field in
  `TARICMeasure` schema are UK-specific scaffolding that should not exist in an EU ontology

## Requirements Trace

- R1. Stop calling the UK Trade Tariff API; use EU TARIC DDS2 measures data instead
- R2. Populate `TARICSection` individuals and `belongsToSection` chapter-to-section links
- R3. Remove `is_uk_only` / `isUKOnlyMeasure` from schema, TBox, and ABox
- R4. DDS2 scraping must handle "deferred" responses gracefully (some wine codes with many
  measures are redirected to a human email form — these must not raise, just log + return empty)
- R5. All ch22 integration tests pass; XLSX-only ABox fallback paths remain functional
- R6. Filesystem cache pattern matches existing (`cache_dir / f"{code_10d}.json"`, `force` flag)

## Scope Boundaries

- No changes to EU CLASS API, EZT wizard scraper, or classification note pipeline
- No EU TARIC XML bulk download replacement — XLSX from CIRCABC remains the primary flat
  measure source; DDS2 provides hierarchy and description enrichment
- No attempt to back-fill historical UK-only measures or map UK→EU measure IDs
- No MeasureCondition → OWL class restriction mapping (future agent prompt update)
- `uk_trade_tariff_api.py` is deleted (not merely skipped); old cache files documented for
  manual deletion by operator
- DDS2 scraping limited to `measures_details.jsp` (two-step with Sid extraction);
  `measures_conditions.jsp` per-SID condition fetch is deferred to a follow-up plan

## Research Summary

### DDS2 Endpoint Architecture (confirmed 2026-06-09)

**Section hierarchy** — `nomenclaturetree_en_YYYYMMDD.js`:
```
GET https://ec.europa.eu/taxation_customs/dds2/taric/nomenclaturetree/nomenclaturetree_en_{date}.js
```
Returns a JavaScript assignment `sectiontree = [...];chapterfootnotes = [...];` where the array
is pure JSON (no eval needed). Strip the assignment prefix with a regex, `json.loads` the rest.
Array structure: `[has_children, "SECTION I", "description", [[ch_entry], ...], ...]` where each
chapter entry is `[has_children, "CHAPTER N", "description", "NN00000000", footnotes_or_null]`.
The date in the filename must match the `SimDate` query parameter (format YYYYMMDD).
German (`_de_`) and English (`_en_`) variants available with identical structure.

**Measures** — two-step with Sid token:
```
Step 1: GET measures.jsp?Lang=en&Taric={code_10d}&SimDate={YYYYMMDD}
        → HTML iframe src contains Sid= session token
Step 2: GET measures_details.jsp?Sid={sid}&Taric={code_10d}&Offset=0&Lang=en&...
        → Full measures HTML (74KB for beer 2203000100, 0 bytes deferred for high-count codes)
```
The Sid is a server-side session token embedded in the iframe `src` attribute. It must be
extracted before the second request — it is not guessable or deterministic.

**HTML structure of measures_details.jsp** (confirmed scraped fields):
- Measure SID: `<div id="measure_{SID}">` wrapper around each measure — SID is an integer
- Measure type description: text content of `td_measure_description to_highlight` cell before
  `<span>(date</span>` — e.g., "Third country duty", "Tariff preference". Code NOT available.
- Duty rate: `<span class="duty_rate">0 %</span>` (absent if measure has no rate)
- Validity: `<span>(DD-MM-YYYY&nbsp;-&nbsp;)</span>` or `(DD-MM-YYYY&nbsp;-&nbsp;DD-MM-YYYY)`
- Regulation ID: `<a id="db_regulation_id_..." style="display: none;">{R_CODE}</a>` hidden anchor
- Geographic area: section header `<div class="measure_area">` with text "(Name CODE)" e.g.
  "(ERGA OMNES 1011)" — both the name and numeric code are parseable from this text
- Import/export: `<img title="Measures for&nbsp;import">` vs `Measures for&nbsp;export`
- Footnote text: JavaScript array `pageDisplayedFootnotes=new Array(new Array("CD808", new
  Footnote("CD808", "text...", ...)))` in the `<script>` block — extractable by regex

**Measure type code limitation**: DDS2 HTML does not expose the numeric measure type code
("103", "142"). Only the description is present. Strategy: enrich from XLSX data by SID match
where available; use description-only `MeasureTypeRecord` (code="", description="...") for
DDS2-only measures. The `MeasureType` IRI is minted from code, so description-only records
use the description slug as IRI fragment (or are omitted if IRI would collide).

**Deferred measures**: For commodity codes with many measures (e.g., many wine codes in ch22),
`measures.jsp` returns an iframe pointing to `deferred_measures.jsp` instead of
`measures_details.jsp`. Fetching `deferred_measures.jsp` returns an email-form HTML page
(unusable for automation). Detection: check whether the iframe `src` contains
`deferred_measures.jsp`. When detected: log a warning and return an empty measure list;
the XLSX-only fallback paths in `abox.py` already handle this correctly (the flat XLSX
measure records are used without DDS2 enrichment).

**Measure type code — practical mitigation**: The XLSX `taric_ch22.json` already has correct
EU measure type codes (e.g., `measure_type_id="103"`). The DDS2 measures fetch adds
descriptions on top. For codes that hit the deferred limit, the XLSX provides codes with no
descriptions (existing XLSX-only fallback). This is acceptable for the OWL ontology — the
IRI is minted from the code, and `rdfs:label` is optional.

### Existing XLSX-only Fallback Paths (already in abox.py)

```python
# When measure_type is None but measure_type_id present:
elif measure.measure_type_id:
    mt_iri = _ensure_measure_type(g, MeasureTypeRecord(code=measure.measure_type_id, description=""))
    g.add((iri, EUCN.hasMeasureType, mt_iri))

# Same pattern for geographic area, regulation
```
These paths were added in the previous session's gap-fix commit (`fffb76e`). They are
correct and sufficient for the XLSX-only case.

## Patterns to Follow

- `src/fetcher/tariffnumber_api.py` — filesystem cache pattern (`cache_dir / f"{code}.json"`,
  `force` flag, `time.sleep(0.2)`, httpx usage)
- `src/fetcher/uk_trade_tariff_api.py` — public interface to preserve: `fetch_chapter_commodities(chapter, cn_codes, cache_dir, force) -> dict[str, list[TARICMeasure]]`
- `src/ontology/abox.py` `_ensure_*` helpers — naming and signature convention
- `src/ontology/tbox.py` `_class()`, `_obj_prop()`, `_data_prop()` builder helpers

---

## Implementation Units

### IU1 — DDS2 nomenclaturetree Section hierarchy fetcher

**Goal**: Parse `nomenclaturetree_en_YYYYMMDD.js` and return a typed mapping of
section name → list of chapter codes, with bilingual labels.

**Files**:
- Create: `src/fetcher/taric_dds2.py`
- Create: `tests/unit/test_taric_dds2.py`

**Approach**:
- `fetch_nomenclaturetree(lang: str, sim_date: date, cache_dir: Path, *, force: bool) -> list[SectionEntry]`
  — GET the JS file, cache it as `nomenclaturetree_{lang}_{sim_date:%Y%m%d}.js`, return parsed entries
- Strip `sectiontree = ` prefix and trailing `;\n...` with `re.sub(r'^sectiontree\s*=\s*', '', content).split(';')[0]`
  then `json.loads()`
- `SectionEntry`: dataclass/Pydantic with `roman_numeral: str`, `label_en: str`, `label_de: str | None`,
  `chapter_codes: list[str]` (2-digit strings, e.g., `["22"]`)
- Map `"CHAPTER 22"` → `"22"` by stripping prefix and zero-padding
- Bilingual: call with `lang="en"` and `lang="de"` separately, merge by index

**Test Scenarios**:
- Parse fixture JS string (sample two-section, three-chapter subset) → correct SectionEntry list
- Chapter 22 maps to the "Beverages…" section (Section IV)
- Roman numeral preserved as-is: "IV"
- `chapter_codes` normalised to 2-digit zero-padded strings: `"01"` not `"1"`
- Cache file written on first call; second call reads cache (no network)
- `force=True` re-downloads even when cache exists

**Verification**: `pytest tests/unit/test_taric_dds2.py -k nomenclaturetree` passes without network

---

### IU2 — ABox TARICSection population

**Goal**: Instantiate `TARICSection` individuals in the ABox and wire chapters to their section
via `eucn:belongsToSection`.

**Files**:
- Modify: `src/ontology/abox.py` — add `_ensure_section()`, extend `build_abox()` signature
- Modify: `src/pipeline.py` — pass section data to `build_abox()`
- Modify: `tests/integration/test_pipeline.py` — verify section individuals appear in TTL

**Approach**:
- `_ensure_section(g: Graph, roman: str, label_en: str, label_de: str | None) -> URIRef`
  — mint IRI via `section_iri(roman)` (new helper in `src/ontology/iri.py`); add
  `rdf:type EUCN.TARICSection`, `rdfs:label` triples
- `build_abox(chapter_data, wizard_tree, graph, *, section_entries=None)` — if `section_entries`
  is provided, find the section matching the chapter number, create the section individual, then
  call `g.add((chapter_iri(chapter), EUCN.belongsToSection, section_iri(roman)))` for each
  chapter in that section
- `section_iri(roman: str) -> URIRef` added to `src/ontology/iri.py`

**Test Scenarios**:
- `build_abox()` with `section_entries=[SectionEntry(roman="IV", ...chapter_codes=["22"]...)]`
  → TTL contains `eucn:section:IV rdf:type eucn:TARICSection`
- Chapter IRI `eucn:chapter:22` has `eucn:belongsToSection eucn:section:IV`
- Calling `build_abox()` without `section_entries` (default `None`) → no section triples,
  no error (backwards-compatible)
- Idempotent: calling twice produces same triple count

**Verification**: `pytest tests/integration/test_pipeline.py -k section` passes;
`grep TARICSection data/ontology/eucn-ch22-*.ttl` is non-empty after re-running pipeline

---

### IU3 — DDS2 measures_details.jsp two-step fetcher

**Goal**: Fetch EU-authoritative measures per commodity code from DDS2 and map to
`TARICMeasure` Pydantic records. Handle deferred codes gracefully.

**Files**:
- Modify: `src/fetcher/taric_dds2.py` — add `fetch_commodity_measures()` and helpers
- Modify: `tests/unit/test_taric_dds2.py` — add measures fetch tests

**Approach**:
- `fetch_commodity_measures(code_10d: str, sim_date: date, cache_dir: Path, *, force: bool) -> list[TARICMeasure]`
  — cache as `cache_dir / f"{code_10d}.json"`; returns `[]` on deferred or error
- Step 1: GET `measures.jsp?Lang=en&Taric={code}&SimDate={date}` → parse `<iframe` src for Sid
  - Detect deferred: if iframe src contains `deferred_measures.jsp` → log warning, cache `[]`, return `[]`
  - If no iframe found → log warning, return `[]`
- Step 2: GET `measures_details.jsp?Sid={sid}&Taric={code}&Offset=0&Lang=en&SimDate={date}`
  → parse HTML
- HTML parsing:
  - Extract footnote map from `pageDisplayedFootnotes` JS array: `{code: description}`
  - For each `<div id="measure_{SID}">`:
    - `sid` from div id
    - `measure_type_description` from text in `td_measure_description` (before date span)
    - `duty_rate_str` from `<span class="duty_rate">` (if present)
    - Validity: parse `(DD-MM-YYYY&nbsp;-&nbsp;[DD-MM-YYYY])` span
    - `regulation_id` from hidden `<a id="db_regulation_id_...">` anchor
    - `geographical_area_id`, `geographical_area_description` from parent `<div class="measure_area">`
      section header text pattern `r'\(([^()]+)\s+(\d+)\)\s*$'`
    - `is_import` from img title text
  - Build `TARICMeasure` records with populated fields:
    - `sid`: from HTML
    - `commodity_code`: parameter passed in (code_10d)
    - `measure_type_id`: `""` (not in HTML; left blank; XLSX provides this)
    - `measure_type`: `MeasureTypeRecord(code="", description=measure_type_description)`
    - `geographical_area_id`: parsed code e.g. "1011"
    - `geographical_area`: `GeographicAreaRecord(code=..., description=...)`
    - `validity_start`: parsed date
    - `validity_end`: parsed date or None
    - `regulation_id`: parsed code
    - `regulations`: `[RegulationRecord(regulation_id=...)]` if non-empty
    - `footnotes`: list of `FootnoteRecord` from the footnote map for codes in parentheses
    - `is_uk_only`: removed (IU4)
- `time.sleep(0.2)` between Step 1 and Step 2 (rate limit)
- Use `httpx.Client` with shared session cookie across both requests

**Test Scenarios**:
- Parse fixture HTML (measures_details.jsp sample for 2203000100) → 17 TARICMeasure records
- SID "2146370" maps to "Third country duty", duty_rate "0 %", area code "1011"
- Deferred iframe → empty list returned, no exception raised
- Missing iframe → empty list returned, warning logged
- Footnote text extracted from `pageDisplayedFootnotes` JS and linked to measure via `(CD808)` reference
- Cache written as JSON; second call skips HTTP
- `force=True` re-fetches

**Verification**: `pytest tests/unit/test_taric_dds2.py -k measures` passes;
fixture HTML stored at `tests/fixtures/dds2_measures_2203000100.html`

---

### IU4 — Pipeline: replace fetch-commodity-details step

**Goal**: Pipeline `fetch-commodity-details` step calls DDS2 fetcher instead of UK API.
The public interface `fetch_chapter_commodities(chapter, cn_codes, cache_dir, force)` is
preserved so callers remain unchanged.

**Files**:
- Modify: `src/pipeline.py` — swap import; pass section_entries to `build_abox()`
- Modify: `src/fetcher/taric_dds2.py` — add `fetch_chapter_commodities()` wrapper
- Delete: `src/fetcher/uk_trade_tariff_api.py`
- Modify: `tests/integration/test_pipeline.py` — update mock patches; add section assertion

**Approach**:
- Add `fetch_chapter_commodities(chapter: int, cn_codes_8d: list[str], cache_dir: Path, *, force: bool) -> dict[str, list[TARICMeasure]]` in `taric_dds2.py`
  — pads codes to 10d with `"00"` suffix; calls `fetch_commodity_measures()` per code;
  returns `{code_8d: measures}` matching the UK API interface exactly
- Pipeline `fetch-commodity-details` step: change `from src.fetcher.uk_trade_tariff_api import ...`
  → `from src.fetcher.taric_dds2 import fetch_chapter_commodities`
- Remove `uk_only_count` stat line from pipeline logging (no longer meaningful)
- Add nomenclaturetree fetch to pipeline and pass `section_entries` to `build_abox()`:
  ```python
  from src.fetcher.taric_dds2 import fetch_section_hierarchy
  section_entries = fetch_section_hierarchy("en", extract_date, DATA_INTERMEDIATE)
  ```
  Keep this non-blocking: if nomenclaturetree fetch fails, log warning and continue with
  `section_entries=None` (ABox section population is skipped gracefully)
- `uk_trade_tariff_api.py` deleted; operator note in commit message: delete
  `data/intermediate/uk_tariff_ch22/` cache directory

**Test Scenarios**:
- `test_fixture_pipeline_produces_ttl` continues to pass (fixture has no DDS2 calls; skip flag)
- New: `test_fetch_commodity_details_calls_dds2` — patches `taric_dds2.fetch_chapter_commodities`,
  confirms it is called not `uk_trade_tariff_api`
- New: `test_pipeline_section_entities_in_ttl` — patches nomenclaturetree fetch with fixture
  SectionEntry list; confirms TTL contains `TARICSection` and `belongsToSection` triples
- `test_run_axiom_agent_missing_api_key_raises` unchanged (independent of this refactor)

**Verification**: `pytest tests/integration/test_pipeline.py` all pass;
`grep isUKOnlyMeasure data/ontology/eucn-ch22-*.ttl` returns nothing after re-run

---

### IU5 — Schema + TBox cleanup: remove is_uk_only / isUKOnlyMeasure

**Goal**: Delete `is_uk_only` from `TARICMeasure`, `isUKOnlyMeasure` from TBox and ABox.
These are UK-API artifacts with no place in an EU ontology.

**Files**:
- Modify: `src/schema/taric.py` — remove `is_uk_only: bool = False` field
- Modify: `src/ontology/tbox.py` — remove `isUKOnlyMeasure` data property block (lines ~500-509)
- Modify: `src/ontology/abox.py` — remove the `is_uk_only` conditional block (lines 214-215)
- Modify: `src/fetcher/uk_trade_tariff_api.py` — N/A (file deleted in IU4)
- Modify: `tests/` — update any fixtures that set `is_uk_only=True` to remove the field

**Approach**: Mechanical deletion. Search for all occurrences of `is_uk_only` and
`isUKOnlyMeasure` and remove. Run full test suite to confirm no silent breakage.

**Test Scenarios**:
- `TARICMeasure(sid="1", commodity_code="2203000100", ...)` no longer accepts `is_uk_only` kwarg
- TBox graph built by `build_tbox()` does not contain `eucn:isUKOnlyMeasure` triple
- ABox graph from `build_abox()` with fixture data has zero `isUKOnlyMeasure` triples

**Verification**: `pytest` full suite passes; `grep -r is_uk_only src/` returns nothing

---

## Deferred to Implementation

- `measures_conditions.jsp?MeasureSid={SID}&Lang=en&SimDate={date}` — per-SID condition fetch
  (condition details are lazy-loaded via AJAX in the browser). Not scraped in this plan; existing
  MeasureCondition records from XLSX remain. A follow-up plan should add this endpoint.
- Pagination: `Offset` parameter in `measures_details.jsp`. For ch22, confirmed single-page
  (17 measures for beer). Implementation should check for a "next page" indicator and handle it,
  but can defer pagination for codes that already hit `deferred_measures.jsp`.
- `data/intermediate/uk_tariff_ch22/` cache directory: operator deletes manually after IU4
  commit; not automated to avoid accidental rm -rf in CI.
- Bilingual section labels: IU1 fetches English only in the first version; German merged in a
  follow-up (call with `lang="de"`, merge into `SectionEntry.label_de`).

## Sequencing

IU5 → IU1 → IU2 → IU3 → IU4

IU5 first: remove the UK-only field before any new DDS2 records are created (prevents accidental
`is_uk_only=True` contamination in fixtures). IU1 before IU2 (ABox needs the helper). IU3 before
IU4 (pipeline calls the new fetcher). All units can be committed independently.
