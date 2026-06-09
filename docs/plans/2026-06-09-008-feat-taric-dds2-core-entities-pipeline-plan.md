---
title: "feat: TARIC DDS2 as source of truth — core entity expansion and pipeline integration"
type: feat
status: active
date: 2026-06-09
---

# feat: TARIC DDS2 as source of truth — core entity expansion and pipeline integration

## Overview

The EU TARIC DDS2 portal (`ec.europa.eu/taxation_customs/dds2/taric/measures.jsp`) exposes the
full TARIC entity graph per commodity code: the complete ancestor hierarchy (Section → Chapter →
Heading → Subheading → CN → TARIC), applicable regulatory measures (tariff rates, import
restrictions, licence requirements), conditions, certificates, footnotes, geographic scopes, and
their legal bases (Regulations/Decisions).

The pipeline currently models only a thin slice of this — `TARICMeasure` as a flat data record
with `dutyRate`, `geographicScope`, and `regulationId` strings. The full TARIC entity model
requires ~10 additional named OWL classes and richer ABox triples.

This plan (a) investigates the DDS2 HTML structure and confirms scrapeability, (b) adopts the UK
Trade Tariff API v2 as the clean JSON proxy for entity model design (same TARIC3 schema, pre-2021
codes unchanged), (c) expands the core ontology with the missing entity classes, (d) adds a
`fetch-commodity-details` pipeline step, and (e) enriches the ABox and agent context.

**Legal text discipline**: The EU CLASS API remains the sole authoritative source for CN
classification guidance notes (the "lex" content that drives discriminating axioms). TARIC DDS2 /
UK API are for regulatory measures and nomenclature hierarchy only. These two layers must never
be conflated.

## Problem Frame

The current ABox models `TARICMeasure` as a flat record: duty rate, geographic scope, regulation
ID. This loses:

- **Measure type semantics** — "suspension" (142) vs "MFN duty" (103) vs "licence condition"
  (762) are fundamentally different entity types, not just values of a string property
- **Geographic area as a named entity** — ERGA OMNES, named trade blocs, individual countries
  are reusable across measures; a string property forces re-assertion on every measure
- **Conditions and certificates** — import licence requirements (D/C/Y prefix codes), certificate
  conditions, threshold conditions (quantity, price), and their OR/AND logic are invisible
- **Footnotes** — legal annotations (TN207 North Korea sanctions, TN701 rice) that restrict the
  scope of a measure are dropped
- **Hierarchy** — `eucn:Section` (Roman numeral sections) is absent; `eucn:Heading` exists as a
  class stub but is never populated in the ABox
- **Quota references** — 6-digit quota order numbers that gate preferential duty rates are not
  modelled

Without these entities the ontology cannot express "this beer commodity is subject to a 0% MFN
tariff for all origins, with an organic certificate requirement (D808) for the organic sub-code,
and a North Korea sanctions prohibition (TN207)".

## Requirements Trace

- R1. Confirm EU DDS2 HTML structure and scrapeability for ch22 sample codes
- R2. Confirm UK Trade Tariff API v2 as clean JSON proxy for pre-Brexit codes
- R3. Identify divergence risk: UK post-2021 measures that do not apply to EU
- R4. Add named OWL entity classes for all missing TARIC entity types
- R5. Build `src/fetcher/uk_trade_tariff_api.py` returning the full entity graph per commodity
- R6. Add `fetch-commodity-details` pipeline step with filesystem cache
- R7. Enrich `src/ontology/abox.py` to emit richer triples for all new entities
- R8. Update `src/agent/prompts/axiom_agent_system.txt` to expose new entity vocabulary

## Scope Boundaries

- No changes to the EU CLASS API fetch or the classification notes / discriminating axiom pipeline
- No changes to the EZT-Online wizard scraper
- No EU DDS2 HTML scraper in this plan (UK API proxy covers the entity model; DDS2 scraping is
  a separate risk item — see Deferred)
- Measure conditions and certificate requirements are modelled as named OWL individuals, not
  complex OWL class restrictions (those belong in a future agent prompt update)
- No attempt to reconcile EU/UK measure divergence algorithmically — flag-field only

### Deferred to Separate Tasks

- EU DDS2 HTML scraper (for EU-authoritative measures on post-2021 codes): evaluate after UK API
  coverage confirmed; implement as a separate PR
- MeasureCondition → OWL restriction mapping (expressing "import only if certificate D808
  present" as a class restriction): future agent prompt update
- Quota allocation tracking (whether a quota is exhausted): out of scope for ontology
- Section-level class hierarchy auto-generation from TARIC section labels: separate PR

## Context & Research

### Relevant Code and Patterns

- `src/ontology/tbox.py` — existing `TARICMeasure`, `CNCode`, `TARICCode`, `Chapter`,
  `Heading` definitions; `_class()`, `_obj_prop()`, `_data_prop()` helpers
- `src/ontology/core.py` — `Packaging`, `Volume`, `SmallContainer`, `LargeContainer`,
  `producedBy`, `inLitres`
- `src/ontology/abox.py` — `_add_measure()` and `_ensure_cn_code()` — patterns to follow for
  new entity ABox builders
- `src/ontology/iri.py` — `mint_iri(key)` for deterministic IRIs; follow existing key
  conventions (`cn:{code}`, `measure:{sid}`)
- `src/schema/taric.py` — `TARICMeasure`, `MeasureComponent`, `ChapterData`; extend models here
- `src/fetcher/tariffnumber_api.py` — pattern for a thin httpx fetcher with no auth and
  per-request rate-limit sleep; follow this for UK API fetcher
- `src/fetcher/class_api.py` — pattern for cache-to-filesystem (JSONL checkpoint), staleness
  check, force-refresh flag; follow for `fetch-commodity-details` cache

### External References

- UK Trade Tariff API v2 docs: `https://docs.trade-tariff.service.gov.uk/`
- UK API commodity endpoint: `GET https://www.trade-tariff.service.gov.uk/api/v2/commodities/{10d}`
  returns JSON:API with `section`, `chapter`, `heading`, `measures`, `duty_expression`,
  `measure_conditions`, `footnotes`, `geographical_area`, `certificates`
- TARIC3 XML Explanation (CIRCABC): measure type series A–F; condition codes; certificate type prefixes
- EU DDS2 JSP parameters: `Lang`, `Taric`, `SimDate`, `Area`, `MeasureType`, `AdditionalCode`
  (HTML only — no public JSON API confirmed)
- Confirmed divergence date: UK measures diverged from EU on 2021-01-01; use
  `validity_start >= 2021-01-01` as a divergence risk signal

## Key Technical Decisions

- **UK API as primary JSON source (not EU DDS2 HTML scraping)**: The UK Trade Tariff API v2
  returns the full TARIC3 entity graph as clean JSON. For Ch22/Ch23 codes (beverages, feed
  residues) the EU/UK measures are largely identical pre-2021. EU DDS2 HTML scraping is deferred
  as a risk item because the JSP has no stable XHR JSON endpoint and is template-rendered.
  Rationale: unblock entity modelling now with clean data; add EU-authoritative scraper later.

- **Divergence flag on TARICMeasure**: Add `eucn:isUKOnlyMeasure xsd:boolean` datatype property.
  Set to `true` for measures with `validity_start >= 2021-01-01` AND UK-specific regulations.
  Consumers can filter. Rationale: preserves data without silently corrupting EU ontology.

- **Named OWL individuals for GeographicArea, MeasureType, Certificate**: These are fixed
  controlled vocabularies in TARIC (ERGA OMNES, named blocs, D/C/Y-prefix codes). Modelling as
  named individuals with `rdf:type eucn:GeographicArea` (rather than strings) enables SPARQL
  joins and future OWL restrictions. Rationale: clean KB design; TARIC controlled vocabularies
  are stable.

- **Footnotes as named individuals linked to measures**: `rdf:type eucn:Footnote` with
  `eucn:footnoteCode`, `rdfs:label`, `skos:definition`. Many measures share the same footnote
  (TN207 for North Korea sanctions) — individual reuse is correct. Rationale: avoids data
  duplication; enables querying "all measures with footnote TN207".

- **Extend `TARICMeasure` schema model for new fields**: Add `footnotes`, `conditions`,
  `additional_codes`, `quota_order_number` to `src/schema/taric.py`; populate from UK API
  response. Keeps the schema the single source of truth for what we fetch vs. what we model.

- **Separate `fetch-commodity-details` step from `fetch-taric`**: `fetch-taric` reads CIRCABC
  XLSX bulk measures. The new step fetches the rich per-commodity graph from UK API. Keeps
  concerns separated; bulk XLSX stays as fallback for codes the UK API lacks (e.g., post-2021
  EU-only codes).

## Open Questions

### Resolved During Planning

- **Does the UK API have Beer (2203)?** Yes — `2203000100` confirmed working with full measure
  graph including MFN 0%, organic certificate D808, North Korea footnote TN207.
- **Does the EU DDS2 JSP have a JSON API?** No — confirmed HTML-only JSP with server-side
  template substitution.
- **Are Ch22 beer/wine measures identical EU/UK?** MFN duty rates (0%) are identical.
  Preferential rates (EPA agreements, CARIFORUM) may differ. Sanction measures (North Korea)
  are shared. Use divergence flag for safety.
- **Are footnotes stable enough for named individuals?** Yes — `TN207`, `TN701` etc. are
  official TARIC footnote codes with permanent IDs.

### Deferred to Implementation

- Exact mapping of all TARIC measure type IDs (103, 105, 142, 762, ...) to human-readable
  labels and OWL subclasses: enumerate from UK API response during IU3 implementation
- How many unique geographic area codes appear across Ch22/Ch23: discover in IU5 from
  actual API response
- Whether to add `owl:sameAs` links between EUCN individuals and UK Trade Tariff IRI
  references: evaluate during IU5

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not
> implementation specification. The implementing agent should treat it as context, not code
> to reproduce.*

**New OWL entity graph per commodity code (after this plan):**

```
eucn:ind/cn-22030001  rdf:type eucn:CNCode
  eucn:hasMeasure  eucn:ind/measure-ABC
  eucn:belongsToHeading  eucn:ind/heading-2203
  eucn:belongsToChapter  eucn:ind/chapter-22
  eucn:belongsToSection  eucn:ind/section-IV

eucn:ind/measure-ABC  rdf:type eucn:TARICMeasure
  eucn:hasMeasureType  eucn:MeasureType103          # named individual: MFN duty
  eucn:hasGeographicArea  eucn:GeographicAreaERGAOMNES
  eucn:hasDutyExpression  eucn:ind/duty-ABC
  eucn:hasCondition  eucn:ind/cond-ABC-D808
  eucn:hasFootnote  eucn:FootnoteTN207
  eucn:hasRegulation  eucn:ind/reg-R1237-16
  eucn:isUKOnlyMeasure  false

eucn:ind/duty-ABC  rdf:type eucn:DutyExpression
  eucn:dutyAmount  0.0
  eucn:dutyRate  "0.0 %"
  eucn:hasMeasurementUnit  eucn:MeasurementUnitAD_VALOREM

eucn:ind/cond-ABC-D808  rdf:type eucn:MeasureCondition
  eucn:conditionCode  "D"
  eucn:hasCertificate  eucn:CertificateD808

eucn:FootnoteTN207  rdf:type eucn:Footnote
  eucn:footnoteCode  "TN207"
  rdfs:label  "Products originating in North Korea..."@en
```

**Pipeline step order after this plan:**

```
fetch-taric (XLSX bulk)
  ↓
fetch-commodity-details (UK API → per-code rich JSON, cached)
  ↓
build-heading-labels (tariffnumber.com → bilingual labels)
  ↓
fetch-legal-text (CLASS API → classification notes, EU-authoritative lex)
  ↓
run-axiom-agent (LLM, reads CLASS API notes only)
  ↓
build-core
  ↓
build-ontology (uses rich measure schema + heading classes + agent axioms)
```

## Implementation Units

- [ ] **IU1: Investigate EU DDS2 HTML structure and confirm UK API coverage**

**Goal:** Establish empirically (a) what the EU DDS2 JSP HTML structure looks like for ch22
sample codes and (b) that the UK Trade Tariff API v2 returns equivalent measures.

**Requirements:** R1, R2, R3

**Dependencies:** None

**Files:**
- Create: `docs/plans/2026-06-09-008-iu1-dds2-investigation.md` (findings doc)
- No code changes

**Approach:**
- Fetch `ec.europa.eu/taxation_customs/dds2/taric/measures.jsp?Lang=en&Taric=22030001&SimDate=20260609`
  and `?Taric=22090011` via Playwright or httpx; parse and document the HTML sections:
  hierarchy table structure, measures table structure, footnotes section
- Fetch `https://www.trade-tariff.service.gov.uk/api/v2/commodities/2203000100` and
  `2209001100`; document the JSON response fields that map to entities in the HTML
- Cross-reference measure type IDs (103, 142, 762, etc.) between the two sources
- Document any EU/UK divergence found in the sample codes
- Record: which HTML elements are stable (IDs, class names, nesting) and which are fragile

**Test scenarios:**
- Test expectation: none — investigation output, not code

**Verification:**
- Findings doc written; EU DDS2 HTML sections mapped to UK API JSON fields; divergence
  cases documented; scraping feasibility verdict written

---

- [ ] **IU2: Expand `src/schema/taric.py` with full TARIC3 entity models**

**Goal:** Add Pydantic models for `MeasureType`, `GeographicArea`, `DutyExpression`,
`MeasureCondition`, `Certificate`, `Footnote`, `AdditionalCode`, `Regulation`.
Extend `TARICMeasure` with lists of conditions, footnotes, additional codes, quota reference.

**Requirements:** R4

**Dependencies:** IU1 (know which fields the UK API returns)

**Files:**
- Modify: `src/schema/taric.py`
- Test: `tests/unit/test_taric_schema.py`

**Approach:**
- New frozen Pydantic models: `MeasureTypeRecord`, `GeographicAreaRecord`,
  `DutyExpression`, `MeasureConditionRecord`, `CertificateRecord`, `FootnoteRecord`,
  `AdditionalCodeRecord`, `RegulationRecord`
- Each model has a stable `code` or `id` field that drives IRI minting
- `TARICMeasure` gains: `footnotes: list[FootnoteRecord]`,
  `conditions: list[MeasureConditionRecord]`, `additional_codes: list[AdditionalCodeRecord]`,
  `quota_order_number: str | None`, `is_uk_only: bool = False`
- `ChapterData` unchanged — it wraps `list[TARICMeasure]`
- All new fields optional with defaults for backward compat with existing XLSX pipeline

**Patterns to follow:**
- Existing `MeasureComponent`, `TARICMeasure` in `src/schema/taric.py`
- `ConfigDict(frozen=True)` on all models

**Test scenarios:**
- Happy path: parse a complete UK API commodity response into the full model graph (all new
  fields populated)
- Edge case: `TARICMeasure` with no conditions, no footnotes — new fields default to empty list
- Edge case: `quota_order_number` absent → `None`
- Happy path: `is_uk_only=True` when `validity_start >= 2021-01-01`

**Verification:**
- All new models import cleanly; `model_validate_json` round-trips on sample UK API response

---

- [ ] **IU3: Add new OWL entity classes and properties to `src/ontology/tbox.py` and `src/ontology/core.py`**

**Goal:** Declare all missing TARIC entity classes and their properties in the TBox.

**Requirements:** R4

**Dependencies:** IU1 (entity list confirmed), IU2 (model fields known)

**Files:**
- Modify: `src/ontology/tbox.py`
- Modify: `src/ontology/core.py` (if any entity belongs in chapter-agnostic core)
- Test: `tests/unit/test_tbox.py` (new class presence assertions)

**Approach:**

New OWL classes (add to `build_tbox` via existing `_class()` helper):

| IRI | Label EN | Label DE | Parent | Notes |
|-----|---------|----------|--------|-------|
| `eucn:TARICSection` | TARIC Section | TARIC-Abschnitt | – | Roman-numeral top-level group |
| `eucn:TARICSubheading` | TARIC Subheading | TARIC-Unterposition | `eucn:CNCode` | 6-digit level |
| `eucn:MeasureType` | Measure Type | Maßnahmetyp | – | Controlled vocabulary individual |
| `eucn:GeographicArea` | Geographic Area | Geografisches Gebiet | – | Country, bloc, or ERGA OMNES |
| `eucn:DutyExpression` | Duty Expression | Zollausdruck | – | Rate + unit + measurement unit |
| `eucn:MeasureCondition` | Measure Condition | Maßnahmebedingung | – | Certificate or threshold |
| `eucn:Certificate` | Certificate | Zertifikat | – | D/C/Y-prefix codes |
| `eucn:Footnote` | Footnote | Fußnote | – | TN-prefix annotation |
| `eucn:AdditionalCode` | Additional Code | Zusatzcode | – | 4-char; trade remedy / authorised use |
| `eucn:Regulation` | Regulation | Verordnung | – | EU Regulation or Decision |
| `eucn:MeasurementUnit` | Measurement Unit | Maßeinheit | – | ASV, HLT, SPR, etc. |

New object properties (add to `build_tbox` via `_obj_prop()` helper):
- `eucn:belongsToHeading` (CNCode → Heading)
- `eucn:belongsToSection` (Chapter → TARICSection)
- `eucn:hasMeasureType` (TARICMeasure → MeasureType)
- `eucn:hasGeographicArea` (TARICMeasure → GeographicArea)
- `eucn:hasDutyExpression` (TARICMeasure → DutyExpression)
- `eucn:hasCondition` (TARICMeasure → MeasureCondition)
- `eucn:hasFootnote` (TARICMeasure or CNCode → Footnote)
- `eucn:hasRegulation` (TARICMeasure → Regulation)
- `eucn:hasCertificate` (MeasureCondition → Certificate)
- `eucn:hasAdditionalCode` (TARICMeasure → AdditionalCode)
- `eucn:hasMeasurementUnit` (DutyExpression → MeasurementUnit)

New datatype properties:
- `eucn:measureTypeCode` (xsd:string) — numeric code e.g. "103"
- `eucn:measureTypeSeries` (xsd:string) — series A–F
- `eucn:areaCode` (xsd:string) — ISO 3166-1 or TARIC group code
- `eucn:footnoteCode` (xsd:string) — TN-prefix code
- `eucn:conditionCode` (xsd:string) — D/C/Y etc.
- `eucn:additionalCodeValue` (xsd:string) — 4-char
- `eucn:quotaOrderNumber` (xsd:string) — 6-digit
- `eucn:regulationRef` (xsd:string) — Regulation/Decision ID
- `eucn:hasMeasurementUnit` (DutyExpression → MeasurementUnit) — already listed above
- `eucn:isUKOnlyMeasure` (xsd:boolean) — divergence flag

**Patterns to follow:**
- All existing `_class()`, `_obj_prop()`, `_data_prop()` calls in `build_tbox()`
- EN + DE labels + `skos:definition` for every new entity

**Test scenarios:**
- Happy path: `build_tbox(Graph(), chapter=22)` completes without error; all new class IRIs
  present in graph
- Happy path: new object properties have correct domain and range assertions
- Edge case: running `build_tbox` twice (idempotency) — no duplicate triples

**Verification:**
- `len(g)` increases by expected triple count; all new IRIs queryable via SPARQL

---

- [ ] **IU4: Build `src/fetcher/uk_trade_tariff_api.py`**

**Goal:** Thin httpx client for the UK Trade Tariff API v2 returning structured data
for a commodity code, with filesystem cache and staleness tracking.

**Requirements:** R5

**Dependencies:** IU2 (schema models defined)

**Files:**
- Create: `src/fetcher/uk_trade_tariff_api.py`
- Test: `tests/unit/test_uk_trade_tariff_api.py`

**Approach:**
- `fetch_commodity(code_10d: str, cache_dir: Path, force: bool = False) -> dict`
  — checks `{cache_dir}/{code_10d}.json`; if absent or `force`, calls
  `GET https://www.trade-tariff.service.gov.uk/api/v2/commodities/{code_10d}`
  — writes raw JSON to cache, returns parsed dict
- `parse_commodity_measures(raw: dict) -> list[TARICMeasure]`
  — maps JSON:API response to `TARICMeasure` list (including new fields from IU2)
  — sets `is_uk_only=True` for measures where regulation date >= 2021-01-01
- `fetch_chapter_commodities(chapter: int, cn_codes: list[str], cache_dir: Path, ...) -> dict[str, list[TARICMeasure]]`
  — batch wrapper: pads 8-digit CN codes to 10 digits (append "00"), fetches each,
  rate-limits to 200 ms between requests
- No auth required; `timeout=20`; retry once on 5xx

**Patterns to follow:**
- `src/fetcher/tariffnumber_api.py` rate-limit sleep pattern
- `src/fetcher/class_api.py` filesystem cache + `force` flag pattern

**Test scenarios:**
- Happy path: `parse_commodity_measures` on fixture JSON for `2203000100` → correct
  `TARICMeasure` list with footnotes and conditions populated
- Happy path: cache hit — file present, no HTTP call made
- Edge case: 8-digit CN code padded correctly to 10 digits
- Edge case: code with no conditions → `conditions=[]`
- Error path: API returns 404 → empty list returned, warning logged (code may be
  UK-only or defunct)

**Verification:**
- Unit tests pass; `fetch_commodity("2203000100", tmp_path)` returns non-empty list
  without network call on second invocation

---

- [ ] **IU5: Add `fetch-commodity-details` pipeline step to `src/pipeline.py`**

**Goal:** Integrate the UK API fetcher as a new pipeline step between `fetch-taric` and
`build-heading-labels`. Cache results per chapter. Output enriches `ChapterData`.

**Requirements:** R6

**Dependencies:** IU4

**Files:**
- Modify: `src/pipeline.py`
- Modify: `src/pipeline.py` → `main()` argument parser (add `--skip-commodity-details`)

**Approach:**
- New step label: `fetch-commodity-details`
- Cache: `data/intermediate/uk_tariff_ch{chapter:02d}/` directory (one JSON per commodity code)
- Input: wizard tree terminal `cn_codes` (8-digit), padded to 10-digit for UK API
- Output: updates `chapter_data.measures` with enriched `TARICMeasure` objects (new fields
  populated from UK API); also writes enriched JSON back to
  `data/intermediate/taric_ch{chapter:02d}_enriched.json`
- Gate: `force or not enriched_json.exists()` — skip if cached
- New CLI flag: `--skip-commodity-details` (mirrors `--skip-fetch`)
- Print summary: `{N} codes fetched, {M} is_uk_only flagged`

**Patterns to follow:**
- `fetch-taric` step structure in `run()` — guard + `_step()` context manager + skip print
- `fetch-legal-text` step filesystem cache pattern

**Test scenarios:**
- Happy path: step runs, enriched JSON written, count logged
- Edge case: `--skip-commodity-details` flag skips without error
- Edge case: chapter has zero terminal wizard nodes — step completes with 0 codes fetched

**Verification:**
- `data/intermediate/uk_tariff_ch22/` populated; `taric_ch22_enriched.json` written

---

- [ ] **IU6: Enrich `src/ontology/abox.py` with full entity ABox builders**

**Goal:** Replace flat TARICMeasure ABox triples with the full entity graph: named individuals
for MeasureType, GeographicArea, DutyExpression, MeasureCondition, Certificate, Footnote,
Regulation.

**Requirements:** R7

**Dependencies:** IU3 (TBox classes declared), IU5 (enriched schema available)

**Files:**
- Modify: `src/ontology/abox.py`
- Test: `tests/unit/test_abox.py`

**Approach:**

Refactor `_add_measure(g, measure, cn_code_iri)` to:

1. `_ensure_measure_type(g, type_code)` → `eucn:ind/mtype-{code}` with
   `rdf:type eucn:MeasureType`, `eucn:measureTypeCode`, `rdfs:label`
2. `_ensure_geographic_area(g, area_code)` → `eucn:ind/area-{code}` with
   `rdf:type eucn:GeographicArea`, `eucn:areaCode`, `rdfs:label`
3. `_ensure_footnote(g, fn)` → `eucn:ind/footnote-{fn.code}` with
   `rdf:type eucn:Footnote`, `eucn:footnoteCode`, `rdfs:label`, `skos:definition`
4. `_ensure_certificate(g, cert)` → `eucn:ind/cert-{cert.code}` with
   `rdf:type eucn:Certificate`
5. `_ensure_regulation(g, reg)` → `eucn:ind/reg-{hash(reg.ref)}` with
   `rdf:type eucn:Regulation`, `eucn:regulationRef`
6. `_add_duty_expression(g, measure_iri, component)` → `eucn:ind/duty-{measure_iri_frag}`
   with `rdf:type eucn:DutyExpression`, `eucn:dutyAmount`, `eucn:dutyRate`
7. `_add_measure_condition(g, measure_iri, cond)` → `eucn:ind/cond-{hash(cond)}`
   with `rdf:type eucn:MeasureCondition`, `eucn:conditionCode`, linked certificate

All `_ensure_*` helpers are idempotent (check triple existence before adding).

Also add: `_ensure_heading(g, cn_code_iri, heading_4d)` linking
`eucn:belongsToHeading <heading_iri>` from the existing heading class IRIs.

**Patterns to follow:**
- Existing `_ensure_cn_code()` idempotency pattern
- `mint_iri(key)` for all new individual IRIs (deterministic keys: `mtype:103`,
  `area:1011`, `footnote:TN207`, `cert:D808`, `reg:{regulationId}`)

**Test scenarios:**
- Happy path: `_add_measure()` with full `TARICMeasure` (footnotes, conditions, additional
  codes) — all new individual triples present in graph
- Happy path: two measures share the same footnote TN207 → only one `Footnote` individual
  in graph (idempotency)
- Happy path: two measures share GeographicArea ERGA OMNES → one individual
- Edge case: `TARICMeasure.conditions = []` → no `MeasureCondition` triples added
- Edge case: `is_uk_only=True` → `eucn:isUKOnlyMeasure true` triple present

**Verification:**
- `build_abox()` on ch22 data produces graph with all new entity types populated; no
  duplicate IRI conflicts

---

- [ ] **IU7: Update agent system prompt with new entity vocabulary**

**Goal:** Extend `src/agent/prompts/axiom_agent_system.txt` so the LLM knows about the
new named entities (MeasureType, GeographicArea, Footnote, Certificate) and can reference
them in axioms.

**Requirements:** R8

**Dependencies:** IU3 (TBox classes declared)

**Files:**
- Modify: `src/agent/prompts/axiom_agent_system.txt`
- Test: `tests/unit/test_axiom_agent_system_prompt.py` (prompt loads, key sections present)

**Approach:**

Add a new section **"Regulatory entity vocabulary"** after the BFO parthood/quality section:

```
### Regulatory entity vocabulary
The TBox includes named individuals for TARIC regulatory entities.
Reference them by IRI when a restriction should attach to a specific measure or condition:

**MeasureType**: eucn:MeasureType103 (MFN third-country duty), eucn:MeasureType105
  (authorised use), eucn:MeasureType142 (tariff suspension), eucn:MeasureType762
  (licence condition). IRI pattern: eucn:MeasureType{code}

**GeographicArea**: eucn:GeographicAreaERGAOMNES (all third countries),
  eucn:GeographicAreaGB (United Kingdom), eucn:GeographicAreaUA (Ukraine).
  IRI pattern: eucn:ind/area-{area_code}

**Certificate**: eucn:CertificateD808 (organic import cert),
  eucn:CertificateC640 (CITES permit). IRI pattern: eucn:ind/cert-{code}

**Footnote**: eucn:FootnoteTN207 (North Korea sanctions),
  eucn:FootnoteTN701 (rice safeguard). IRI pattern: eucn:ind/footnote-{code}

Do NOT invent measure type codes or footnote codes. Only reference individuals
that appear in the running TBox context provided to you.
```

**Patterns to follow:**
- Existing SmallContainer/LargeContainer examples in the prompt
- Existing BFO guidance section style

**Test scenarios:**
- Happy path: new section present in loaded prompt file; `"MeasureType"` substring found
- Happy path: running TBox section populated with real named individuals → agent cites them
  correctly in a test invocation (integration test, optional/skip if no API key)

**Verification:**
- Prompt file loads; section present; no existing sections regressed

## System-Wide Impact

- **TBox hash change**: adding new classes to `build_tbox()` changes `compute_tbox_hash()`
  → all agent node cache files become stale → full re-run of `run-axiom-agent` required
  after IU3 is merged. Document this explicitly in the IU3 verification step.
- **ABox triple count**: adding full entity graph will increase triple count significantly.
  Run Konclude consistency check after IU6 to confirm OWL 2 DL compliance.
- **`is_uk_only` flag discipline**: any consumer of `TARICMeasure` ABox triples must be
  made aware of the flag. Add note to `README` or `data/ontology/` notes.
- **Unchanged invariants**: EU CLASS API notes pipeline, wizard axiom transformer, and
  `NodeAxiomSet` / `AxiomCandidate` schema are not modified by this plan.
- **`tariffnumber_api.py` heading labels step**: this step (added in preceding session) uses
  labels only, not measures. It is unaffected but should run before `fetch-commodity-details`
  to avoid redundant heading fetches.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| UK/EU measure divergence silently corrupts EU ontology | `isUKOnlyMeasure` flag + documentation; EU DDS2 scraper as follow-up |
| UK API rate limiting or availability | 200 ms sleep; retry on 5xx; filesystem cache means one fetch per code ever |
| JSP HTML structure changes break any future EU DDS2 scraper | Deferred; build only after structure confirmed in IU1 |
| New OWL entities make ontology inconsistent | Konclude check after IU6; all new entities are simple named individuals, low DL risk |
| Agent re-run after TBox hash change (~1h per chapter) | Expected; document; do not merge IU3 + IU7 separately |
| 10-digit padding for CN codes (8-digit + "00") is wrong for some codes | Verify in IU1 against actual UK API; UK API may also accept 8-digit |

## Documentation / Operational Notes

- After IU3 merge: delete `data/axiom_candidates/ch22/node_*.jsonl` and re-run agent
  (`--force --run-axiom-agent`) to pick up new TBox vocabulary
- `isUKOnlyMeasure=true` triples are informational only; downstream SPARQL queries should
  filter with `FILTER(?isUKOnly = false)` for EU-applicable measures
- Cache location: `data/intermediate/uk_tariff_ch{N}/` — add to `.gitignore`

## Sources & References

- Related code: `src/ontology/tbox.py`, `src/ontology/abox.py`, `src/schema/taric.py`
- UK Trade Tariff API: `https://docs.trade-tariff.service.gov.uk/`
- UK commodity endpoint: `https://www.trade-tariff.service.gov.uk/api/v2/commodities/2203000100`
- EU DDS2 TARIC portal: `https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp`
- TARIC3 XML explanation: `https://circabc.europa.eu` (requires login)
- Existing data source memory: `memory/reference_taric_dds2.md`, `memory/reference_tariffnumber_api.md`
