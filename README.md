# eu-customs-ontology

OWL ontology for assigning EU customs codes and tariff regulations to products. Integrates legally binding TARIC tariff measures with the EU Commission's interactive product classification tree.

OWL classes and individuals are published under the persistent IRI base **`https://w3id.org/eucn`**.

## Ontology Architecture

The OWL 2 DL ontology uses a **production-process restriction pattern** for individual classification. Each CN heading is defined by an `owl:equivalentClass` axiom combining `eucn:producedBy` (an `owl:FunctionalProperty` `owl:ObjectProperty`) `hasValue` restrictions on named process singleton individuals (e.g. `eucn:malt-fermentation`) with numeric range restrictions on `eucn:alcoholByVolumePercent`. Process singletons are typed as `bfo:Process` subclasses with pairwise `owl:disjointWith` between classes and `owl:differentFrom` between individuals to enable world-closure under OWA. Phase 2 classes (Spirit, EthylAlcohol) use graph-derived `NOT(producedBy = X)` complement restrictions for the remaining headings.

```turtle
# Example: Beer ≡ (malt fermentation ∩ ABV > 0.5%)
eucn:Beer owl:equivalentClass [
    owl:intersectionOf (
        [ owl:onProperty eucn:producedBy ; owl:hasValue eucn:malt-fermentation ]
        [ owl:onProperty eucn:alcoholByVolumePercent ;
          owl:someValuesFrom [ owl:onDatatype xsd:decimal ;
            owl:withRestrictions ([ xsd:minExclusive 0.5 ]) ] ]
    )
] .
```

See [docs/ontology-patterns.md](docs/ontology-patterns.md) for the full pattern specification, world-closure mechanics, and a step-by-step guide for adding new chapters.

## Data Sources

| Source | What it provides | URL |
|--------|-----------------|-----|
| CIRCABC Duties Import | TARIC tariff measures for CN chapters 01-99 (duty rates, validity dates, geographic scope) | [CIRCABC group](https://circabc.europa.eu/ui/group/0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b) |
| EZT-Online wizard | EU Commission classification decision tree (non-binding advisory guidance) | [auskunft.ezt-online.de](https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do) |

Both sources are public and require no authentication.

## Local Usage

### Prerequisites

- Python ≥ 3.11
- Node.js ≥ 20 (for the bundled Konclude WASM reasoner)
- Playwright Chromium: `playwright install --with-deps chromium`

### Install

```bash
pip install -r requirements.txt
```

### Run the pipeline

```bash
# Build chapter 22 (Beverages) — the current pilot chapter
python -m src.pipeline --chapter 22

# Common flags
python -m src.pipeline --chapter 22 --skip-scrape   # reuse cached wizard data
python -m src.pipeline --chapter 22 --skip-fetch    # reuse cached TARIC data
python -m src.pipeline --chapter 22 --no-reasoner   # skip Konclude check
python -m src.pipeline --chapter 22 --force         # rebuild all outputs
```

The pipeline runs five stages in sequence:

| Stage | Output |
|-------|--------|
| Fetch TARIC | `data/intermediate/taric_ch{N}.json` |
| Scrape EZT-Online wizard | `data/intermediate/wizard_ch{N}.jsonl` |
| Build core TBox | `data/ontology/eucn-core-{date}.ttl` + `eucn-core-latest.ttl` |
| Build chapter ontology | `data/ontology/eucn-ch{N}-{slug}-{date}.ttl` + `eucn-ch{N}-{slug}-latest.ttl` + `.trig` |
| Konclude consistency check | OWL DL consistency (exit 1 if inconsistent) |

The Konclude OWL reasoner is bundled in `tools/konclude/` (WASM, requires Node.js). Override the path with the `KONCLUDE_CLI_PATH` environment variable.

## CI/CD Workflows

All automation lives in [`.github/workflows/`](.github/workflows/).

### `build-release.yml` — Weekly rebuild and release

Runs every Monday at 06:00 UTC. Also triggered manually.

**Workflow dispatch inputs:**

| Input | Default | Description |
|-------|---------|-------------|
| `chapters` | `22` | Chapters to build: `22`, `all`, or comma-separated (e.g. `22,23`) |
| `dry_run` | `false` | Build and test without creating a GitHub Release |
| `force_rebuild` | `false` | Release even if the output TTL is identical to the last release |

**Job flow:**

```
setup
  Parses the `chapters` input into a JSON matrix.
  "all" expands to chapters 01-99.
  ↓
build  [one job per chapter, parallel]
  1. pip install -r requirements.txt
  2. playwright install --with-deps chromium (cached by requirements hash)
  3. python -m src.pipeline --chapter N --force
       → fetches TARIC XLSX from CIRCABC (public URL, no auth)
       → scrapes EZT-Online wizard via Playwright / Chromium
       → builds OWL ontology (TBox + ABox + provenance graph)
       → Konclude WASM consistency check (tools/konclude/cli.js)
       → SPARQL acceptance test (MFN rate validation)
  4. SHA256 of generated TTL vs. .github/cache/ch{N}-ttl.sha256
     → upload artifact if changed (or force_rebuild=true)
  ↓
release  (skipped when no chapters changed or dry_run=true)
  Downloads all ontology-ch* artifacts.
  gh release create  tag=ontology-YYYY-MM-DD-rN
    attaches TTL + TRIG for all changed chapters
  Commits updated SHA256 hashes to .github/cache/ [skip ci].
  Dispatches repository_dispatch "trigger-docs" → docs.yml.
  ↓
summary  (always)
  Writes a GitHub Actions job summary table.
  Notes "Dry run" when dry_run=true.
```

**Change detection:** SHA256 of `eucn-ch{N}-latest.ttl` is compared to `.github/cache/ch{N}-ttl.sha256`. SHA256 of `eucn-core-latest.ttl` is stored in `.github/cache/core-ttl.sha256`. Release is created only when a hash differs (or `force_rebuild=true`). Cache files are updated after each release.

---

### `docs.yml` — Versioned HTML documentation

Generates [Widoco](https://github.com/dgarijo/Widoco) HTML documentation from a chapter TTL and publishes it to the `gh-pages` branch, accumulating version history without overwriting older releases.

**Triggers:**
- Automatically: `repository_dispatch "trigger-docs"` sent by `build-release.yml` after each GitHub Release.
- Manually: `workflow_dispatch` — specify a release tag or leave empty to rebuild `/dev/`.

**Workflow dispatch inputs:**

| Input | Default | Description |
|-------|---------|-------------|
| `version` | _(empty)_ | Release tag to document (e.g. `ontology-2026-06-08-r1`). Empty rebuilds `/dev/` from the latest committed TTL. |
| `chapter` | `22` | Chapter to document |

**Job flow:**

```
check
  Resolves version and chapter.
  Priority: repository_dispatch payload → workflow_dispatch input → "latest"
  ↓
build-and-deploy
  Fetches existing gh-pages branch (to rebuild the version index).

  Resolve TTL:
    version="latest" → use TTL committed in data/ontology/
    version=tag      → gh release download <tag> *.ttl

  java -jar widoco.jar -ontFile <TTL> -outFolder _site/<version>/doc/ \
    -lang en-de -uniteSections -webVowl -getOntologyMetadata ...

  Updates /dev/ (always).
  Regenerates root index.html (releases only).
  peaceiris/actions-gh-pages  keep_files=true → gh-pages branch
```

**Resulting Pages structure:**

```
/                           root index — lists all releases
/dev/doc/                   latest release (updated automatically)
/ontology-YYYY-MM-DD-r1/doc/   specific release, preserved forever
/ontology-YYYY-MM-DD-r2/doc/   next release, alongside the previous
...
```

**One-time setup:** After the first workflow run, go to:
> Settings → Pages → Build and deployment → Source
> Change from **"GitHub Actions"** to **"Deploy from a branch"** — branch `gh-pages`, folder `/ (root)`.

---

## Live Demo

**[Open in Ontosphere →](https://thhanke.github.io/ontosphere/?rdfUrl=https://raw.githubusercontent.com/ThHanke/eu-customs-ontology/refs/heads/main/demo/ch22-beverages-demo.ttl)**

Ontosphere runs WASM Konclude in the browser. It loads [`demo/ch22-beverages-demo.ttl`](demo/ch22-beverages-demo.ttl) — which imports the main ontology — then classifies 10 beverage individuals in real time.

## Product Classification Demo

The ontology uses OWL 2 DL equivalence axioms to classify products automatically. Describing a beverage with its production process and physical properties is enough for a reasoner to infer its CN product class — no explicit type assertion needed.

Each CN heading is linked to a named **process singleton** (e.g. `eucn:malt-fermentation`) via `eucn:producedBy`, an `owl:FunctionalProperty` `owl:ObjectProperty`. The singletons are typed as `bfo:Process` subclasses with pairwise `owl:disjointWith` between classes, enabling world-closure under OWA.

### Describe a product

The ABox contains two kinds of individuals: **process instances** (typed as `eucn:*Process` BFO subclasses) linked to their beverage outputs via `obo:RO_0002234` (`has_output`), and **beverage individuals** with their discriminating data properties. `eucn:producedBy` (the inverse of `has_output`) is inferred automatically.

```turtle
@prefix demo: <https://w3id.org/eucn/demo/> .
@prefix eucn: <https://w3id.org/eucn/> .
@prefix obo:  <http://purl.obolibrary.org/obo/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .

# Process instances — typed as eucn:*Process (bfo:Process subclasses)
demo:malt-brew-1     a eucn:MaltFermentation ;  obo:RO_0002234 demo:czech-lager .
demo:grape-ferment-1 a eucn:GrapeFermentation ; obo:RO_0002234 demo:champagne-brut, demo:bordeaux-rouge .
demo:grain-distil-1  a eucn:GrainDistillation ;  obo:RO_0002234 demo:whisky-12y, demo:grain-spirit-96 .

# Beverage individuals — eucn:producedBy is inferred from the inverse
demo:champagne-brut  a owl:NamedIndividual ; eucn:isCarbonated "true"^^xsd:boolean .
demo:bordeaux-rouge  a owl:NamedIndividual ; eucn:isCarbonated "false"^^xsd:boolean .
demo:czech-lager     a owl:NamedIndividual ; eucn:alcoholByVolumePercent "5.0"^^xsd:decimal .
demo:whisky-12y      a owl:NamedIndividual ; eucn:alcoholByVolumePercent "43.0"^^xsd:decimal .
demo:grain-spirit-96 a owl:NamedIndividual ; eucn:alcoholByVolumePercent "96.0"^^xsd:decimal .
demo:still-water     a owl:NamedIndividual ; eucn:alcoholByVolumePercent "0.0"^^xsd:decimal .
```

### What the reasoner infers

| Individual | Inferred types | Inferred `cnHeadingCode` |
|------------|----------------|--------------------------|
| `demo:champagne-brut` | `eucn:SparklingWine` · `eucn:Wine` · `eucn:Beverage` | `220410` |
| `demo:bordeaux-rouge` | `eucn:StillWine` · `eucn:Wine` · `eucn:Beverage` | `220421` |
| `demo:apple-cider` | `eucn:FermentedBeverage` · `eucn:Beverage` | `2206` |
| `demo:dry-vermouth` | `eucn:FlavouredWine` · `eucn:Beverage` | `2205` |
| `demo:malt-vinegar` | `eucn:Vinegar` · `eucn:Beverage` | `2209` |
| `demo:sparkling-lemonade` | `eucn:NonAlcoholicBeverage` · `eucn:Beverage` | `2202` |
| `demo:czech-lager` | `eucn:Beer` · `eucn:Beverage` | `2203` |
| `demo:whisky-12y` | `eucn:Spirit` · `eucn:Beverage` | `2208` |
| `demo:grain-spirit-96` | `eucn:EthylAlcohol` · `eucn:Beverage` | `2207` |
| `demo:still-water` | `eucn:Water` · `eucn:Beverage` | `2201` |

`eucn:cnHeadingCode` is inferred because each product class carries `rdfs:subClassOf [owl:onProperty eucn:cnHeadingCode; owl:hasValue "XXXX"]` — the reasoner propagates the value to every classified individual.

### How it works

`eucn:SparklingWine` is defined by an `owl:equivalentClass` axiom using `someValuesFrom` on the process class:

```turtle
eucn:SparklingWine owl:equivalentClass [
    a owl:Class ;
    owl:intersectionOf (
        [ owl:onProperty eucn:producedBy ; owl:someValuesFrom eucn:GrapeFermentation ]
        [ owl:onProperty eucn:isCarbonated ; owl:hasValue "true"^^xsd:boolean ]
    )
] .
```

Any individual produced by a `eucn:GrapeFermentation` process and marked carbonated is automatically classified as `SparklingWine`. `eucn:producedBy` is `owl:FunctionalProperty` (each beverage has exactly one producer) and the 7 process classes are pairwise `owl:disjointWith` — together these close the open world so Konclude can infer `NOT(∃producedBy.MaltFermentation)` for a grape-fermented individual, enabling discrimination of Spirit and EthylAlcohol by elimination.

---

## Repository Layout

```
.github/
  cache/              SHA256 of last-released TTL per chapter + core (committed)
                        ch{N}-ttl.sha256, core-ttl.sha256
  workflows/
    build-release.yml   Weekly rebuild, change detection, GitHub Release
    docs.yml            Widoco HTML docs → gh-pages branch
data/
  intermediate/       Fetcher + scraper cache (gitignored)
  ontology/           Built TTL + TRIG files
                        eucn-core-{date}.ttl, eucn-core-latest.ttl (stable alias)
                        eucn-ch{N}-{slug}-{date}.ttl, eucn-ch{N}-{slug}-latest.ttl
src/
  fetcher/            TARIC XML / XLSX fetcher (httpx + lxml)
  scraper/            Playwright EZT-Online wizard scraper
  ontology/           RDF builder: TBox, ABox, IRI minting, provenance
  reasoning/          Konclude OWL consistency check wrapper
  sparql/             Pyoxigraph SPARQL store
  pipeline.py         Main orchestration CLI
tools/
  konclude/           Bundled Konclude WASM reasoner (Node.js, 8 MB)
tests/
  unit/               Schema, IRI, OWL axiom tests
  integration/        Pipeline, fetcher, scraper, reasoning tests
  acceptance/         SPARQL MFN rate validation
```

## License

See [LICENSE](LICENSE).
