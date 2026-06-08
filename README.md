# eu-customs-ontology

OWL ontology for assigning EU customs codes and tariff regulations to products. Integrates legally binding TARIC tariff measures with the EU Commission's interactive product classification tree.

OWL classes and individuals are published under the persistent IRI base **`https://w3id.org/eucn`**.

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
| Build OWL ontology | `data/ontology/eucn-ch{N}-{date}.ttl` + `.trig` |
| Konclude consistency check | OWL DL consistency (exit 1 if inconsistent) |
| SPARQL acceptance test | MFN rate validation (chapter 22 only) |

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

**Change detection:** SHA256 of the generated TTL is compared to the committed value in `.github/cache/ch{N}-ttl.sha256`. A release is created only when the hash differs (or `force_rebuild=true`). The cache file is updated after each release so subsequent runs skip unchanged chapters.

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

## Repository Layout

```
.github/
  cache/              SHA256 of last-released TTL per chapter (committed)
  workflows/
    build-release.yml   Weekly rebuild, change detection, GitHub Release
    docs.yml            Widoco HTML docs → gh-pages branch
data/
  intermediate/       Fetcher + scraper cache (gitignored)
  ontology/           Built TTL + TRIG files
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
