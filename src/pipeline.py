from __future__ import annotations

"""Chapter-parameterized EU customs ontology pipeline.

Usage:
    python -m src.pipeline --chapter 22 [--skip-scrape] [--skip-fetch]
                            [--xml-path PATH] [--no-reasoner] [--force]
"""

import argparse
import json
import logging
import shutil
import sys
import time
from datetime import date as Date
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import OWL, RDF

ROOT = Path(__file__).parent.parent
DATA_INTERMEDIATE = ROOT / "data" / "intermediate"
DATA_ONTOLOGY = ROOT / "data" / "ontology"
LOG_FILE = ROOT / "data" / "logs" / "pipeline.log"


def _configure_logging() -> None:
    fmt = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    # Quiet noisy third-party loggers
    for noisy in ("httpcore", "httpx", "anthropic._base_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _step(name: str):
    class _Timer:
        def __enter__(self):
            print(f"[{name}] starting...")
            self._t = time.perf_counter()
            return self

        def __exit__(self, *_):
            elapsed = time.perf_counter() - self._t
            print(f"[{name}] done in {elapsed:.1f}s")

    return _Timer()


def run(
    chapter: int,
    skip_fetch: bool = False,
    skip_scrape: bool = False,
    skip_legal_text: bool = False,
    xml_path: Path | None = None,
    xlsx_path: Path | None = None,
    no_reasoner: bool = False,
    no_classify: bool = False,
    force: bool = False,
    extract_date: Date | None = None,
    run_axiom_agent: bool = False,
    agent_model: str = "claude-sonnet-4-6",
) -> None:
    if extract_date is None:
        extract_date = Date.today()

    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Pipeline start: chapter=%d model=%s", chapter, agent_model if run_axiom_agent else "n/a")

    DATA_INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    DATA_ONTOLOGY.mkdir(parents=True, exist_ok=True)

    taric_json = DATA_INTERMEDIATE / f"taric_ch{chapter:02d}.json"
    wizard_jsonl = DATA_INTERMEDIATE / f"wizard_ch{chapter:02d}.jsonl"
    date_str = extract_date.isoformat()
    from src.ontology.chapter_registry import get_chapter
    slug = get_chapter(chapter).slug
    ttl_out = DATA_ONTOLOGY / f"eucn-ch{chapter:02d}-{slug}-{date_str}.ttl"
    ttl_latest = DATA_ONTOLOGY / f"eucn-ch{chapter:02d}-{slug}-latest.ttl"
    trig_out = DATA_ONTOLOGY / f"eucn-ch{chapter:02d}-{slug}-{date_str}.trig"
    core_ttl_out = DATA_ONTOLOGY / f"eucn-core-{date_str}.ttl"
    core_ttl_latest = DATA_ONTOLOGY / "eucn-core-latest.ttl"
    flat_ttl_out = DATA_ONTOLOGY / f"eucn-ch{chapter:02d}-{slug}-{date_str}-flat.ttl"

    t0 = time.perf_counter()

    # ── Step 1: Fetch TARIC XML ──────────────────────────────────────────────
    if not skip_fetch and (force or not taric_json.exists()):
        with _step("fetch-taric"):
            from src.fetcher.taric_xml import fetch_and_parse, write_chapter_json
            chapter_data = fetch_and_parse(chapter=chapter, xml_path=xml_path, xlsx_path=xlsx_path)
            write_chapter_json(chapter_data, DATA_INTERMEDIATE)
    elif skip_fetch and not taric_json.exists():
        raise FileNotFoundError(
            f"--skip-fetch requested but {taric_json} does not exist."
        )
    else:
        print(f"[fetch-taric] skipped (using existing {taric_json.name})")

    # ── Step 2: Scrape wizard ────────────────────────────────────────────────
    if not skip_scrape and (force or not wizard_jsonl.exists()):
        with _step("scrape-wizard"):
            from src.scraper.wizard import scrape_chapter
            scrape_chapter(chapter, DATA_INTERMEDIATE)
    elif skip_scrape and not wizard_jsonl.exists():
        raise FileNotFoundError(
            f"--skip-scrape requested but {wizard_jsonl} does not exist."
        )
    else:
        print(f"[scrape-wizard] skipped (using existing {wizard_jsonl.name})")

    # ── Load wizard tree (needed for run-axiom-agent and build-ontology) ─────
    wizard_tree = None
    ds = None
    if wizard_jsonl.exists():
        from src.schema.wizard import ClassificationNode, WizardTree
        from src.scraper.checkpoint import load_nodes_jsonl
        raw_nodes = load_nodes_jsonl(wizard_jsonl)
        nodes = {n["node_id"]: ClassificationNode.model_validate(n) for n in raw_nodes}
        root_id = next((n["node_id"] for n in raw_nodes if not n["path_from_root"]), "")
        wizard_tree = WizardTree(chapter=chapter, nodes=nodes, root_node_id=root_id)

    # ── Step 2.6a: Run axiom agent (LLM-based) ──────────────────────────────
    if run_axiom_agent:
        with _step("run-axiom-agent"):
            import os
            if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY or ANTHROPIC_FOUNDRY_API_KEY environment variable is required for --run-axiom-agent"
                )
            from src.agent.chapter_runner import ChapterRunner
            from src.agent.coverage_reporter import build_report, write_report
            from src.agent.node_registry import NodeRegistry

            runner = ChapterRunner(chapter=chapter, model=agent_model, data_root=ROOT / "data")
            run_result = runner.run(wizard_tree, force=force)
            print(
                f"  [axiom-agent] ch{chapter:02d}: total={run_result.total}, "
                f"approved={run_result.approved}, proposed={run_result.proposed}, "
                f"failed={run_result.failed}, skipped={run_result.skipped}"
            )

            # Harmonization pass
            node_registry_dir = ROOT / "data" / "axiom_candidates" / f"ch{chapter:02d}"
            node_reg = NodeRegistry(node_registry_dir)
            new_iris = [
                {
                    "iri": f"https://w3id.org/eucn/{cls.iri_local_name}",
                    "label": cls.label_en,
                    "definition": cls.definition_en,
                    "class_or_property": "class",
                }
                for aset in node_reg.iter_all() if aset.status == "proposed"
                for cls in aset.new_classes
            ]
            flat_ttl_path = DATA_ONTOLOGY / f"eucn-ch{chapter:02d}-{slug}-latest-flat.ttl"
            if flat_ttl_path.exists():
                from src.agent.harmonizer import harmonize
                harmonize(
                    chapter,
                    new_iris,
                    flat_ttl_path,
                    model=agent_model,
                    out_path=node_registry_dir / "harmonization.jsonl",
                )

            # Coverage report
            reports_dir = ROOT / "data" / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            report = build_report(chapter, node_reg, run_result)
            write_report(report, reports_dir / f"ch{chapter:02d}_coverage.json")

    # ── Step 2.6b: Fetch legal text and extract axiom candidates ────────────
    legal_text_dir = ROOT / "data" / "legal_text" / f"ch{chapter:02d}"
    candidates_path = ROOT / "data" / "axiom_candidates" / f"ch{chapter:02d}.jsonl"

    if not skip_legal_text and (force or not candidates_path.exists()):
        with _step("fetch-legal-text"):
            from src.fetcher.class_api import fetch_chapter_notes
            from src.agent.rule_extractor import extract_candidates
            from src.agent.candidate_registry import CandidateRegistry
            from src.ontology.chapter_registry import get_chapter as get_ch

            chapter_module = get_ch(chapter)
            legal_text_dir.mkdir(parents=True, exist_ok=True)
            sections = fetch_chapter_notes(chapter, legal_text_dir, force=force)

            registry = CandidateRegistry(candidates_path)
            if candidates_path.exists():
                registry.load()

            for section in sections:
                candidates = extract_candidates(section, section.cn_code, chapter)
                for c in candidates:
                    registry.upsert(c)

            registry.save()
            stale = registry.stale_summary()
            if stale:
                print(
                    f"WARNING: {len(stale)} axiom candidate(s) for chapter {chapter} are stale "
                    f"(CLASS note updated).",
                    file=sys.stderr,
                )
                for s in stale:
                    print(
                        f"  - {s['candidate_id'][:8]}... ({s['owl_class']}, "
                        f"{s['restriction_type']}, {s['property_iri']}) "
                        f"— note {s['source_note_id'][:8]} updated {s['source_ingestion_date']}",
                        file=sys.stderr,
                    )
                print(
                    f"Re-run: python -m src.pipeline --chapter {chapter} --steps fetch-legal-text",
                    file=sys.stderr,
                )
    else:
        if skip_legal_text:
            print(f"[fetch-legal-text] skipped (--skip-legal-text)")
        else:
            print(f"[fetch-legal-text] skipped (using existing {candidates_path.name})")

    # ── Step 2.5: Build and serialize core TBox ──────────────────────────────
    if force or not core_ttl_out.exists():
        with _step("build-core"):
            from src.ontology.core import build_core_tbox
            core_g = Graph()
            build_core_tbox(core_g, extract_date=extract_date)
            core_g.serialize(destination=str(core_ttl_out), format="longturtle")
            shutil.copy(str(core_ttl_out), str(core_ttl_latest))
            print(f"  Written: {core_ttl_out} ({len(core_g)} triples)")
    else:
        print(f"[build-core] skipped (using existing {core_ttl_out.name})")

    # ── Step 3: Build ontology ───────────────────────────────────────────────
    if force or not ttl_out.exists():
        with _step("build-ontology"):
            from src.ontology.abox import build_abox
            from src.ontology.provenance import build_provenance
            from src.ontology.tbox import build_tbox
            from src.schema.taric import ChapterData

            # Load intermediate data
            chapter_data = ChapterData.model_validate_json(taric_json.read_text())

            # Re-use wizard_tree loaded earlier; fall back to loading from disk if needed
            if wizard_tree is None:
                from src.schema.wizard import ClassificationNode, WizardTree
                from src.scraper.checkpoint import load_nodes_jsonl
                raw_nodes = load_nodes_jsonl(wizard_jsonl)
                nodes = {n["node_id"]: ClassificationNode.model_validate(n) for n in raw_nodes}
                root_id = next(
                    (n["node_id"] for n in raw_nodes if not n["path_from_root"]), ""
                )
                wizard_tree = WizardTree(chapter=chapter, nodes=nodes, root_node_id=root_id)

            # Build TBox + ABox in default graph
            g = Graph()
            build_tbox(g, extract_date=extract_date)
            g, wizard_coverage = build_abox(chapter_data, wizard_tree, g)

            # Provenance in named graph
            ds = Dataset()
            for triple in g:
                ds.default_graph.add(triple)
            import uuid
            run_id = str(uuid.uuid4())
            build_provenance(ds, run_id, chapter, sources=[
                "https://circabc.europa.eu/ui/group/0e5f18c2-4b2f-42e9-aed4-dfe50ae1263b",
                "https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do",
            ])

            # Write wizard axiom coverage report
            coverage_json = DATA_INTERMEDIATE / f"wizard_axiom_coverage_ch{chapter:02d}.json"
            coverage_json.write_text(wizard_coverage.model_dump_json(indent=2))
            total_q = len(wizard_coverage.questions)
            print(
                f"  [wizard-axioms] ch{chapter:02d}: "
                f"{wizard_coverage.total_terminal_nodes} terminal nodes, "
                f"{wizard_coverage.covered_boolean} boolean, "
                f"{wizard_coverage.covered_quantitative} quantitative, "
                f"{wizard_coverage.fallback_count} fallback "
                f"(coverage {wizard_coverage.coverage_pct:.1f}%)"
            )

            # Add chapter ontology header with owl:imports to core
            from src.ontology.core import CORE_RAW_URL
            ch_iri = URIRef(f"https://w3id.org/eucn/ch{chapter:02d}-{slug}")
            g.add((ch_iri, RDF.type, OWL.Ontology))
            g.add((ch_iri, OWL.imports, URIRef(CORE_RAW_URL)))

            # Serialize chapter TTL (with owl:imports)
            g.serialize(destination=str(ttl_out), format="longturtle")
            ds.serialize(destination=str(trig_out), format="trig")
            print(f"  Written: {ttl_out} ({len(g)} triples)")

            # Stable alias for chapter TTL
            shutil.copy(str(ttl_out), str(ttl_latest))

            # Flat TTL for Konclude (strip all owl:imports triples)
            flat_g = Graph()
            for s, p, o in g:
                if p != OWL.imports:
                    flat_g.add((s, p, o))
            for prefix, ns in g.namespaces():
                flat_g.bind(prefix, ns)
            flat_g.serialize(destination=str(flat_ttl_out), format="longturtle")
    else:
        print(f"[build-ontology] skipped (using existing {ttl_out.name})")

    # ── Step 4: Konclude consistency check ───────────────────────────────────
    if not no_reasoner:
        with _step("konclude-check"):
            from src.reasoning.konclude import KoncludeConsistencyError, check_consistency
            try:
                check_consistency(flat_ttl_out)
                print("  Ontology: consistent")
            except KoncludeConsistencyError as exc:
                print(f"  INCONSISTENT: {exc}", file=sys.stderr)
                sys.exit(1)
    else:
        print("[konclude-check] skipped (--no-reasoner)")

    # ── Step 4.5: Konclude classify → inferred named graph ───────────────────
    if not no_classify and not no_reasoner:
        with _step("konclude-classify"):
            import subprocess
            from src.reasoning.konclude import classify
            try:
                inferred_ttl = classify(flat_ttl_out)
                if inferred_ttl.strip():
                    inferred_g = Graph()
                    inferred_g.parse(data=inferred_ttl, format="turtle")
                    inferred_graph_iri = URIRef(
                        f"https://w3id.org/eucn/inferred/{date_str}"
                    )
                    inferred_named = ds.graph(inferred_graph_iri)
                    for triple in inferred_g:
                        inferred_named.add(triple)
                    ds.serialize(destination=str(trig_out), format="trig")
                    print(f"  Inferred triples: {len(inferred_g)} → {trig_out.name}")
                else:
                    print("  classify: empty output (stub TBox — expected)")
            except subprocess.TimeoutExpired:
                print("  WARNING: Konclude classify timed out — continuing without inferred graph",
                      file=sys.stderr)
            except Exception as exc:
                print(f"  WARNING: Konclude classify failed: {exc} — continuing",
                      file=sys.stderr)
    else:
        print("[konclude-classify] skipped (--no-classify or --no-reasoner)")

    total = time.perf_counter() - t0
    print(f"\nPipeline complete in {total:.1f}s")


def main() -> None:
    p = argparse.ArgumentParser(description="EU customs ontology pipeline")
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--skip-fetch", action="store_true")
    p.add_argument("--skip-scrape", action="store_true")
    p.add_argument("--skip-legal-text", action="store_true")
    p.add_argument("--xml-path", type=Path, default=None)
    p.add_argument("--xlsx-path", type=Path, default=None, help="CIRCABC Duties Import xlsx")
    p.add_argument("--no-reasoner", action="store_true")
    p.add_argument("--no-classify", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--extract-date", type=Date.fromisoformat, default=None,
                   metavar="YYYY-MM-DD", help="TARIC data extract date (default: today)")
    p.add_argument("--run-axiom-agent", action="store_true",
                   help="Run LLM-based axiom agent (requires ANTHROPIC_API_KEY)")
    p.add_argument("--agent-model", default="claude-sonnet-4-6",
                   metavar="MODEL", help="Model for --run-axiom-agent (default: claude-sonnet-4-6)")
    args = p.parse_args()

    run(
        chapter=args.chapter,
        skip_fetch=args.skip_fetch,
        skip_scrape=args.skip_scrape,
        skip_legal_text=args.skip_legal_text,
        xml_path=args.xml_path,
        xlsx_path=args.xlsx_path,
        no_reasoner=args.no_reasoner,
        no_classify=args.no_classify,
        force=args.force,
        extract_date=args.extract_date,
        run_axiom_agent=args.run_axiom_agent,
        agent_model=args.agent_model,
    )


if __name__ == "__main__":
    main()
