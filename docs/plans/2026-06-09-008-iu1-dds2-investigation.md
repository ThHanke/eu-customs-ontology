---
title: "IU1: EU DDS2 HTML + UK API Investigation Findings"
plan: "2026-06-09-008-feat-taric-dds2-core-entities-pipeline-plan.md"
date: 2026-06-09
status: complete
---

# IU1: EU DDS2 HTML + UK API Investigation Findings

## EU DDS2 JSP

The EU TARIC DDS2 JSP (`ec.europa.eu/taxation_customs/dds2/taric/measures.jsp`) is an
HTML-only JSP with server-side template rendering. No public JSON or XHR API exists.
The HTML page renders: nomenclature hierarchy table, measures table with type/rate/area/
validity columns, footnotes section, and regulatory references. Scraping is feasible but
fragile (no stable element IDs). **EU DDS2 scraper deferred** per plan scope.

## UK Trade Tariff API v2 — Confirmed Structure

Endpoint: `GET https://www.trade-tariff.service.gov.uk/api/v2/commodities/{10d}`

Returns JSON:API with two top-level keys:
- `data` — the commodity node
- `included` — flat array of all related entities (resolved references)

### `data.attributes` fields
```
producline_suffix, description, number_indents, goods_nomenclature_item_id,
basic_duty_rate, validity_start_date, validity_end_date, declarable
```

### `included` entity types and counts (2203000100 sample)
| type | count |
|------|-------|
| measure | 71 |
| geographical_area | 276 |
| duty_expression | 71 |
| measure_condition | 48 |
| measure_condition_permutation | 41 |
| measure_condition_permutation_group | 17 |
| measure_type | 11 |
| legal_act | 19 |
| footnote | 18 |
| additional_code | 7 |
| measure_component | 58 |
| measurement_unit | 1 |
| section | 1 |
| chapter | 1 |
| heading | 1 |
| commodity | 1 |

### Measure entity fields

**attributes**: `origin`, `import`, `export`, `id` (integer SID), `effective_start_date`,
`effective_end_date`, `excise`, `vat`, `reduction_indicator`, `meursing`,
`resolved_duty_expression`, `universal_waiver_applies`

**relationships** (JSON:API `data` refs):
`duty_expression`, `measure_type` (→ id string e.g. `"103"`), `legal_acts` (array),
`measure_conditions` (array), `measure_components` (array), `geographical_area`,
`footnotes` (array), `order_number` (quota, absent if no quota), `preference_code`,
`excluded_countries` (array), `measure_condition_permutation_groups`

### measure_type fields
```json
{
  "id": "103",
  "attributes": {
    "id": "103",
    "description": "Third country duty",
    "measure_type_series_id": "C",
    "measure_component_applicable_code": 1,
    "order_number_capture_code": 2,
    "trade_movement_code": 0,
    "validity_start_date": "1972-01-01T00:00:00.000Z",
    "validity_end_date": null,
    "measure_type_series_description": "Applicable duty"
  }
}
```

Confirmed measure types in 2203000100:
| id | description | series |
|----|-------------|--------|
| 103 | Third country duty | C |
| 109 | Supplementary unit | O |
| 142 | Tariff preference | C |
| 305 | Value added tax | P |
| 306 | Excises | Q |
| 750 | Import control of organic products | B |

### geographical_area fields
```json
{"id": "AD", "attributes": {"id": "AD", "description": "Andorra", "geographical_area_id": "AD", "geographical_area_sid": 140}}
```
ERGA OMNES = `id: "1011"`. Has `relationships.children_geographical_areas` listing 276 child areas.

### footnote fields
```json
{"id": "TN207", "attributes": {"code": "TN207", "description": "...", "formatted_description": "..."}}
```
Confirmed: TN207 (North Korea sanctions — UK version), TN701 (Crimea), CD808 (organic cert note)

### measure_condition fields
```json
{
  "id": "20287079",
  "attributes": {
    "condition_code": "B",
    "document_code": "C644",
    "action": "Import allowed",
    "action_code": "26",
    "condition_duty_amount": null,
    "condition_measurement_unit_code": null,
    "measure_condition_class": "document",
    "requirement": "Other certificates: Certificate of Inspection for Organic Products..."
  }
}
```
`measure_condition_class`: `document`, `exemption`, `negative`, `threshold`

### additional_code fields
```json
{"id": -1009345122, "attributes": {"code": "X301", "description": "Low Alcohol - not exc 1.2%"}}
```
**Note**: internal `id` is negative integer SID; use `attributes.code` for IRI minting.

### legal_act (regulation) fields
```json
{
  "id": "P2014301",
  "attributes": {
    "regulation_code": "S.I. 2020/1430",
    "regulation_url": "https://www.legislation.gov.uk/uksi/2020/1430",
    "description": "The Customs Tariff (Establishment) (EU Exit) Regulations 2020",
    "validity_start_date": "2021-01-01T00:00:00.000Z",
    "validity_end_date": null,
    "officialjournal_number": "1",
    "officialjournal_page": 1,
    "published_date": null,
    "role": 1
  }
}
```

### duty_expression fields
```json
{"id": "20002426-duty_expression", "attributes": {"base": "0.00 %", "formatted_base": "<span>0.00</span> %", "verbose_duty": "0.00%"}}
```
IRI key: measure SID with `-duty_expression` suffix; ID is `{measure_id}-duty_expression`.

### heading + section
- heading: `goods_nomenclature_item_id: "2203000000"`, `description: "Beer made from malt"`
- section: `numeral: "IV"`, `title: "Prepared foodstuffs; beverages, spirits and vinegar..."`

## Divergence Findings

### `origin` field on measures
`origin: "eu"` does NOT mean EU-authoritative. It means the measure was ported from EU TARIC
at Brexit. UK-specific measures also show `origin: "eu"`. Do not use `origin` for isUKOnly.

### isUKOnly heuristics
- Type 305 (VAT) and 306 (Excise) are always UK-specific — no EU equivalent
- Legal acts with `regulation_code` matching `S.I. ` prefix are UK secondary legislation
- Legal act `P2014301` (`S.I. 2020/1430`) = UK Customs Tariff establishment — UK-only
- Measure type 750 (organic import control) applies to ERGA OMNES with 33 EU countries
  in `excluded_countries` — UK-specific adaptation of EU Regulation 2018/848

### Plan correction: organic certificate code
Plan text mentions `D808` for organic cert. Actual UK API data:
- Condition `document_code: "C644"` = Certificate of Inspection for Organic Products
- Footnote code `"CD808"` = a footnote about organic certification requirements
Use `C644` (not `D808`) for the organic certificate individual in IU2/IU3/IU7.

### Additional codes
X301–X366 series are UK excise category codes (introduced post-Brexit for UK duty calculation).
These are UK-specific and should be flagged `isUKOnlyMeasure=true` on any measure using them.

## JSON:API Traversal Strategy

To build a flat `TARICMeasure` from the response:
1. Build a lookup dict: `{(type, id): attrs}` from `included`
2. For each measure in `included` where `type == "measure"`:
   - Resolve `relationships.measure_type.data.id` → measure_type attrs
   - Resolve `relationships.geographical_area.data.id` → area attrs
   - Resolve `relationships.duty_expression.data.id` → duty attrs
   - Resolve `relationships.legal_acts.data[]` → list of legal_act attrs
   - Resolve `relationships.measure_conditions.data[]` → list of condition attrs
   - Resolve `relationships.footnotes.data[]` → list of footnote attrs
   - Resolve `relationships.order_number.data` (if present) → quota number
   - Resolve `relationships.excluded_countries.data[]` → list of area codes

## Scraping Feasibility Verdict

EU DDS2 HTML: scraping is feasible but fragile. Deferred. UK API is the correct primary
source for entity model design. Ch22 MFN rates are identical EU/UK (0% third country duty).
Preferential rates and sanction measures require the `isUKOnly` flag for safety.

## 10-digit Code Padding

UK API accepts both 8-digit and 10-digit codes in the URL path. `2203000100` (10-digit)
and `22030001` (8-digit) both return the same commodity. Safe to use 10-digit codes
(append `"00"` to 8-digit CN codes as planned).
