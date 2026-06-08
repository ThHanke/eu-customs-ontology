---
id: "2026-06-08-006"
title: "Legal-text-driven OWL axiom generation with CLASS API, hashed provenance, and candidate registry"
status: active
created: 2026-06-08
type: feature
---

# Legal-text-driven OWL axiom generation

## Problem

OWL equivalence axioms in `src/ontology/equivalence_axioms_*.py` are hand-authored from memory. No traceability to legal text. When the annual CN Regulation changes, there is no way to detect which axioms are stale. Adding a new chapter requires manual authoring from scratch.

## Goal

Replace manually-authored equivalence axioms with agent-generated candidates derived from EU CN Explanatory Notes via the EU CLASS REST API, with `ingestionDate`-based provenance linking each axiom to the exact official legal clause. Build warns when source note is updated.

## Scope

- **In:** CLASS API client, `LegalSection` schema, `AxiomCandidate` schema, rule-based extractor, LLM agent fallback, candidate registry (JSONL), staleness detection, pipeline integration, migration of Ch22/Ch23 axioms.
- **Out:** ABox (TARIC measures), wizard scraping, process/product class authoring (still manual).

## Approval flow

Auto-apply. When `ingestionDate` of a source note changes on re-fetch, affected candidates are marked `stale`. Build warns (non-fatal) listing stale candidates. Re-run extractor or manually edit `data/axiom_candidates/ch{N}.jsonl` to re-confirm.

---

## Key data source: EU CLASS REST API

Discovered via reverse-engineering the Angular app at `https://webgate.ec.europa.eu/class-public-ui-web/`.

**Search endpoint:**
```
POST https://webgate.ec.europa.eu/class-public-ui-rest/api/consultation/searchSecondLevel
Content-Type: application/json

{
  "language": "en",          # or "de" for German labels
  "simDate": "2026-06-08",
  "informationTypes": ["CN"],
  "cnCodes": [{"valueType": "RANGE", "valueFrom": "2200000000", "valueTo": "2299999999"}]
}
```

**Response shape (verified):**
```json
{
  "totalCnNotes": 52,
  "cnNotes": [
    {
      "cnCode": "220820",
      "noteDescrSnippet": "Spirits obtained by distilling grape wine or grape marc...",
      "noteType": "CNEN HS Subheading Notes",
      "noteId": "82da68aabc8aa51fa036b486fb7ec6a4",
      "ingestionDate": "2023-10-06",
      "language": "en"
    },
    ...
  ]
}
```

**Note types present in Chapter 22:**
- `CN Section Notes` — section-level scope
- `CN Chapter Notes` — chapter exclusions
- `CN Chapter General Notes` — container size distinctions
- `CN Chapter Additional Notes` — ABV measurement methodology
- `CN Chapter Subheading Notes` — sparkling wine pressure criteria
- `CNEN HS Heading Notes` — heading-level classification criteria (primary source)
- `CNEN HS Subheading Notes` — subheading criteria (primary source)
- `CNEN CN Subheading Notes` — CN-level criteria (primary source)

**Staleness signal:** `ingestionDate` per note. If re-fetch returns a newer `ingestionDate`, the note was updated by the Commission → mark all candidates derived from that `noteId` as `stale`.

**Full note PDF:** `GET /api/classification/getNotesById?referenceId={noteId}` → returns `{"base64": "..."}` (PDF). Use for human review; not required for automated extraction.

**Language support:** all 23 EU languages. Query `en` for extraction, `de` for German labels.

---

## Architecture overview

```text
CLASS REST API (official EU)
        ↓ POST searchSecondLevel per chapter  (language: "en" + "de")
  ClassApiClient  →  data/legal_text/ch{N}/notes.jsonl  (LegalSection per note, bilingual)
        ↓
        ├─── AnnotationBuilder ──────────────────────────────────────────────────────────────┐
        │    (note resources + skos:definition per language + eucn:hasExplanatoryNote links) │
        │                                                                                    ↓
        │                                                                             Graph (annotations)
        │
        └─── AxiomExtractor  (ingestionDate as version key)
               ├── RuleBasedExtractor  (numeric thresholds, process names — regex)
               └── LLMAxiomAgent       (complex criteria, scope exclusions)
                       ↓
               CandidateRegistry  →  data/axiom_candidates/ch{N}.jsonl
                       ↓ status filter (not stale)
               build_equivalence_axioms_from_candidates(g, active_candidates)
                       ↓
                equivalence axioms in Graph
```

---

## Implementation units

### IU1 — `src/schema/legal_text.py`: LegalSection model

**New file.**

```python
class LegalSection(BaseModel):
    note_id: str            # CLASS noteId (stable identifier)
    chapter: int
    cn_code: str            # e.g. "220820", "2208", "22" — as returned by CLASS
    note_type: str          # e.g. "CNEN HS Subheading Notes"
    source_text: str        # noteDescrSnippet — verbatim from CLASS API
    source_text_hash: str   # SHA256(source_text)
    ingestion_date: str     # CLASS ingestionDate — version key for staleness
    language: str           # "en" | "de" | ...
    source_url: str         # https://webgate.ec.europa.eu/class-public-ui-web/#/search (canonical)
    fetched_at: str         # ISO date of our fetch
```

`source_text_hash = SHA256(source_text)` — detects if the snippet text itself changed even if `ingestionDate` stayed the same (defensive).

Staleness trigger: `ingestion_date` changed on re-fetch **or** `source_text_hash` changed.

**Test file:** `tests/unit/test_schema_legal_text.py`

Test scenarios:
- `source_text_hash` equals `hashlib.sha256(source_text.encode()).hexdigest()`
- Pydantic rejects missing required fields
- `cn_code` accepts 2–10 digit strings (chapter-level through CN-code-level)
- `note_type` is unconstrained string (future-proofs against CLASS adding new types)

---

### IU2 — `src/schema/axiom_candidate.py`: AxiomCandidate model

**New file.**

```python
class AxiomCandidate(BaseModel):
    candidate_id: str       # SHA256(chapter:owl_class:restriction_type:property_iri:value:facet)
    chapter: int
    owl_class: str          # EUCN IRI suffix, e.g. "Beer", "WhiskySpirit"
    restriction_type: Literal["someValuesFrom", "hasValue", "decimalRange", "complement"]
    property_iri: str       # e.g. "eucn:producedBy"
    value: str              # class IRI suffix, literal, or threshold (as str)
    facet: str | None       # "minExclusive"|"maxInclusive"|"minInclusive"|"maxExclusive"
    source_note_id: str     # FK → LegalSection.note_id
    source_text: str        # verbatim triggering clause
    source_text_hash: str   # SHA256(source_text) — copied at extraction time
    source_ingestion_date: str  # CLASS ingestionDate at extraction time
    status: Literal["proposed", "approved", "stale"]
    confidence: float       # 0.0–1.0
    extractor: str          # "rule-based" | "llm-agent" | "manual"
    extracted_at: str       # ISO date
```

`candidate_id` deterministic: `sha256(f"{chapter}:{owl_class}:{restriction_type}:{property_iri}:{value}:{facet or ''}")`.

**Test file:** `tests/unit/test_schema_axiom_candidate.py`

Test scenarios:
- `candidate_id` deterministic for same semantic content
- Different `value` → different `candidate_id`
- `restriction_type` rejects unknown values
- `confidence` rejected outside 0.0–1.0
- `status` only accepts 3 values

---

### IU3 — `src/fetcher/class_api.py`: ClassApiClient

**New file.** Pure `httpx` — no Playwright, no scraping.

```python
BASE_URL = "https://webgate.ec.europa.eu/class-public-ui-rest/api"

def fetch_chapter_notes(
    chapter: int,
    out_dir: Path,
    *,
    languages: list[str] = ("en", "de"),  # both languages fetched
    sim_date: str | None = None,           # defaults to today
    force: bool = False,
) -> list[LegalSection]:
    """Fetch CN Notes for chapter in all requested languages, write to data/legal_text/ch{N}/notes.jsonl."""
```

Implementation:
1. For each language in `languages`, POST `{BASE_URL}/consultation/searchSecondLevel` with:
   - `informationTypes: ["CN"]`
   - `cnCodes: [{"valueType": "RANGE", "valueFrom": f"{chapter:02d}00000000", "valueTo": f"{chapter:02d}99999999"}]`
2. Parse `cnNotes` array from response; build `LegalSection` per note (language stored in model)
3. Checkpoint keyed on `(note_id, language)`: skip if both present and `ingestion_date` unchanged
4. If `ingestion_date` changed for an existing `(note_id, language)`: update record — caller detects staleness
5. Return combined list of `LegalSection` across all languages

Also expose:
```python
def fetch_note_pdf(note_id: str) -> bytes:
    """Fetch full note PDF via /classification/getNotesById?referenceId={note_id}."""
```

**Error handling:** `httpx.HTTPStatusError` on non-200 → raise with note_id in message. Retry once on 5xx.

**Rate limiting:** 1 req/s sleep between requests (CLASS has no documented rate limit but be polite).

**Test file:** `tests/unit/test_fetcher_class_api.py`

Test scenarios (mock `httpx`):
- Successful fetch (two languages) → `LegalSection` list contains both `en` and `de` rows for same `note_id`
- Checkpoint keyed on `(note_id, language)`: same `note_id` + same `ingestion_date` → skipped per language independently
- `ingestion_date` changed for `en` only → `en` record updated, `de` record unchanged
- API 420 error → raises `ValueError` with chapter in message
- Response shape validated: missing `noteId` key → `KeyError` surfaced cleanly

---

### IU4 — `src/agent/rule_extractor.py`: RuleBasedExtractor

**New file.** Non-LLM first pass. Same as originally planned, now operates on `LegalSection.source_text`.

**Note type priority** (only these contain classification criteria):
- `CNEN HS Subheading Notes` — highest priority: explicit process/property criteria
- `CNEN CN Subheading Notes` — CN-level refinements
- `CNEN HS Heading Notes` — heading-level general criteria
- `CN Chapter Additional Notes` — numeric thresholds (ABV measurement rules)
- `CN Chapter Subheading Notes` — sparkling wine pressure, other quantitative criteria

Skip: `CN Chapter Notes` (exclusions — used for `complement` type only), `CN Section Notes` (too broad).

**Pattern registry:**

| Regex pattern | Restriction type | Property | Notes |
|---|---|---|---|
| `alcoholic strength by volume( of)?\s*(not exceeding\|exceeding\|less than\|not less than)\s*(\d+(?:\.\d+)?)\s*%` | `decimalRange` | `eucn:alcoholByVolumePercent` | Extract operator + value |
| `in containers holding (\d+(?:\.\d+)?)\s*litres? or less` | `decimalRange` | `eucn:maxContainerVolumeL` | `maxInclusive` |
| `obtained by( the)? distillation of (grape wine\|grape marc\|malted barley\|grain\|fruit\|sugar cane)` | `someValuesFrom` | `eucn:producedBy` | Map phrase → process class |
| `obtained by( the)? fermentation of (grape\|malt\|grain\|fruit\|sugar)` | `someValuesFrom` | `eucn:producedBy` | Map phrase → process class |
| `\b(not )?carbonated\b` | `hasValue` | `eucn:isCarbonated` | bool |
| `\bdenatured\b` | `hasValue` | `eucn:isDenatured` | `True` |
| `excess pressure of not less than (\d+(?:\.\d+)?)\s*bar` | `decimalRange` | `eucn:pressureBar` | `minInclusive` |

**Process name lookup table** (maps legal text phrase → EUCN class suffix):
```python
PROCESS_MAP = {
    "distillation of grape wine": "GrapeDistillation",
    "distillation of grape marc": "GrapeDistillation",
    "distilling grape wine": "GrapeDistillation",
    "fermentation of malted barley": "MaltFermentation",
    "fermented from malted barley": "MaltFermentation",
    "fermentation of grapes": "GrapeFermentation",
    "fermented grape": "GrapeFermentation",
    "distillation of grain": "GrainDistillation",
    "fermented from grain": "GrainDistillation",
    "distilling ... sugar cane": "SugarCaneDistillation",
    # extend per chapter
}
```

**Confidence scoring:**
- Exact threshold match with operator keyword: 0.95
- Process name exact match: 0.90
- Partial match / ambiguous operator: 0.70

**Test file:** `tests/unit/test_agent_rule_extractor.py`

Test scenarios:
- `"alcoholic strength by volume not exceeding 2.8%"` → `decimalRange`, `maxInclusive`, `"2.8"`
- `"obtained by distilling grape wine"` → `someValuesFrom`, `GrapeDistillation`
- `"in containers holding 2 litres or less"` → `decimalRange`, `maxContainerVolumeL`, `maxInclusive`, `"2.0"`
- `"carbonated"` → `hasValue`, `isCarbonated`, `"true"`
- `"not carbonated"` → `hasValue`, `isCarbonated`, `"false"`
- `"excess pressure of not less than 3 bar"` → `decimalRange`, `pressureBar`, `minInclusive`, `"3.0"`
- Note with no matching pattern → empty list, no exception
- Note type `CN Chapter Notes` → skipped (returns empty list)

---

### IU5 — `src/agent/llm_agent.py`: LLMAxiomAgent

**New file.** Claude API fallback for complex criteria.

When invoked: sections where rule-based returned empty or confidence < 0.7.

**API:** `claude-sonnet-4-6` via `anthropic` SDK.

**System prompt** includes:
- Available `restriction_type` values and their semantics
- Available process class IRI suffixes loaded from chapter module at runtime
- Available data property IRI suffixes per chapter
- Instruction: return a JSON array of `AxiomCandidate`-shaped dicts; set `confidence` honestly
- Instruction: if no extractable axiom, return `[]`

**Input per call:** `source_text`, `owl_class` hint (the CN code mapped to its product class), available process classes, chapter number.

**Cost guard:** `max_sections: int = 20` — warn and skip if exceeded.

**Test file:** `tests/unit/test_agent_llm_agent.py`

Test scenarios:
- Mocked `anthropic.Anthropic`: valid JSON → parsed to `AxiomCandidate` list
- Malformed JSON → `ValueError` with section note_id in message
- Empty response `[]` → returns empty list, no exception
- `max_sections` exceeded → `RuntimeError` before any API call

---

### IU6 — `src/agent/candidate_registry.py`: CandidateRegistry

**New file.** Unchanged from original plan. CRUD for `data/axiom_candidates/ch{N}.jsonl`.

```python
class CandidateRegistry:
    def load(self) -> list[AxiomCandidate]: ...
    def upsert(self, candidate: AxiomCandidate) -> None:
        # If source_ingestion_date changed → set status="stale"
        # If unchanged → preserve existing status
    def get_active(self) -> list[AxiomCandidate]:
        # Returns all with status != "stale"
    def stale_summary(self) -> list[dict]: ...
    def save(self) -> None:  # atomic write
```

JSONL format, sorted by `candidate_id` for stable git diffs.

**Test file:** `tests/unit/test_agent_candidate_registry.py`

Test scenarios:
- Upsert new → appears in load
- Upsert same `candidate_id` with new `source_ingestion_date` → status=`stale`
- Upsert same `candidate_id`, same `source_ingestion_date`, existing status=`approved` → status preserved
- `get_active()` excludes stale
- Round-trip save/load identical
- Atomic write: temp file + rename

---

### IU7 — `src/agent/axiom_builder.py`: build_equivalence_axioms_from_candidates

**New file.** Converts active candidates → OWL triples. Unchanged from original plan.

```python
def build_equivalence_axioms_from_candidates(
    g: Graph,
    candidates: list[AxiomCandidate],
) -> None:
```

Groups by `owl_class`, applies helpers from `owl_helpers.py`, calls `_equiv`. Complement candidates applied in Phase 2 (after all Phase 1 restrictions). BNode key: `f"cand:{candidate_id[:12]}"`.

**Test file:** `tests/unit/test_agent_axiom_builder.py`

Test scenarios:
- Single `decimalRange` → `owl:onDataRange` triple present
- Single `someValuesFrom` → `owl:someValuesFrom` triple present
- Called twice → idempotent
- `complement` before Phase 1 → `ValueError`
- Empty list → no triples, no exception

---

### IU_ANNOT — `src/agent/annotation_builder.py`: build_note_annotations

**New file.** Emits all CLASS API data as first-class RDF, independent of axiom extraction.

```python
def build_note_annotations(
    g: Graph,
    sections: list[LegalSection],
    cn_code_to_owl_class: dict[str, str],  # e.g. {"220820": "WhiskySpirit"}
) -> None:
    """Emit note resources, skos:definition, and eucn:hasExplanatoryNote links."""
```

**RDF emitted per `note_id`** (once, language-neutral):
```turtle
eucn:note_{note_id[:8]}  a eucn:ExplanatoryNote ;
    eucn:noteId     "{note_id}" ;
    eucn:noteType   "{note_type}" ;
    eucn:forCnCode  "{cn_code}" ;
    dcterms:modified "{ingestion_date}"^^xsd:date ;
    dcterms:source  <https://webgate.ec.europa.eu/class-public-ui-web/> .
```

**Per language variant of the same note:**
```turtle
eucn:note_{note_id[:8]}
    skos:definition "{source_text}"@{language} .
```

**OWL class annotation** (when `cn_code` maps to a known class):
```turtle
eucn:{OwlClass}
    skos:definition "{source_text}"@en ;
    skos:definition "{source_text}"@de ;
    eucn:hasExplanatoryNote eucn:note_{note_id[:8]} .
```

**CN code without OWL class mapping** — still emit the note resource and its text; skip the `skos:definition` on class (no class to annotate).

**Namespace additions** (`src/ontology/namespaces.py`):
- `eucn:ExplanatoryNote` class
- `eucn:hasExplanatoryNote` property
- `eucn:noteId`, `eucn:noteType`, `eucn:forCnCode` annotation properties

**Test file:** `tests/unit/test_agent_annotation_builder.py`

Test scenarios:
- Single `en` section for mapped CN code → `skos:definition`@en on OWL class
- `en` + `de` sections for same `note_id` → both `skos:definition` triples, single `eucn:ExplanatoryNote` resource
- CN code not in `cn_code_to_owl_class` → note resource emitted, no `skos:definition` on class, no exception
- Called twice (same sections) → idempotent (no duplicate triples)
- `eucn:hasExplanatoryNote` link present from OWL class to note resource
- `dcterms:modified` typed as `xsd:date`

---

### IU8 — Pipeline integration + TARIC consultation as wizard replacement

**Modified files:**
- `src/pipeline.py` — add `fetch-legal-text` step before `build-ontology`; replace EZT-Online wizard with TARIC consultation for descriptions
- `src/ontology/abox.py` — dispatch to `build_equivalence_axioms_from_candidates` when registry exists
- `src/ontology/chapter_registry.py` — `add_equivalence_axioms` optional

**New pipeline step `fetch-legal-text`:**
1. `ClassApiClient.fetch_chapter_notes(chapter, ...)` → `LegalSection` list
2. `RuleBasedExtractor.extract_candidates(sections, ...)` → candidates
3. LLM fallback for zero-result sections
4. `CandidateRegistry.upsert(each)` → detect staleness
5. Warn if `registry.stale_summary()` non-empty

**TARIC consultation as wizard replacement (bonus):**

The TARIC consultation page `taric_consultation.jsp?Lang={en|de}&Taric={chapter:02d}&Expand=true&SimDate={date}` gives hierarchy + descriptions for both languages via stateless GET. Replace the current EZT-Online Ausfuhr Playwright scraper with a simple `httpx` fetch + HTML parse of the TARIC page. This is a separate small IU (IU8b) but can be bundled here.

**Staleness warning format:**
```text
WARNING: 3 axiom candidate(s) for chapter 22 are stale (CLASS note updated).
  - cand:abc123... (Beer, someValuesFrom, eucn:producedBy) — note 82da68aa updated 2026-01-15
Re-run: python -m src.pipeline --chapter 22 --steps fetch-legal-text
or edit: data/axiom_candidates/ch22.jsonl (set status="approved" to re-confirm)
```

**Test file:** `tests/unit/test_pipeline_legal_text_integration.py`

Test scenarios:
- Stale candidates → build completes, `stderr` contains "stale"
- No registry file → falls back to `add_equivalence_axioms`
- Registry with active candidates → `add_equivalence_axioms` not called
- `--skip-step fetch-legal-text` → fetch skipped, existing registry used

---

### IU9 — Migration script: Ch22 + Ch23 → candidate registry

**New file:** `scripts/migrate_axioms_to_candidates.py` (one-shot).

Reads existing hand-authored axioms from `equivalence_axioms_beverages.py` and `equivalence_axioms_ch23_feed.py`, constructs `AxiomCandidate` with:
- `extractor = "manual"`
- `status = "approved"`
- `source_note_id = "manual-migration"` (not a real CLASS note ID)
- `source_ingestion_date = "2026-06-08"` (date of migration)
- `confidence = 1.0`

After migration: full pipeline run + Konclude check must pass unchanged.

---

## Files created / modified

| File | Action |
|---|---|
| `src/schema/legal_text.py` | **New** |
| `src/schema/axiom_candidate.py` | **New** |
| `src/fetcher/class_api.py` | **New** — replaces tariffnumber.com plan |
| `src/agent/__init__.py` | **New** (empty) |
| `src/agent/rule_extractor.py` | **New** |
| `src/agent/llm_agent.py` | **New** |
| `src/agent/candidate_registry.py` | **New** |
| `src/agent/axiom_builder.py` | **New** |
| `src/agent/annotation_builder.py` | **New** |
| `scripts/migrate_axioms_to_candidates.py` | **New** (one-shot) |
| `src/pipeline.py` | **Modified** — `fetch-legal-text` step |
| `src/ontology/abox.py` | **Modified** — registry dispatch |
| `src/ontology/chapter_registry.py` | **Modified** — `add_equivalence_axioms` optional |
| `data/legal_text/` | **New dir** (gitignored — regenerable) |
| `data/axiom_candidates/` | **New dir** (tracked — curated registry) |

---

## Dependencies

- `anthropic` SDK — add to `pyproject.toml` if not present
- `httpx` — already present
- `lxml` — already present (for TARIC consultation HTML parse in IU8b)

No new major dependencies.

---

## Key decisions

**Why CLASS API over tariffnumber.com?**
Official EU Commission source. Structured JSON (no HTML parsing). `noteId` is a stable identifier. `ingestionDate` is a built-in version signal. Available in all 23 EU languages. No scraping fragility. API verified working 2026-06-08.

**Why `searchSecondLevel` not `searchFirstLevel`?**
`searchFirstLevel` returns only the list of CN codes that have notes (for navigation). `searchSecondLevel` returns the actual note snippets — the content we need.

**Why `ingestionDate` as staleness key instead of content hash?**
CLASS updates `ingestionDate` when a note is revised. This is the authoritative change signal from the Commission. We also store `source_text_hash` as a defensive check (detects if snippet text changes even without `ingestionDate` update, though this should not happen in practice).

**Why snippets not full PDFs for extraction?**
Snippets from `searchSecondLevel` are complete enough for the formulaic language of CN Notes. PDFs are available via `getNotesById` for human review but add PDF-parsing complexity with no benefit for the structured patterns we target. If a snippet is truncated for a complex note, LLM agent handles it.

**Why rule-based first, LLM second?**
CN Notes use highly formulaic language. Rule-based covers ~70% of cases at 0.9+ confidence with zero API cost. LLM handles scope exclusions and complex multi-criterion notes.

**Why JSONL for candidate registry?**
Git-diffable, sortable by `candidate_id`, matches existing `wizard_*.jsonl` pattern, no DB dependency.

**Why emit note resources as RDF (not just internal JSONL)?**
The CLASS API data is not just pipeline input — it IS the legal basis for classification. Making it queryable via SPARQL (`?class eucn:hasExplanatoryNote ?note`) lets tooling and humans ask "what legal text justifies this classification?" directly on the graph. `skos:definition` in both `en` and `de` also gives multilingual labels without a second lookup. Provenance (`dcterms:modified` from `ingestionDate`) is preserved in the ontology itself, not just in a sidecar file.

**Why fetch both `en` and `de` in IU3?**
German labels are needed for `skos:definition`@de on OWL classes (required by `test_heading_class_has_de_label` pattern established in Ch22/Ch23 modules). Fetching both languages in a single `ClassApiClient` call avoids a second pipeline step. The `LegalSection` model already carries `language`, so storage cost is 2× notes JSONL rows per chapter — negligible.

---

## Risks

| Risk | Mitigation |
|---|---|
| CLASS API changes URL/schema | Pin `class-public-ui-rest` base; alert on non-200; `ingestionDate` field is stable across versions |
| `noteDescrSnippet` truncated for long notes | LLM agent fallback; PDF available for manual review |
| Process class IRI not in EUCN namespace | `axiom_builder.py` validates all IRIs against known namespace before adding triples; rejects unknowns with `ValueError` |
| BTI search returns 420 | BTI not needed for v1; CN Notes alone sufficient for equivalence axioms |
| Annual CN update renames/renumbers notes | `ingestionDate` change → stale flag surfaces affected candidates; re-extraction resolves |

---

## Sequencing

1. **IU1 + IU2** — schemas, no dependencies, parallelizable
2. **IU3** — CLASS API client (bilingual fetch), depends on IU1
3. **IU4 + IU5** — extractors, depend on IU1 + IU2
4. **IU6** — registry, depends on IU2
5. **IU7** — axiom builder, depends on IU2
6. **IU_ANNOT** — annotation builder, depends on IU1; parallelizable with IU7
7. **IU8** — pipeline integration, depends on IU3–IU7 + IU_ANNOT
8. **IU9** — migration, depends on IU6; run after IU8 confirmed working
