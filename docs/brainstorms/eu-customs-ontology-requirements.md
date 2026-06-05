---
date: 2026-06-05
topic: eu-customs-ontology
---

# EU Customs Ontology

## Problem Frame

Importers, exporters, customs brokers, and compliance systems need to determine (a) the correct CN/HS code for a product and (b) all EU regulatory obligations tied to that code — tariff rates, duty suspensions, import/export restrictions, licenses, and quotas. Today this knowledge is fragmented across EZT-Online's interactive wizard, the EU TARIC database, and EUR-Lex legal texts. There is no machine-readable, reasoning-capable representation of the full classification-to-regulation pipeline. This project builds that: an OWL 2 ontology capturing both the classification decision tree and the regulatory measures, with automation scripts to populate it from authoritative sources.

## Requirements

**Data Acquisition**

- R1. A Playwright-based scraper traverses the EZT-Online sequential classification wizard (`SeqEinreihungSucheAnzeige.do`) and captures all decision-tree branches as structured data (question text, answer options, next-state references, terminal CN code). The scraper performs a manual spot-traversal first to bound graph size (depth, branching factor, cycle detection) before full automated traversal is attempted.
- R2. A TARIC data fetcher downloads tariff measures for each CN code (duty rates, suspensions, quotas, import/export controls, licensing requirements, linked legal references) from the EU Open Data Portal bulk XML export and/or the CIRCABC TARIC distribution group. Each fetched measure includes its validity period and measure sequence number for stable identification.
- R3. Both tools produce a clean, intermediate JSON representation that is independent of the ontology serialization format. The JSON schema is designed contract-first (before R1/R2 are implemented) and defines: node identifier convention, answer-edge structure, terminal-node discriminator for the wizard tree, and measure sequence number as the identity key for TARIC measures.
- R4. Scripts accept a CN chapter number as a parameter; the pilot targets Chapter 22. Cross-chapter structural uniformity is validated against at least one additional chapter before the "no code changes" claim is asserted.

**Ontology Structure**

- R5. The ontology models the CN code hierarchy: Section → Chapter → Heading (4-digit) → Subheading (6-digit) → CN code (8-digit) → TARIC code (10-digit).
- R6. Each CN code individual carries: code string, description text (EN + DE), legal note references, and links to applicable TARIC measures.
- R7. TARIC measures are modeled as individuals with properties: measure type, duty rate or condition, geographic scope (origin country), validity period, linked regulation. The measure sequence number from the EU source is used as the stable IRI key.
- R8. The classification decision tree is represented as a graph of `ClassificationNode` individuals linked by `hasAnswer` edges, each terminal node `classifiesAs` a CN code individual. Each node carries a provenance annotation: source (`EZT-Online`), capture date, and a disclaimer that EZT content is an advisory aid, not a legally binding EU instrument.
- R9. The ontology serializes to RDF/Turtle (`.ttl`) as primary format. JSON-LD export is deferred to a post-pilot phase unless a concrete downstream consumer is identified.

**Pipeline and Automation**

- R10. A single orchestration script runs the full pipeline: scrape wizard → fetch TARIC → merge → write ontology files.
- R11. The pipeline is idempotent: re-running against the same chapter produces the same output (no duplicate individuals). Idempotency relies on deterministic IRI minting: CN code individuals keyed by code string; TARIC measure individuals keyed by measure sequence number; ClassificationNode individuals keyed by a root-to-node path string derived from wizard question/answer labels.
- R12. The pilot processes Chapter 22 (Beverages, spirits and vinegar, ~50 CN codes) end-to-end and validates output.

## Success Criteria

- Chapter 22 ontology is complete: all CN codes present, each with at least one MFN duty rate measure and correct decision-tree path from root.
- A SPARQL query for the MFN ad-valorem rate for CN 2204 21 (still wine ≤2L containers, non-EU non-preferential origin) returns the value matching the current Official Journal TARIC regulation — the expected value is confirmed from the EU Open Data source before the test is run.
- The orchestration script runs unattended for Chapter 22 in under 30 minutes on a standard development machine with unthrottled internet (TARIC bulk download latency is excluded from the budget if a pre-downloaded XML snapshot is used).
- A manual spot-traversal of the Chapter 22 wizard is completed and node count documented before automated traversal begins.

## Scope Boundaries

- Does not cover export declarant procedures (ECS), only import classification and duty.
- Does not include anti-dumping or countervailing duty measures in the pilot (can be added in later chapters).
- Does not build a UI or chatbot — ontology + scripts only.
- Legal text full-text is out of scope; only regulation identifiers and article references are captured.
- Non-EU preferential tariff schedules (GSP, bilateral FTAs) are deferred beyond pilot.
- JSON-LD export is out of scope for the pilot.
- Cross-chapter parameterization (R4) is validated in a second chapter but not automated beyond the pilot.

## Key Decisions

- **Hybrid data sourcing:** EU Open Data / CIRCABC bulk XML export for TARIC measures (authoritative, structured); EZT-Online wizard for classification decision tree logic (advisory, not available in structured form elsewhere). Pipelines are fault-isolated.
- **OWL 2 DL + RDF/Turtle:** Supports SPARQL querying and OWL 2 DL class inference via Konclude (WASM module in `rdf-reasoner-konclude`). Konzlude is the designated reasoner; rdflib handles RDF I/O.
- **Konclude (WASM) as OWL 2 DL reasoner:** Already available in the repo ecosystem (`rdf-reasoner-konclude`). Used for class inference validation; SPARQL queries run against Jena Fuseki or Oxigraph to avoid the rdflib/pyparsing 3.x compatibility issue.
- **Chapter 22 as pilot:** Heavy regulatory burden validates the TARIC measures pipeline; moderate wizard complexity validates the scraping approach without full-scale commitment.
- **Contract-first intermediate JSON schema:** Schema is designed before scrapers are built so both R1 and R2 conform to the same contract; prevents scraper output from driving ontology semantics.
- **Deterministic IRI minting:** IRIs are derived from stable source identifiers (code strings, measure sequence numbers, path-based node keys) to satisfy idempotency (R11) without a deduplication post-pass.
- **EZT content is advisory-only:** Provenance annotations on all ClassificationNode individuals; ontology documentation states EZT is a national interpretation aid, not a legally binding EU instrument.

## Dependencies / Assumptions

- EZT-Online sequential classification wizard is accessible (URL and auth model to be confirmed — see Outstanding Questions).
- TARIC bulk data is available via EU Open Data Portal (`data.europa.eu`) and/or CIRCABC group `0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b` without registration barriers for download.
- Konclude WASM module (`rdf-reasoner-konclude`) is callable from the pipeline toolchain (Node.js or Python subprocess).
- The classification wizard state machine is finite and acyclic for Chapter 22 (to be verified by manual spot-traversal before full automated run).

## Outstanding Questions

### Resolve Before Planning

- **[Affects R1][Needs research]** Confirm EZT-Online wizard: full base URL, whether login is required, and whether the wizard is server-rendered (Struts/JSP form POSTs — Playwright-amenable) or a client-rendered SPA (requires full browser execution). The German `www2.zoll.de` URL is unreachable; the correct host must be identified.

### Deferred to Planning

- **[Affects R1][Technical]** Optimal Playwright strategy for wizard traversal (BFS vs DFS; session persistence; checkpoint/resume on timeout).
- **[Affects R5–R8][Technical]** OWL ontology design: class definitions, property axioms, annotation properties for multilingual labels, provenance annotation schema.
- **[Affects R3][Technical]** JSON intermediate schema: finalize node identifier convention, answer-edge encoding, and measure sequence number field names.
- **[Affects R2][Technical]** EU Open Data / CIRCABC bulk XML schema analysis: confirm field names for measure sequence number, validity dates, and geographic scope before implementing the fetcher.
- **[Affects R10][Technical]** Konclude WASM integration: confirm Python/Node.js subprocess invocation pattern for OWL 2 DL consistency checking within the pipeline.

## Next Steps

-> Resolve the EZT wizard URL/access question (one remaining `Resolve Before Planning` item), then -> `/ce-plan`.

---

```
Classification Pipeline Overview

  Product description
        │
        ▼
  ┌─────────────────┐
  │  Decision Tree  │  ← EZT-Online SeqEinreihung wizard (scraped)
  │  ClassificationNode chain (provenance annotated)        │
  └────────┬────────┘
           │ classifiesAs
           ▼
     CN Code (8-digit)
           │
           ▼
  ┌─────────────────┐
  │  TARIC Measures │  ← EU Open Data / CIRCABC bulk XML
  │  Duty rates     │
  │  Restrictions   │
  │  Licenses       │
  └─────────────────┘
           │
           ▼
  OWL 2 Ontology (.ttl)
  Reasoner: Konclude (WASM)
  SPARQL: Jena Fuseki / Oxigraph
```
