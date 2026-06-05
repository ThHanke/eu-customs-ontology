---
title: "feat: EU Customs Ontology — Chapter 22 Pilot Pipeline"
type: feat
status: active
date: 2026-06-05
origin: docs/brainstorms/eu-customs-ontology-requirements.md
---

# feat: EU Customs Ontology — Chapter 22 Pilot Pipeline

## Overview

Build the full data acquisition and ontology construction pipeline for EU customs classification, piloting on CN Chapter 22 (Beverages, spirits and vinegar). The pipeline scrapes the EZT-Online sequential classification wizard to capture the classification decision tree, fetches TARIC3 bulk XML from CIRCABC for duty measures, merges both into a contract-defined intermediate JSON format, and populates an OWL 2 DL ontology in RDF/Turtle. OWL 2 DL consistency is validated via Konclude (WASM). SPARQL acceptance tests run on a pyoxigraph store.

## Problem Frame

EU customs knowledge is fragmented across EZT-Online's interactive wizard, the CIRCABC TARIC database, and EUR-Lex legal texts. There is no machine-readable, reasoning-capable representation combining classification decision trees with regulatory measures. Importers, exporters, customs brokers, and compliance systems need both in one queryable artifact. (See origin: `docs/brainstorms/eu-customs-ontology-requirements.md`)

## Requirements Trace

- R1. Playwright scraper traverses EZT-Online wizard, captures all Chapter 22 decision-tree branches
- R2. TARIC fetcher downloads measures from CIRCABC bulk XML / EU Open Data Portal
- R3. Both tools produce intermediate JSON per a contract-first Pydantic schema
- R4. Scripts parameterized by CN chapter number; pilot = Chapter 22
- R5. Ontology models CN hierarchy: Section → Chapter → Heading → Subheading → CN code → TARIC code
- R6. Each CN code individual: code string, EN/DE description, legal note references, measure links
- R7. TARIC measures: type, duty rate, geographic scope, validity period, regulation reference
- R8. Decision tree: `ClassificationNode` graph with `hasAnswer` edges; terminal nodes `classifiesAs` CN codes; provenance annotations on every node
- R9. Primary serialization: RDF/Turtle (`.ttl`); JSON-LD deferred post-pilot
- R10. Single orchestration script: scrape → fetch → merge → write ontology
- R11. Idempotent: deterministic IRI minting; re-runs produce identical output
- R12. Pilot: Chapter 22 end-to-end, validates SPARQL success criterion

**Success criteria:**
- All Chapter 22 CN codes present, each with MFN duty rate and correct wizard path from root
- SPARQL query for MFN ad-valorem rate on CN 2204 21 (still wine ≤2L, non-EU non-preferential) matches Official Journal value confirmed from CIRCABC source data
- Orchestration completes unattended in under 30 minutes (excluding bulk XML download time)
- Manual spot-traversal of Chapter 22 wizard completes before full automated run, node count documented

## Scope Boundaries

- Import classification and duty only — no export declarant procedures (ECS)
- Anti-dumping and countervailing duty measures excluded from pilot
- GSP/FTA preferential schedules excluded from pilot
- Legal text full-text out of scope; only regulation identifiers and article references
- JSON-LD export deferred post-pilot
- Cross-chapter parameterization validated against one additional chapter after pilot completes

### Deferred to Separate Tasks

- JSON-LD export and LLM/RAG integration: separate task when a consumer is identified
- Extension to full CN (all 99 chapters): separate automation task post-pilot
- Anti-dumping measures: separate chapter post-pilot

## Context & Research

### EZT-Online Wizard (R1) — Confirmed Architecture

- **Live URL:** `https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do`
- **Stack:** Java Struts servlets, server-rendered JSP, POST-based form submission
- **Auth:** No login required. Session cookies (`JSESSIONID`) must be allowed. Publicly accessible.
- **Prior access issues:** `www2.zoll.de` and `ezto.zoll.de` are defunct. `auskunft.ezt-online.de` is the current host, migrated from the old domain. Last content update confirmed February 2026.
- **Scraping approach:** Playwright sync API (no async loop in pipeline scripts), DFS traversal preferred (deep narrow tree), form POST via DOM click/submit, `wait_for_load_state("networkidle")` after each submission. `page.wait_for_navigation()` is deprecated — do not use.

### TARIC Bulk XML (R2) — Confirmed Sources

- **CIRCABC group:** `https://circabc.europa.eu/ui/group/0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b` — anonymous access, no registration required. TARIC3 XML: daily delta + monthly full snapshots.
- **EU Open Data Portal:** `https://data.europa.eu/data/datasets/eu-customs-tariff-taric` — Excel format bulk download also available.
- **TARIC3 XML schema:** Envelope → `oub:transaction` → `oub:record`. Measure = record code `271`. Duty components = record code `430` (`MeasureComponent`), linked via `<oub:sid>` (the **stable** measure identifier — NOT `<oub:record.sequence.number>` which is per-extraction only).
- **Measure SID field:** `<oub:sid>` inside `<oub:measure>`. This is the IRI key for measure individuals.
- **Duty rate fields (in MeasureComponent, record 430):** `measureSid` (FK to parent), `dutyExpressionId`, `dutyAmount`, `monetaryUnitCode`, `measurementUnitCode`.
- **MFN scope:** `geographicalAreaId = 1011` (ERGA OMNES = all third countries).

### Python/Node.js Environment

- **Python 3.11.2**, **Node.js 25.1.0** on this machine
- **Installed:** `rdflib 7.6.0` (pyparsing 3.x fix included in 7.6.0), `owlrl 7.1.4`, `pyshacl 0.31.0`, `pydantic 2.12.5`, `requests 2.34.0`, `httpx 0.28.1`, `beautifulsoup4 4.14.3`, `pytest 7.2.1`
- **Not installed (must add):** `playwright` (Python), `pyoxigraph`, `lxml`
- **Trunk linting** configured in `.trunk/trunk.yaml` (Node 22 + Python 3.14 runtimes). Run `trunk fmt` before commits.

### Konclude WASM Reasoner

**WASM Konclude surpasses native Konclude OWL 2 DL capabilities** (confirmed 2026-06-02, capability matrix in `rdf-reasoner-konclude/docs/solutions/capability-gaps/wasm-vs-native-owl-violation-detection.md`):

| Construct | Native v0.7.0 | WASM |
|-----------|--------------|------|
| `AsymmetricProperty` bidirectional clash | consistent ✗ (native bug) | inconsistent ✓ |
| `IrreflexiveProperty` self-loop clash | consistent ✗ (native bug) | inconsistent ✓ |
| `AllDisjointProperties` + `EquivalentObjectProperties` clash | consistent ✗ (native bug) | inconsistent ✓ |
| `NegativePropertyAssertion` contradiction | inconsistent ✓ | inconsistent ✓ |
| `disjointWith`, cardinality, `allValuesFrom` | inconsistent ✓ | inconsistent ✓ |

Additional OWL 2 DL features handled via JS-layer workarounds in the **JS API only** (not CLI):
- `owl:FunctionalProperty` / `owl:InverseFunctionalProperty`: declarations stripped before WASM to prevent ALIF+ hang; `owl:sameAs` chains computed in JS instead
- `owl:complementOf` (named class): pre-checked in JS `checkConsistency()` before WASM call

**Two integration surfaces:**

1. **JS API** (`dist/index.js` — `RdfReasoner` class): Full capability with JS-layer workarounds. Takes **N3.Store** (`import { Store } from 'n3'`) as native input. Methods: `checkConsistency(store)`, `classify(store)`, `materialize(store)`, `explain(store, axiom)`, `validate(store)`, `isEntailed(store, axiom)`, `whatIf(store, additions)`. Inferred triples written to `INFERRED_GRAPH_IRI` named graph in the N3 store. Wire format across JS↔WASM boundary is NTriples (serialized by n3 Writer, parsed back by n3 Parser).
2. **CLI** (`dist/cli.js`): Subprocess interface for non-JS runtimes. Does NOT apply JS-layer workarounds (FP/IFP stripping, complementOf pre-check). Suitable for basic consistency/classify calls when the ontology avoids `owl:FunctionalProperty` ABox assertions.

**For the Python pipeline:** use CLI subprocess (`node dist/cli.js`). Node.js flags `--experimental-wasm-threads`/`--experimental-wasm-bulk-memory` do NOT exist in Node 25 — remove them. Use `--mode consistency` (not `--mode classify`) for inconsistency detection; classify exits 0 regardless of consistency.

- **Consistency check:** `node /home/hanke/rdf-reasoner-konclude/dist/cli.js --input ont.ttl --mode consistency` — exits 1 if inconsistent
- **Classification (TBox inference):** `--mode classify --format ttl` — exits 0, inferred triples on stdout
- **CLI output:** plain Turtle/NTriples triples, no named graph annotation. `urn:konclude:inferred` named graph only exists in the JS API's in-process N3 store.
- **Known hang (CLI only):** `materialize()` hangs on `AllDisjointClasses`/`disjointUnionOf` via NTriples path when ABox individuals present — use Turtle input (`--input`) which avoids the NTriples hang path.
- **Validation:** triple-level sorted diff (not count) for idempotency verification.

### rdflib 7.x Patterns

- Use `Dataset` (not deprecated `ConjunctiveGraph`). `Dataset.graphs` replaces `Dataset.contexts`.
- Serializing `Dataset` to Turtle silently drops named graphs — use `format="trig"` when preserving provenance graphs. Use `format="longturtle"` for single-graph git-diffable output.
- **SPARQL:** Do NOT use `rdflib.Graph.query()` — route all SPARQL through pyoxigraph.
- rdflib role: RDF I/O only (`Graph.parse()`, `Graph.add()`, `Graph.serialize()`).

### pyoxigraph 0.5.8

- `Store(path)` for persistent disk store; `Store()` for in-memory.
- `store.bulk_load(path=..., format=RdfFormat.TURTLE)` for non-transactional fast ingestion.
- `store.query("SELECT ...", use_default_graph_as_union=True)` to query across named graphs.
- ASK queries return `QueryBoolean`, not Python `bool`.
- `format=` uses `RdfFormat.TURTLE` enum (not MIME string — changed in 0.5).

### OWL 2 Design Principles

- Model CN/TARIC codes as **named individuals** (not classes) — a hierarchical lookup system with enumerable instances belongs in the ABox.
- IRI minting: **UUID5** (deterministic, SHA-1 hash-based). Fixed pipeline namespace UUID + stable source string → always same IRI.
- Provenance: `dcterms:source`, `dcterms:created`, `dcterms:creator` per individual; `prov:wasGeneratedBy` linking to a pipeline run `prov:Activity` individual in a separate named graph.
- EZT content legal disclaimer: `rdfs:comment` annotation on every `ClassificationNode` that this is an advisory tool, not a legally binding EU instrument.

### Institutional Learnings Applied

- Konclude WASM surpasses native: fixes for AsymmetricProperty, IrreflexiveProperty, AllDisjointProperties bugs are in the WASM build but NOT in native Konclude v0.7.0.
- Node.js WASM flags (`--experimental-wasm-threads`, `--experimental-wasm-bulk-memory`) were graduated to stable and removed in Node 22 — do NOT pass them on Node 25.
- Use `--mode consistency` (not `--mode classify`) for inconsistency detection from CLI; classify always exits 0.
- `AllDisjointClasses`/`disjointUnionOf` + ABox individuals hang in WASM realization (`materialize()`) via NTriples path — use Turtle input via `--input` to avoid.
- CLI does not apply JS-layer workarounds (FP/IFP stripping); avoid `owl:FunctionalProperty` in ABox assertions in the pilot ontology to keep the CLI path safe.
- Triple-level diff (not count) for idempotency validation — count match can mask compensating errors.
- SPARQL never goes through rdflib (pyparsing compat confirmed fixed in 7.6.0, but external triplestore is the established pattern).
- `owlrl 7.1.4` is OWL RL, not OWL DL — use only for RL-level RDFS materialization if needed separately from Konclude.

## Key Technical Decisions

- **Contract-first JSON schema (Pydantic) before scrapers:** Pydantic models define the exact shape both R1 and R2 must produce; scrapers are written to satisfy the schema, not the reverse. This makes R8's ClassificationNode semantics ontology-driven, not scraper-driven.
- **DFS wizard traversal with SHA-256 state keys:** State = hash(URL + sorted hidden form parameters). Avoids URL-only cycle detection misses from Struts hidden fields. Checkpoint every 50 nodes to JSONL.
- **Session persistence via `context.storage_state()`:** Saves/restores `JSESSIONID` across partial traversal runs. Detected session expiry = re-navigate to entry page, replay path from last checkpoint.
- **UUID5 for all IRI minting:** Namespace UUID is a fixed project constant. CN codes: keyed by normalized code string. TARIC measures: keyed by `oub:sid` string. ClassificationNodes: keyed by root-to-node path (serialized question+answer chain). Guarantees R11 idempotency.
- **Turtle-only Konclude input:** Never pass NTriples to the Konclude CLI. Write `.ttl`, invoke with `--input`, receive `.ttl`. Avoids known `AllDisjointClasses` hang.
- **pyoxigraph for SPARQL:** Load the output `.ttl` into a pyoxigraph in-memory `Store`, run SPARQL 1.1 queries. No external server needed. Use `use_default_graph_as_union=True` when provenance is in named graphs.
- **rdflib `Dataset` + TriG for provenance:** Asserted ontology triples in the default graph; provenance triples (pipeline run, capture date, source URL, disclaimer) in a separate named graph. Serialize to TriG for archival; extract default graph to Turtle for SPARQL load.

## Open Questions

### Resolved During Planning

- **EZT wizard host:** `auskunft.ezt-online.de` — confirmed live, no login, Struts/JSP server-rendered.
- **TARIC API accessibility:** CIRCABC anonymous access confirmed; TARIC3 XML schema confirmed; `oub:sid` is the stable measure identifier.
- **Konclude invocation:** CLI subprocess via Node.js with `--experimental-wasm-threads --experimental-wasm-bulk-memory`; Turtle input only.
- **rdflib SPARQL:** Fixed in rdflib 7.6.0 at library level; project convention still routes SPARQL to pyoxigraph.
- **OWL reasoner:** Konclude WASM via CLI. No additional installation required; `dist/` pre-compiled.

### Deferred to Implementation

- Exact OWL 2 class and property axiom set: depends on what classification and lookup queries need to be expressible. Start minimal (object property hierarchy only), add restrictions if reasoning needs arise.
- Chapter 22 wizard node count: measure by manual spot-traversal in Unit 4 before full automation.
- TARIC XML full schema: confirm exact XPath for `dutyAmount`, `monetaryUnitCode` in MeasureComponent records during Unit 3 implementation — schema PDF on CIRCABC is the reference.
- Oxigraph persistent vs. in-memory store: use in-memory for pilot acceptance test (chapter 22 is small); switch to persistent for full CN if needed.
- CIRCABC programmatic download: the group page requires a browser session; determine whether direct file-path URLs are stable enough for `httpx` download or whether a Playwright session is needed for CIRCABC browsing.

## Output Structure

```
eu-customs-ontology/
├── src/
│   ├── schema/
│   │   ├── wizard.py          # Pydantic: ClassificationNode, AnswerEdge, WizardTree
│   │   └── taric.py           # Pydantic: TARICMeasure, MeasureComponent, ChapterData
│   ├── scraper/
│   │   ├── wizard.py          # Playwright DFS scraper, session management
│   │   └── checkpoint.py      # JSONL checkpoint/resume
│   ├── fetcher/
│   │   └── taric_xml.py       # CIRCABC/EU Open Data download + TARIC3 XML parser
│   ├── ontology/
│   │   ├── namespaces.py      # Namespace definitions and project IRI constants
│   │   ├── iri.py             # UUID5 IRI minting helpers
│   │   ├── tbox.py            # OWL 2 TBox: classes, properties, annotations
│   │   ├── abox.py            # ABox population from intermediate JSON
│   │   └── provenance.py      # PROV-O + dcterms provenance graph
│   ├── reasoning/
│   │   └── konclude.py        # Subprocess wrapper: node --experimental-wasm-threads ...
│   ├── sparql/
│   │   └── store.py           # pyoxigraph Store: bulk load, SPARQL query helpers
│   └── pipeline.py            # Chapter-parameterized orchestration entry point
├── data/
│   ├── intermediate/          # Per-chapter JSON outputs (wizard.json, taric.json)
│   └── ontology/              # Per-chapter .ttl + .trig outputs
├── tests/
│   ├── unit/                  # Schema validation, IRI minting, XML parsing
│   ├── integration/           # Konclude subprocess, Oxigraph load/query
│   └── acceptance/            # Chapter 22 SPARQL success criterion
├── pyproject.toml
└── requirements.txt
```

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
CIRCABC TARIC3 XML             EZT-Online Wizard
       │                    auskunft.ezt-online.de
       │                              │
       ▼                              ▼
 taric_xml.py                  scraper/wizard.py
 (httpx download +             (Playwright DFS +
  TARIC3 XML parse)             session/checkpoint)
       │                              │
       │     ◄── Pydantic schema ──►  │
       │        schema/taric.py       │
       │        schema/wizard.py      │
       ▼                              ▼
 data/intermediate/            data/intermediate/
   taric_ch22.json              wizard_ch22.jsonl
            │                         │
            └─────────┬───────────────┘
                      ▼
               ontology/abox.py
               + tbox.py
               + iri.py (UUID5)
               + provenance.py
                      │
                      ▼
               rdflib Dataset
               (default graph: ontology triples)
               (named graph: provenance)
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
      .ttl (Turtle)       .trig (TriG)
       [default graph]     [all graphs]
            │
            ▼
      reasoning/
      konclude.py
      subprocess: node --experimental-wasm-threads
                       --experimental-wasm-bulk-memory
                       dist/cli.js --input ont.ttl
                       --mode classify
            │
            ▼ (consistency: OK / FAIL)
            │
            ▼
      sparql/store.py
      pyoxigraph bulk_load(.ttl)
      store.query("SELECT ...")
            │
            ▼
      Acceptance test:
      CN 2204 21 MFN rate
      matches CIRCABC source
```

## Implementation Units

- [x] **Unit 1: Project scaffolding**

**Goal:** Establish the Python project structure, install dependencies, and configure the development toolchain.

**Requirements:** R3, R10, R12 (prerequisite infrastructure)

**Dependencies:** None

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/schema/__init__.py`
- Create: `src/scraper/__init__.py`
- Create: `src/fetcher/__init__.py`
- Create: `src/ontology/__init__.py`
- Create: `src/reasoning/__init__.py`
- Create: `src/sparql/__init__.py`
- Create: `data/intermediate/.gitkeep`
- Create: `data/ontology/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/acceptance/__init__.py`

**Approach:**
- `pyproject.toml` with `[project]` table: Python ≥3.11, package name `eu-customs-ontology`
- `requirements.txt` pins: `rdflib>=7.6.0`, `pyoxigraph>=0.5.8`, `playwright>=1.60.0`, `pydantic>=2.12`, `httpx>=0.28`, `lxml>=5.0`, `pytest>=7.2`, `owlrl>=7.1.4`
- After install: `playwright install chromium` (downloads browser binary)
- Add `src/` to Python path in `pyproject.toml` (`[tool.setuptools.packages.find]`)
- Follow `.trunk/trunk.yaml` conventions already in place — no changes to Trunk config

**Test scenarios:**
- Test expectation: none — scaffolding only, verified by successful `python -c "import src.schema"` and `pytest --collect-only` returning no errors

**Verification:**
- `pip install -e .` succeeds with no dependency conflicts
- `playwright install chromium` completes
- `pytest --collect-only` discovers the test directories
- `trunk check` reports no violations on new files

---

- [x] **Unit 2: Contract-first JSON intermediate schema (Pydantic)**

**Goal:** Define Pydantic models for the wizard decision tree and TARIC measures that both the scraper (R1) and fetcher (R2) must satisfy. This schema gates all downstream work.

**Requirements:** R3 (both tools produce clean intermediate JSON), R8 (ClassificationNode graph), R7 (TARIC measures)

**Dependencies:** Unit 1

**Files:**
- Create: `src/schema/wizard.py`
- Create: `src/schema/taric.py`
- Test: `tests/unit/test_schema.py`

**Approach:**
- `wizard.py`: `ClassificationNode` (node_id: str, question_text: str, answer_options: list[AnswerOption], is_terminal: bool, cn_code: str | None, path_from_root: list[str]); `AnswerOption` (answer_text: str, next_node_id: str | None); `WizardTree` (chapter: int, nodes: dict[str, ClassificationNode], root_node_id: str)
- `taric.py`: `MeasureComponent` (duty_expression_id: str, duty_amount: float | None, monetary_unit: str | None, measurement_unit: str | None); `TARICMeasure` (sid: str, commodity_code: str, measure_type_id: str, geographical_area_id: str, validity_start: date, validity_end: date | None, regulation_id: str, components: list[MeasureComponent]); `ChapterData` (chapter: int, measures: list[TARICMeasure])
- All fields use strict types; optional fields use `None` not empty string
- `model_config = ConfigDict(frozen=True)` on leaf models for safe hashing

**Patterns to follow:**
- pydantic 2.x `model_config = ConfigDict(...)` pattern (not `class Config`)

**Test scenarios:**
- Happy path: valid wizard node dict round-trips through `ClassificationNode.model_validate()` → `model_dump()` without loss
- Happy path: valid TARIC measure dict round-trips through `TARICMeasure.model_validate()`
- Edge case: terminal node with `cn_code = "2204219100"` and empty `answer_options` validates correctly
- Edge case: `validity_end = None` (open-ended measure) validates; `validity_end = "2026-12-31"` parses as `date`
- Error path: missing required `sid` field raises `ValidationError`
- Error path: `cn_code` present on non-terminal node raises `ValidationError` (add a validator)

**Verification:**
- All unit tests pass
- `WizardTree.model_json_schema()` and `ChapterData.model_json_schema()` produce valid JSON Schema documents (confirming schema is introspectable for documentation)

---

- [x] **Unit 3: TARIC bulk XML fetcher**

**Goal:** Download Chapter 22 TARIC3 XML from CIRCABC or EU Open Data Portal, parse measure and measure-component records, and write `data/intermediate/taric_ch22.json` conforming to the Pydantic schema.

**Requirements:** R2, R3, R4

**Dependencies:** Unit 2

**Files:**
- Create: `src/fetcher/taric_xml.py`
- Test: `tests/unit/test_taric_fetcher.py`
- Test: `tests/integration/test_taric_integration.py`

**Approach:**
- Accept `--chapter N` parameter; filter XML to records where `goodsNomenclatureItemId` starts with the 2-digit chapter prefix
- Download strategy: try direct CIRCABC file URL (httpx GET, no auth); fall back to prompting the user for a local XML path if CIRCABC requires browser session
- XML parsing: `lxml.etree` for namespace-aware parsing of the TARIC3 envelope. Parse record code `271` (Measure) and `430` (MeasureComponent). Join on `sid`.
- Key field extraction from Measure (271): `sid` (stable ID), `goodsNomenclatureItemId`, `measureTypeId`, `geographicalAreaId`, `validityStartDate`, `validityEndDate`, `measureGeneratingRegulationId`
- Key field extraction from MeasureComponent (430): `measureSid`, `dutyExpressionId`, `dutyAmount`, `monetaryUnitCode`, `measurementUnitCode`
- Output: `ChapterData.model_dump_json()` to `data/intermediate/taric_ch{chapter}.json`
- Validate output against Pydantic schema before writing

**Patterns to follow:**
- Use `httpx.Client` (not `requests`) — already installed, supports streaming for large files
- Parse XML with `lxml.etree.iterparse()` for streaming (TARIC XML files can be 100MB+)

**Test scenarios:**
- Happy path: fixture XML with 3 measures (2 for chapter 22, 1 for chapter 01) → output contains exactly 2 measures
- Happy path: measure with `validity_end` empty → parsed as `None`
- Happy path: MeasureComponent with `monetary_unit = "EUR"` → preserved in output
- Edge case: measure with no MeasureComponent records → empty `components` list, not validation error
- Edge case: chapter 22 commodity code `2204219100` (10-digit) correctly filtered
- Error path: XML with malformed envelope element → raises descriptive `ValueError` with element name
- Integration: actual CIRCABC or EU Open Data download succeeds for Chapter 22 and produces ≥10 measures (smoke test, skipped in offline CI)

**Verification:**
- Unit tests pass with fixture XML
- Integration test produces a valid `ChapterData` JSON with at least one MFN measure (type `103`) for CN code prefix `22`
- `pyoxigraph` or `jq` query against the JSON confirms `sid` field is populated and non-null on all measures

---

- [x] **Unit 4: EZT-Online wizard scraper**

**Goal:** Manually spot-traverse Chapter 22 wizard to bound graph size, then build a Playwright DFS scraper that captures all decision-tree branches and writes `data/intermediate/wizard_ch22.jsonl` conforming to the Pydantic schema.

**Requirements:** R1, R3, R4

**Dependencies:** Unit 2

**Files:**
- Create: `src/scraper/wizard.py`
- Create: `src/scraper/checkpoint.py`
- Test: `tests/unit/test_wizard_scraper.py`
- Test: `tests/integration/test_wizard_integration.py`

**Approach:**
- Entry URL: `https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do`
- Chapter selection: POST form parameter to select Chapter 22 at the entry screen
- **Manual spot-traversal first:** Navigate 10-15 nodes manually, record: max observed depth, branching factor, whether any state IDs repeat. Document node count estimate. This must complete before automated traversal begins.
- **DFS traversal:** Explicit stack of `(url, form_data, path_from_root)` tuples. Pop, submit form, extract next options, push unvisited states.
- **State key:** `sha256(url + "|" + "&".join(sorted(f"{k}={v}" for k, v in form_data.items())))` — includes all hidden form fields (Struts action tokens, state machine position)
- **Session management:** `browser.new_context(storage_state=...)` if `checkpoint.json` exists, otherwise fresh context. Save `storage_state` after wizard entry page loads.
- **Session expiry detection:** POST response URL matches entry page URL despite being in mid-traversal → session expired. Re-navigate to entry, reload chapter 22, replay path from last checkpoint.
- **Checkpoint:** `checkpoint.py` saves visited set + frontier stack to `data/intermediate/checkpoint_ch22.json` every 50 nodes. Also appends completed nodes to `data/intermediate/wizard_ch22.jsonl` as they are finalized.
- **Terminal node detection:** No further answer options present, or a CN code is shown in the page (regex `\d{8,10}` in specific page elements)
- Use `sync_playwright` (no asyncio loop in pipeline scripts)
- `wait_for_load_state("networkidle")` after every form submission
- Screenshot to `data/intermediate/error_{timestamp}.png` on any `TimeoutError`

**Patterns to follow:**
- Checkpoint/resume pattern from learnings: append-only JSONL for completed nodes, separate checkpoint file for traversal state
- SHA-256 state key pattern for cycle detection

**Test scenarios:**
- Happy path (unit, mocked Playwright): DFS stack with 3 nodes (root → A → terminal) produces correct `WizardTree` with `root_node_id` set and terminal node's `is_terminal=True`
- Edge case: state key collision (same URL + same hidden fields from two different navigation paths) → second visit skipped (cycle detection working)
- Edge case: session expiry detected (response URL = entry URL mid-traversal) → checkpoint saved, exception raised with checkpoint path in message so operator can resume
- Error path: `TimeoutError` on page load → screenshot saved, traversal state checkpointed, exception raised
- Integration: 10-node manual spot-traversal against live EZT wizard completes without session expiry, depth and branching factor recorded in test output (skipped in offline CI, requires network)

**Verification:**
- Unit tests pass with mocked Playwright responses
- Manual spot-traversal integration test documents: observed max depth, observed max branching factor, whether state IDs are session-independent (confirms UUID5 path-based IRI minting will be stable)
- Full Chapter 22 traversal produces a JSONL file where every terminal node has a non-null `cn_code`

---

- [x] **Unit 5: OWL 2 ontology TBox and namespace definitions**

**Goal:** Define the ontology's namespace, class hierarchy, object properties, data properties, and annotation properties. Establish the IRI minting helpers. This is the ontology contract that the ABox populator (Unit 6) implements against.

**Requirements:** R5, R6, R7, R8

**Dependencies:** Unit 1

**Files:**
- Create: `src/ontology/namespaces.py`
- Create: `src/ontology/iri.py`
- Create: `src/ontology/tbox.py`
- Test: `tests/unit/test_iri.py`
- Test: `tests/unit/test_tbox.py`

**Approach:**
- `namespaces.py`: Define `CUSTOMS = Namespace("https://eu-customs-ontology.example.org/ontology/")` and the fixed pipeline UUID namespace constant. Import standard namespaces from `rdflib.namespace` (RDF, RDFS, OWL, XSD, SKOS, DCTERMS, PROV).
- `iri.py`: `mint_iri(namespace_uuid: UUID, base: str, key: str) -> URIRef` using `uuid.uuid5`. Provide specific helpers: `cn_code_iri(code: str)`, `taric_measure_iri(sid: str)`, `classification_node_iri(path: list[str])`.
- `tbox.py`: `build_tbox(graph: Graph) -> Graph` adds all TBox triples to the given graph:
  - Classes: `customs:CNCode`, `customs:TARICCode` (subclass of CNCode), `customs:TARICMeasure`, `customs:ClassificationNode`, `customs:Chapter`, `customs:Heading`
  - Object properties: `customs:classifiesAs` (ClassificationNode → CNCode), `customs:hasAnswer` (ClassificationNode → ClassificationNode), `customs:hasMeasure` (CNCode → TARICMeasure), `customs:belongsToChapter` (CNCode → Chapter)
  - Data properties: `customs:codeString`, `customs:description`, `customs:questionText`, `customs:answerText`, `customs:dutyRate`, `customs:geographicScope`, `customs:measureTypeId`, `customs:validityStart`, `customs:validityEnd`
  - Annotation properties: `dcterms:source`, `dcterms:created`, `dcterms:creator`
  - Every TBox term carries `rdfs:label` (EN + DE) and `skos:definition` (EN + DE, ISO 704 intensional form: genus + differentia, no leading article, substitutable for the term). Canonical definitions:

```turtle
customs:CNCode
    rdfs:label      "CN Code"@en , "KN-Code"@de ;
    skos:definition "commodity nomenclature code of eight digits assigned within the \
Combined Nomenclature of the European Union for the classification of goods in \
international trade"@en ;
    skos:definition "Warenpositionsnummer aus acht Stellen, die innerhalb der Kombinierten \
Nomenklatur der Europäischen Union zur Einreihung von Waren im internationalen Handel \
vergeben wird"@de .

customs:TARICMeasure
    rdfs:label      "TARIC Measure"@en , "TARIC-Maßnahme"@de ;
    skos:definition "regulatory instrument of the Integrated Tariff of the European \
Communities that specifies a tariff rate, restriction, suspension, quota, or licensing \
condition applicable to goods identified by a CN or TARIC code, valid within a defined \
geographical and temporal scope"@en ;
    skos:definition "Regelungsinstrument des Integrierten Zolltarifs der Europäischen \
Gemeinschaften, das einen Zollsatz, eine Beschränkung, eine Aussetzung, ein Kontingent \
oder eine Genehmigungspflicht für Waren festlegt, die durch einen KN- oder TARIC-Code \
identifiziert werden, gültig innerhalb eines bestimmten geografischen und zeitlichen \
Geltungsbereichs"@de .

customs:ClassificationNode
    rdfs:label      "Classification Node"@en , "Einreihungsknoten"@de ;
    skos:definition "step in a sequential commodity classification procedure that poses a \
single discriminating question to narrow the applicable nomenclature position; sourced \
from the EZT-Online advisory wizard and carrying advisory status only, not constituting \
a legally binding EU instrument"@en ;
    skos:definition "Schritt in einem sequenziellen Wareneinreihungsverfahren, der eine \
einzelne unterscheidende Frage stellt, um die zutreffende Nomenklaturposition \
einzugrenzen; bezogen auf den Beratungsassistenten EZT-Online und ohne rechtsbindende \
Wirkung als EU-Instrument"@de .

customs:Chapter
    rdfs:label      "Chapter"@en , "Kapitel"@de ;
    skos:definition "two-digit subdivision of the Harmonized System nomenclature that \
groups goods sharing a common material composition, functional category, or industrial \
origin"@en ;
    skos:definition "zweistellige Unterteilung der Nomenklatur des Harmonisierten Systems, \
die Waren mit gemeinsamer Materialzusammensetzung, funktionaler Kategorie oder \
industriellem Ursprung zusammenfasst"@de .

customs:Heading
    rdfs:label      "Heading"@en , "Position"@de ;
    skos:definition "four-digit subdivision of the Harmonized System nomenclature that \
identifies a specific group of goods within a chapter by further differentiating on \
material, process, or use"@en ;
    skos:definition "vierstellige Unterteilung der Nomenklatur des Harmonisierten Systems, \
die eine bestimmte Warengruppe innerhalb eines Kapitels durch weitere Differenzierung \
nach Material, Verarbeitungsstufe oder Verwendungszweck identifiziert"@de .

customs:codeString
    rdfs:label      "code string"@en , "Codenummer"@de ;
    skos:definition "digit string uniquely identifying a nomenclature position without \
separating punctuation, derived by concatenating the numeric segments of the code, \
e.g. '22042100' for CN code 2204 21 00"@en ;
    skos:definition "Ziffernfolge, die eine Nomenklaturstelle ohne Trennzeichen eindeutig \
identifiziert, gebildet durch Aneinanderreihung der numerischen Segmente des Codes, \
z. B. '22042100' für KN-Code 2204 21 00"@de .

customs:description
    rdfs:label      "description"@en , "Warenbezeichnung"@de ;
    skos:definition "official textual designation of a commodity as established in the \
legal text of the Combined Nomenclature, expressed in a specified natural language and \
carrying legal force within EU customs classification"@en ;
    skos:definition "amtliche Warenbezeichnung, wie sie im Rechtstext der Kombinierten \
Nomenklatur festgelegt ist, in einer bestimmten natürlichen Sprache und mit rechtlicher \
Wirkung innerhalb der EU-Zolleinreihung"@de .

customs:measureTypeId
    rdfs:label      "measure type ID"@en , "Maßnahmetyp-Kennung"@de ;
    skos:definition "numeric code assigned by TARIC that designates the regulatory \
category of a measure, distinguishing between duty types, prohibitions, suspensions, \
quotas, and licence requirements, e.g. '103' for Most Favoured Nation ad-valorem duty"@en ;
    skos:definition "von TARIC zugewiesener numerischer Code, der die Regelungskategorie \
einer Maßnahme bezeichnet und zwischen Zollarten, Verboten, Aussetzungen, Kontingenten \
und Genehmigungspflichten unterscheidet, z. B. '103' für den \
Meistbegünstigungs-Wertzollsatz"@de .

customs:dutyRate
    rdfs:label      "duty rate"@en , "Zollsatz"@de ;
    skos:definition "textual expression of the duty or charge rate applicable under a \
TARIC measure as published in the TARIC bulk data, combining a numeric value with a \
unit of measurement, e.g. '12.0 %' or '32.0 EUR/hl'"@en ;
    skos:definition "textliche Darstellung des Zoll- oder Abgabensatzes, der im Rahmen \
einer TARIC-Maßnahme gilt, wie in den TARIC-Massendaten veröffentlicht, bestehend aus \
einem numerischen Wert und einer Maßeinheit, z. B. '12,0 %' oder '32,0 EUR/hl'"@de .

customs:geographicScope
    rdfs:label      "geographic scope"@en , "geografischer Geltungsbereich"@de ;
    skos:definition "identifier of the country or country group to whose originating goods \
a TARIC measure applies, expressed as an ISO 3166-1 alpha-2 country code or a \
TARIC-assigned group code, e.g. '1011' for ERGA OMNES (all third countries)"@en ;
    skos:definition "Kennung des Landes oder der Ländergruppe, deren Ursprungswaren einer \
TARIC-Maßnahme unterliegen, ausgedrückt als ISO 3166-1-Alpha-2-Ländercode oder als \
TARIC-Gruppencode, z. B. '1011' für ERGA OMNES (alle Drittländer)"@de .

customs:questionText
    rdfs:label      "question text"@en , "Fragetext"@de ;
    skos:definition "textual formulation of the discriminating question posed at a \
classification node in the EZT-Online wizard, expressed in a specified natural language, \
used to guide the classifier toward the applicable nomenclature branch"@en ;
    skos:definition "textliche Formulierung der unterscheidenden Frage, die an einem \
Einreihungsknoten des EZT-Online-Assistenten gestellt wird, in einer bestimmten \
natürlichen Sprache, zur Führung des Einreihenden zur zutreffenden \
Nomenklaturstelle"@de .

customs:answerText
    rdfs:label      "answer text"@en , "Antworttext"@de ;
    skos:definition "textual formulation of the answer option that, when selected at a \
parent classification node, determines the transition to this classification node in \
the sequential classification procedure"@en ;
    skos:definition "textliche Formulierung der Antwortoption, die bei Auswahl an einem \
übergeordneten Einreihungsknoten den Übergang zu diesem Einreihungsknoten im \
sequenziellen Einreihungsverfahren bestimmt"@de .

customs:hasMeasure
    rdfs:label      "has measure"@en , "hat Maßnahme"@de ;
    skos:definition "relation between a CN code and a TARIC measure under which goods \
classified by that CN code are subject to the regulatory conditions specified by the \
measure"@en ;
    skos:definition "Beziehung zwischen einem KN-Code und einer TARIC-Maßnahme, deren \
Regelungsbedingungen für Waren gelten, die unter diesen KN-Code eingereiht sind"@de .

customs:classifiesAs
    rdfs:label      "classifies as"@en , "wird eingereiht als"@de ;
    skos:definition "relation between a terminal classification node and the CN code to \
which goods are assigned upon completion of the sequential classification procedure \
initiated at the root node"@en ;
    skos:definition "Beziehung zwischen einem terminalen Einreihungsknoten und dem \
KN-Code, unter den Waren nach Abschluss des sequenziellen Einreihungsverfahrens, das \
am Wurzelknoten beginnt, eingereiht werden"@de .

customs:hasAnswer
    rdfs:label      "has answer"@en , "hat Antwort"@de ;
    skos:definition "relation between a classification node and a subsequent \
classification node reached by selecting a particular answer to the discriminating \
question posed at the source node"@en ;
    skos:definition "Beziehung zwischen einem Einreihungsknoten und einem nachfolgenden \
Einreihungsknoten, der durch Auswahl einer bestimmten Antwort auf die am Ausgangsknoten \
gestellte unterscheidende Frage erreicht wird"@de .

customs:belongsToChapter
    rdfs:label      "belongs to chapter"@en , "gehört zu Kapitel"@de ;
    skos:definition "relation between a CN code and the two-digit Harmonized System \
chapter in whose nomenclature scope the code is situated"@en ;
    skos:definition "Beziehung zwischen einem KN-Code und dem zweistelligen Kapitel des \
Harmonisierten Systems, in dessen Nomenklaturgeltungsbereich der Code fällt"@de .
```

**Patterns to follow:**
- rdflib `Namespace` + `Graph.bind()` for prefix management
- OWL 2 axioms via `graph.add((cls, RDF.type, OWL.Class))`, etc. — no external OWL library needed for TBox construction

**Test scenarios:**
- Happy path: `cn_code_iri("22042100")` and `cn_code_iri("22042100")` return identical `URIRef` (determinism)
- Happy path: `taric_measure_iri("123456")` and `classification_node_iri(["Q1:yes", "Q2:no"])` produce valid URIRef strings in the CUSTOMS namespace
- Edge case: `classification_node_iri([])` (root node, empty path) → produces a stable IRI (test that it doesn't raise)
- Happy path: `build_tbox(Graph())` returns a graph with at least 6 class declarations and 10 property declarations; serializes to valid Turtle without error
- Happy path: every class and property in the TBox has exactly two `skos:definition` triples (one `@en`, one `@de`) — query with SPARQL `SELECT ?term WHERE { ?term a owl:Class . FILTER NOT EXISTS { ?term skos:definition ?d . FILTER(LANG(?d) = "en") } }`
- Edge case: calling `build_tbox` twice on the same graph → no duplicate triples (idempotent TBox construction)

**Verification:**
- All unit tests pass
- `rdflib.Graph.parse(data=tbox_graph.serialize(format="turtle"), format="turtle")` round-trips without error
- Konclude CLI invoked on the TBox-only Turtle file returns exit code 0 and reports `consistent`

---

- [x] **Unit 6: Ontology ABox population and serialization**

**Goal:** Load the intermediate JSON for Chapter 22 (wizard tree + TARIC measures), mint deterministic IRIs, create OWL individuals with all required properties and provenance annotations, and serialize to `data/ontology/ch22.ttl` and `data/ontology/ch22.trig`.

**Requirements:** R5, R6, R7, R8, R9, R11

**Dependencies:** Units 2, 3, 4, 5

**Files:**
- Create: `src/ontology/abox.py`
- Create: `src/ontology/provenance.py`
- Test: `tests/unit/test_abox.py`
- Test: `tests/integration/test_abox_integration.py`

**Approach:**
- `abox.py`: `build_abox(chapter_data: ChapterData, wizard_tree: WizardTree, graph: Graph) -> Graph`
  - For each `TARICMeasure`: mint IRI via `taric_measure_iri(measure.sid)`, add type `customs:TARICMeasure`, add all data properties, add `MeasureComponent` sub-individuals for each duty expression
  - For each `ClassificationNode`: mint IRI via `classification_node_iri(node.path_from_root)`, add type, `customs:questionText`, `customs:isAdvisoryOnly = true`, `dcterms:source = <EZT-Online URL>`, `dcterms:created = today`; add `customs:hasAnswer` edges to next nodes; add `customs:classifiesAs` to CN code IRI if terminal
  - For each CN code encountered: mint IRI via `cn_code_iri(code)`, add type `customs:CNCode`, `customs:codeString`, `skos:prefLabel` (EN + DE if available), `customs:hasMeasure` edges to all applicable measure IRIs
  - Build CN hierarchy skeleton: infer Chapter/Heading/Subheading individuals from code string prefix slicing; add `customs:inChapter` / `customs:inHeading` etc.
- `provenance.py`: `build_provenance(graph: Dataset, run_id: str, chapter: int, sources: list[str])` — creates a `prov:Activity` individual in a named graph `customs:provenance`, links all individuals with `prov:wasGeneratedBy`
- Serialize: `ds.serialize(destination="data/ontology/ch22.trig", format="trig")` for the full Dataset; extract default graph and serialize to `format="longturtle"` for `ch22.ttl`

**Execution note:** Implement ABox population test-first — write failing tests against expected Turtle output for a minimal 3-node wizard + 1 measure fixture before implementing `abox.py`.

**Patterns to follow:**
- rdflib `Dataset` (not `ConjunctiveGraph`) — use `Dataset` with named graphs for provenance
- `format="longturtle"` for git-diffable single-graph Turtle output
- `format="trig"` when serializing multi-graph Dataset

**Test scenarios:**
- Happy path: 2-node wizard (root + terminal `cn_code="22042100"`) + 1 measure (sid="999") → output Turtle contains exactly `customs:CNCode_<uuid>` individual with `customs:codeString "22042100"`, linked to measure individual and terminal ClassificationNode
- Happy path: determinism — calling `build_abox` twice with same inputs, then sorting both outputs and diffing → identical (tests R11 at unit level)
- Edge case: wizard tree with a non-terminal node that also appears as a next-node target from two different parent nodes → single IRI minted, not duplicated
- Edge case: TARIC measure with `validity_end = None` → no `customs:validityEnd` triple added (not `customs:validityEnd "None"`)
- Edge case: CN code `22042100` appears as terminal in two different wizard paths → single `customs:CNCode` individual with two `customs:classifiesAs` incoming edges (graph has both; individual not duplicated)
- Integration: load Chapter 22 fixture JSON, build ABox, serialize to Turtle, parse back with rdflib → graph size ≥ 100 triples, `CONSTRUCT { ?s a customs:TARICMeasure }` via rdflib returns ≥1 result

**Verification:**
- Unit tests pass
- `rdflib.Graph.parse(format="turtle")` round-trips the serialized output without error
- Sorted NTriples output from two identical pipeline runs is byte-identical (idempotency at output level)

---

- [x] **Unit 7: Konclude OWL 2 DL consistency check integration**

**Goal:** Wrap the Konclude WASM CLI in a Python helper that validates the merged ontology (TBox + ABox) for OWL 2 DL consistency, with correct Node.js flags.

**Requirements:** Supports success criteria (consistent ontology), Key Decisions (Konclude as designated reasoner)

**Dependencies:** Units 5, 6

**Files:**
- Create: `src/reasoning/konclude.py`
- Test: `tests/integration/test_konclude.py`

**Approach:**
- `check_consistency(ttl_path: Path) -> bool`: invokes `node --experimental-wasm-threads --experimental-wasm-bulk-memory /home/hanke/rdf-reasoner-konclude/dist/cli.js --input {ttl_path} --mode classify --format ttl`; captures stdout; returns `True` if exit code 0
- `KONCLUDE_CLI_PATH` constant pointing to the rdf-reasoner-konclude dist directory — this is a cross-repo path reference, documented explicitly
- Timeout: 120 seconds (generous for Chapter 22, which has a small ontology)
- On non-zero exit: raise `KoncludeConsistencyError` with stderr content
- Log inferred triple count from stdout to confirm reasoning ran (not just loaded)

**Approach note — no absolute path hardcoding in code:** Store the Konclude path as an environment variable `KONCLUDE_CLI_PATH` with a fallback to the known location. This makes the pipeline portable if the rdf-reasoner-konclude repo moves.

**Test scenarios:**
- Happy path: TBox-only Turtle fixture (`owl:Class` declarations, no ABox) → consistency check returns `True`, exit code 0
- Happy path: small ABox with one `customs:CNCode` individual typed correctly → consistent, inferred triples contain at least the input triples
- Error path: ontology with explicit `owl:disjointWith` contradiction (class A and class B disjoint, individual `x` typed as both) → `KoncludeConsistencyError` raised
- Error path: Node.js `--experimental-wasm-threads` flag omitted → test fixture with property chains included → verify timeout or deadlock detected within 10 seconds (this tests that the production wrapper always includes the flags)
- Integration: Chapter 22 combined TBox+ABox Turtle → consistent, completes within 60 seconds

**Verification:**
- Integration test with Chapter 22 ontology passes and logs inferred triple count
- A hand-crafted inconsistent ontology (two disjoint classes, one individual typed as both) raises `KoncludeConsistencyError`

---

- [x] **Unit 8: SPARQL store and Chapter 22 acceptance test**

**Goal:** Load the Chapter 22 ontology into a pyoxigraph in-memory store and execute the SPARQL acceptance test: query for the MFN ad-valorem duty rate on CN 2204 21 (still wine ≤2L, non-EU non-preferential origin), verify it matches the value confirmed from the CIRCABC source data.

**Requirements:** R12, Success Criteria (SPARQL query)

**Dependencies:** Units 2, 3, 6

**Files:**
- Create: `src/sparql/store.py`
- Test: `tests/acceptance/test_chapter22_sparql.py`

**Approach:**
- `store.py`: `OntologyStore` class wrapping `pyoxigraph.Store()` (in-memory). `load_turtle(path: Path)` calls `store.bulk_load(path=str(path), format=RdfFormat.TURTLE)`. `query(sparql: str) -> list[dict]` wraps `store.query(sparql, use_default_graph_as_union=True)` and returns results as list of dicts.
- Acceptance test: query for the MFN rate on CN 2204 21:
  ```sparql
  SELECT ?rate ?unit WHERE {
    ?measure a customs:TARICMeasure ;
             customs:codeString ?code ;
             customs:measureTypeId "103" ;
             customs:geographicalScope "1011" ;
             customs:dutyAmount ?rate ;
             customs:validityStart ?start .
    FILTER(STRSTARTS(?code, "220421"))
    FILTER(?rate > 0)
  }
  ```
- Expected value: MFN rate for CN 2204 21 confirmed against CIRCABC source data during Unit 3 implementation. Store the expected value as a test constant (e.g., `EXPECTED_MFN_RATE_2204_21 = 13.4` — actual value to be confirmed from source data).
- `use_default_graph_as_union=True` — provenance triples are in named graphs; ontology triples are in default graph.
- ASK query returns `QueryBoolean`, not Python `bool` — convert explicitly.

**Patterns to follow:**
- pyoxigraph 0.5.8 API: `RdfFormat.TURTLE` (not MIME string), `QueryBoolean` handling

**Test scenarios:**
- Happy path: Chapter 22 Turtle loaded → SPARQL COUNT query returns ≥10 `customs:TARICMeasure` individuals
- Happy path: MFN rate for CN 2204 21 → result set non-empty, rate matches `EXPECTED_MFN_RATE_2204_21` (from CIRCABC source, set during Unit 3)
- Happy path: ASK `{ ?x a customs:ClassificationNode }` → `bool(result)` is `True`
- Edge case: empty store → SPARQL SELECT returns empty list, no exception
- Edge case: malformed SPARQL → pyoxigraph raises `SyntaxError`, not silent empty result
- Integration: root ClassificationNode of Chapter 22 wizard tree reachable from SPARQL by filtering for nodes with no incoming `customs:hasAnswer` edge

**Verification:**
- All acceptance tests pass
- `EXPECTED_MFN_RATE_2204_21` constant has a code comment citing the CIRCABC source and date of confirmation

---

- [x] **Unit 9: Chapter-parameterized orchestration script**

**Goal:** Wire all components into a single `src/pipeline.py` script that accepts `--chapter N` and runs the full pipeline end-to-end, respecting checkpoints, enforcing idempotency, and reporting timing.

**Requirements:** R4, R10, R11, Success Criteria (30-minute runtime)

**Dependencies:** Units 3, 4, 6, 7, 8

**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/integration/test_pipeline.py`

**Approach:**
- CLI interface: `python -m src.pipeline --chapter 22 [--skip-scrape] [--skip-fetch] [--no-reasoner]`
- Step sequence with timing per step:
  1. Fetch TARIC XML → `data/intermediate/taric_ch{N}.json` (skip if exists + `--skip-fetch`)
  2. Scrape wizard → `data/intermediate/wizard_ch{N}.jsonl` (skip if exists + `--skip-scrape`)
  3. Build TBox + ABox → `data/ontology/ch{N}.ttl` + `ch{N}.trig`
  4. Konclude consistency check (skip if `--no-reasoner`)
  5. SPARQL acceptance test (Chapter 22 only: compare against expected MFN rate)
- Idempotency: if output files already exist and `--force` not passed, steps 1-3 are skipped. This is the primary idempotency mechanism; UUID5 IRI minting ensures re-population from same JSON also yields identical Turtle.
- Print total elapsed time at end. Exit non-zero if any step fails.
- `--chapter` parameter is a plain integer; no other code changes needed to process a different chapter (R4 / success criterion).

**Test scenarios:**
- Happy path (integration, mocked steps): pipeline with all steps mocked → called in correct order, timing printed, exit code 0
- Edge case: `--skip-scrape` with no existing wizard JSON → raise `FileNotFoundError` with helpful message (not a silent empty tree)
- Edge case: Konclude consistency check fails → pipeline exits non-zero, error message includes stderr from Konclude
- Edge case: `--chapter 22` with existing output files → steps 1-3 skipped, step 4 (Konclude) still runs (re-validates existing output)
- Integration: pipeline `--chapter 22 --skip-scrape --skip-fetch` with pre-built fixture JSON → produces valid `ch22.ttl`, Konclude passes, SPARQL acceptance test passes (end-to-end from JSON to accepted query)

**Verification:**
- Integration test with fixture JSON completes in < 2 minutes (excluding Playwright and network I/O)
- Full pilot run `--chapter 22` completes in under 30 minutes on development machine with pre-downloaded CIRCABC XML
- Sorted NTriples diff of two identical `--chapter 22` runs against same input JSON produces empty diff (idempotency at output level)

---

## System-Wide Impact

- **External service dependencies:** EZT-Online (`auskunft.ezt-online.de`) and CIRCABC are external; pipeline must tolerate HTTP timeouts gracefully. Both are government services — no SLA guarantees.
- **State lifecycle risks:** Playwright wizard traversal is stateful; interrupted runs must checkpoint before exit. The checkpoint file and the final wizard JSONL are append-only to prevent partial-write corruption.
- **Idempotency invariant:** All IRIs are deterministically derived from source data strings. The invariant is: given identical intermediate JSON input, output Turtle is byte-identical. Tests in Unit 6 and Unit 9 verify this.
- **Konclude cross-repo path:** The pipeline references `/home/hanke/rdf-reasoner-konclude/dist/cli.js` from a sibling repo. Document this in `README.md` and in the `KONCLUDE_CLI_PATH` environment variable. If the rdf-reasoner-konclude repo is not present, the reasoner step fails with a clear error.
- **rdflib `Dataset` / multi-graph serialization:** The `.trig` file contains provenance in named graphs. The `.ttl` file contains only the default graph (asserted ontology). SPARQL acceptance tests load `.ttl` — provenance metadata is not SPARQL-queryable from the `.ttl` file. This is intentional.
- **Unchanged invariants:** The rdf-reasoner-konclude package is used as-is; this plan makes no changes to it. All integration is via the documented CLI interface.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| EZT wizard session expires mid-traversal | Checkpoint/resume every 50 nodes; session expiry detection + re-login (no auth) + replay from checkpoint |
| CIRCABC file URLs change (direct download path unstable) | Fall back to prompting user for local XML path; document download steps in README |
| Chapter 22 wizard tree larger than ~50 CN codes implies | Manual spot-traversal (Unit 4) bounds this before automation; 30-min budget includes contingency |
| Konclude deadlock on `AllDisjointClasses` via NTriples path | Always use Turtle (`--input`) for Konclude; avoid `AllDisjointClasses` in ABox |
| pyoxigraph 0.5 API incompatibility with future 0.6 | Pin `pyoxigraph>=0.5.8,<0.6` in requirements; 0.5 → 0.6 migration guide exists if upgrade needed |
| TARIC XML schema varies between full-snapshot and delta files | Parse and validate against Pydantic schema immediately after download; delta files apply updates not replacement — use full-snapshot for pilot |
| rdf-reasoner-konclude repo not present on target machine | Document dependency and provide fallback `--no-reasoner` flag |
| EZT wizard structure differs for other chapters (R4 claim) | Validate R4 by running `--chapter N` on one structurally different chapter (e.g., Chapter 84) after pilot; scope success criterion note accordingly |

## Documentation / Operational Notes

- Add `README.md` section documenting: Konclude path dependency, Playwright browser install step (`playwright install chromium`), CIRCABC download procedure, and `--no-reasoner` fallback.
- The pilot acceptance test constant `EXPECTED_MFN_RATE_2204_21` must be confirmed against CIRCABC source data during Unit 3 and set with a citation comment.
- Legal disclaimer: the ontology README must state that EZT-Online classification paths are advisory aids, not legally binding EU instruments. Each ClassificationNode in the ontology also carries this as an `rdfs:comment` annotation.

## Sources & References

- **Origin document:** [docs/brainstorms/eu-customs-ontology-requirements.md](docs/brainstorms/eu-customs-ontology-requirements.md)
- **EZT-Online live URL:** `https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do`
- **CIRCABC TARIC group:** `https://circabc.europa.eu/ui/group/0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b`
- **EU Open Data TARIC:** `https://data.europa.eu/data/datasets/eu-customs-tariff-taric`
- **TARIC3 XML schema doc:** `https://circabc.europa.eu/d/d/versionStore/version2Store/724b4f5b-356f-4048-a00a-50b38780f5ba/Explanation%20files%20for%20the%20Taric%20database%20extractions.pdf`
- **Konclude CLI:** `/home/hanke/rdf-reasoner-konclude/dist/cli.js` (sibling repo)
- **Konclude CLAUDE.md:** `/home/hanke/rdf-reasoner-konclude/CLAUDE.md`
- **rdflib 7.6.0 changelog:** https://rdflib.readthedocs.io/en/stable/changelog/
- **pyoxigraph 0.5.8 docs:** https://pyoxigraph.readthedocs.io/en/stable/
- **OWL 2 Primer:** https://www.w3.org/TR/owl2-primer/
- **PROV-O:** https://www.w3.org/TR/prov-o/
- **Playwright Python docs:** https://playwright.dev/python/docs/api/class-playwright
