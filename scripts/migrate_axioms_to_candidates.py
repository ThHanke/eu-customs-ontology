#!/usr/bin/env python3
"""One-shot migration: convert hand-authored equivalence axioms to AxiomCandidate JSONL."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.agent.candidate_registry import CandidateRegistry
from src.schema.axiom_candidate import AxiomCandidate

MIGRATION_DATE = "2026-06-08"
MIGRATION_NOTE_ID = "manual-migration"


def _cand(chapter, owl_class, restriction_type, property_iri, value, facet, source_text):
    source_text_hash = hashlib.sha256(source_text.encode()).hexdigest()
    return AxiomCandidate(
        chapter=chapter,
        owl_class=owl_class,
        restriction_type=restriction_type,
        property_iri=property_iri,
        value=value,
        facet=facet,
        source_note_id=MIGRATION_NOTE_ID,
        source_text=source_text,
        source_text_hash=source_text_hash,
        source_ingestion_date=MIGRATION_DATE,
        status="approved",
        confidence=1.0,
        extractor="manual",
        extracted_at=MIGRATION_DATE,
    )


CH22_SOURCE = "equivalence_axioms_beverages.py"
CH23_SOURCE = "equivalence_axioms_ch23_feed.py"


def migrate_ch22() -> list[AxiomCandidate]:
    t = lambda text: f"Hand-authored: {text}. Migrated from {CH22_SOURCE}."
    candidates = [
        _cand(22, "Water", "decimalRange", "eucn:alcoholByVolumePercent", "0.0", "maxInclusive", t("CN 2201: ABV ≤ 0")),
        _cand(22, "NonAlcoholicBeverage", "someValuesFrom", "eucn:producedBy", "SweetenedWaterProcess", None, t("CN 2202: sweetened/flavoured water process")),
        _cand(22, "Beer", "someValuesFrom", "eucn:producedBy", "MaltFermentation", None, t("CN 2203: malt fermentation")),
        _cand(22, "Beer", "decimalRange", "eucn:alcoholByVolumePercent", "0.5", "minExclusive", t("CN 2203: ABV > 0.5%")),
        _cand(22, "Wine", "someValuesFrom", "eucn:producedBy", "GrapeFermentation", None, t("CN 2204: grape fermentation")),
        _cand(22, "SparklingWine", "someValuesFrom", "eucn:producedBy", "GrapeFermentation", None, t("CN 2204 10: grape fermentation")),
        _cand(22, "SparklingWine", "hasValue", "eucn:isCarbonated", "true", None, t("CN 2204 10: carbonated")),
        _cand(22, "StillWine", "someValuesFrom", "eucn:producedBy", "GrapeFermentation", None, t("CN 2204 21/29: grape fermentation")),
        _cand(22, "StillWine", "hasValue", "eucn:isCarbonated", "false", None, t("CN 2204 21/29: not carbonated")),
        _cand(22, "FlavouredWine", "someValuesFrom", "eucn:producedBy", "GrapeFlavouringProcess", None, t("CN 2205: grape flavouring process")),
        _cand(22, "FermentedBeverage", "someValuesFrom", "eucn:producedBy", "FruitFermentation", None, t("CN 2206: fruit fermentation")),
        _cand(22, "Vinegar", "someValuesFrom", "eucn:producedBy", "AceticFermentation", None, t("CN 2209: acetic fermentation")),
        _cand(22, "EthylAlcohol", "decimalRange", "eucn:alcoholByVolumePercent", "80.0", "minInclusive", t("CN 2207: ABV ≥ 80%")),
        _cand(22, "Spirit", "decimalRange", "eucn:alcoholByVolumePercent", "0.5", "minExclusive", t("CN 2208: ABV > 0.5%")),
        _cand(22, "Spirit", "decimalRange", "eucn:alcoholByVolumePercent", "80.0", "maxExclusive", t("CN 2208: ABV < 80%")),
    ]
    return candidates


def migrate_ch23() -> list[AxiomCandidate]:
    t = lambda text: f"Hand-authored: {text}. Migrated from {CH23_SOURCE}."
    candidates = [
        _cand(23, "AnimalByProductMeal", "someValuesFrom", "eucn:producedBy", "AnimalMealRendering", None, t("CN 2301: animal meal rendering")),
        _cand(23, "CerealMillingResidue", "someValuesFrom", "eucn:producedBy", "GrainMillingProcess", None, t("CN 2302: grain milling")),
        _cand(23, "StarchManufactureResidue", "someValuesFrom", "eucn:producedBy", "StarchExtractionProcess", None, t("CN 2303: starch extraction")),
        _cand(23, "SoybeanOilcake", "someValuesFrom", "eucn:producedBy", "SoybeanOilExtraction", None, t("CN 2304: soybean oil extraction")),
        _cand(23, "GroundnutOilcake", "someValuesFrom", "eucn:producedBy", "GroundnutOilExtraction", None, t("CN 2305: groundnut oil extraction")),
        _cand(23, "VegetableOilcake", "someValuesFrom", "eucn:producedBy", "OtherOilseedExtraction", None, t("CN 2306: other oilseed extraction")),
        _cand(23, "WineLees", "someValuesFrom", "eucn:producedBy", "WineLeesByproduction", None, t("CN 2307: wine lees byproduction")),
        _cand(23, "PlantResidue", "someValuesFrom", "eucn:producedBy", "PlantResidueCollection", None, t("CN 2308: plant residue collection")),
        _cand(23, "AnimalFeedPreparation", "someValuesFrom", "eucn:producedBy", "AnimalFeedMixing", None, t("CN 2309: animal feed mixing")),
    ]
    return candidates


def main():
    data_dir = ROOT / "data" / "axiom_candidates"
    data_dir.mkdir(parents=True, exist_ok=True)

    for chapter, candidates_fn in [(22, migrate_ch22), (23, migrate_ch23)]:
        path = data_dir / f"ch{chapter:02d}.jsonl"
        if path.exists():
            print(f"Skipping ch{chapter:02d}: {path} already exists. Use --force to overwrite.")
            continue
        registry = CandidateRegistry(path)
        for c in candidates_fn():
            registry.upsert(c)
        registry.save()
        active = registry.get_active()
        print(f"Migrated ch{chapter:02d}: {len(active)} candidates → {path}")

    print("Migration complete.")

if __name__ == "__main__":
    main()
