"""ABox realization demo: WASM Konclude classifies individuals via property-based reasoning.

Loads the flat chapter TTL plus tests/fixtures/beverages_demo.ttl, runs WASM
Konclude realization, and asserts that individuals typed as PARENT classes with
property assertions are correctly inferred as leaf CN classes.

No individual in the fixture is explicitly typed as a leaf class — classification
comes entirely from OWL equivalentClass reasoning over properties.

Skip condition: WASM Konclude CLI absent (KONCLUDE_CLI_PATH or default path).
"""
from __future__ import annotations

import pytest
from pathlib import Path
from rdflib import Graph, Namespace

from src.reasoning.konclude import KONCLUDE_CLI_PATH, parse_realization

EUCN = Namespace("https://w3id.org/eucn/")
DEMO = Namespace("https://w3id.org/eucn/demo/")
FIXTURES = Path(__file__).parent.parent / "fixtures"
DEMO_TTL = FIXTURES / "beverages_demo.ttl"
DATA_ONTOLOGY = Path(__file__).parent.parent.parent / "data" / "ontology"

WASM_AVAILABLE = Path(KONCLUDE_CLI_PATH).exists()
skip_no_wasm = pytest.mark.skipif(
    not WASM_AVAILABLE,
    reason="WASM Konclude CLI not found — set KONCLUDE_CLI_PATH",
)


def _find_flat_ttl() -> Path:
    candidates = sorted(DATA_ONTOLOGY.glob("eucn-ch22-*-flat.ttl"))
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(
        f"No eucn-ch22-*-flat.ttl in {DATA_ONTOLOGY}. "
        "Run: python -m src.pipeline --chapter 22"
    )


def _build_combined_ttl(tmp_path: Path) -> Path:
    g = Graph()
    g.parse(_find_flat_ttl(), format="turtle")
    g.parse(DEMO_TTL, format="turtle")
    out = tmp_path / "combined.ttl"
    out.write_text(g.serialize(format="longturtle"))
    return out


def _realize(tmp_path: Path) -> dict[str, list[str]]:
    """Run Konclude realization and return {individual_iri: [class_iri]}."""
    from src.reasoning.konclude import realize
    ttl = _build_combined_ttl(tmp_path)
    xml_out = tmp_path / "realization.xml"
    realize(ttl, xml_out)
    return parse_realization(xml_out)


@skip_no_wasm
class TestPropertyBasedClassification:
    """All individuals are typed as PARENT classes; leaf classification is inferred."""

    # ── Container size inference ──────────────────────────────────────────

    def test_small_bottle_inferred_as_small_container(self, tmp_path):
        """Packaging + Volume(0.75L) → SmallContainer via equivalentClass."""
        types = _realize(tmp_path)
        assert str(EUCN.SmallContainer) in types.get(str(DEMO.bottle_075), []), (
            "demo:bottle-075 (Packaging, 0.75L) should be inferred as SmallContainer"
        )

    def test_large_keg_inferred_as_large_container(self, tmp_path):
        """Packaging + Volume(20L) → LargeContainer via equivalentClass."""
        types = _realize(tmp_path)
        assert str(EUCN.LargeContainer) in types.get(str(DEMO.keg_20), []), (
            "demo:keg-20 (Packaging, 20L) should be inferred as LargeContainer"
        )

    # ── Wine vinegar — two-level classification chain ─────────────────────
    # Chain: Packaging+Volume → SmallContainer/LargeContainer
    #        Vinegar2209 + WineVinegarQuality + SmallContainer → WineVinegarSmallContainer22090011

    def test_wine_vinegar_bottle_inferred_as_small_container(self, tmp_path):
        """The 0.75L wine-vinegar packaging individual should be inferred as SmallContainer."""
        types = _realize(tmp_path)
        assert str(EUCN.SmallContainer) in types.get(str(DEMO.wine_vinegar_bottle), [])

    def test_wine_vinegar_small_inferred_from_properties(self, tmp_path):
        """Vinegar2209 + WineVinegarQuality + (hasPart SmallContainer)
        → WineVinegarSmallContainer22090011 (CN 2209 00 11)."""
        types = _realize(tmp_path)
        ind = str(DEMO.wine_vinegar_small)
        inferred = types.get(ind, [])
        assert str(EUCN.WineVinegarSmallContainer22090011) in inferred, (
            f"Expected WineVinegarSmallContainer22090011 in {inferred}"
        )
        # Transitively inferred superclasses
        assert str(EUCN.Vinegar2209) in inferred

    def test_wine_vinegar_jug_inferred_as_large_container(self, tmp_path):
        """The 5L wine-vinegar packaging individual should be inferred as LargeContainer."""
        types = _realize(tmp_path)
        assert str(EUCN.LargeContainer) in types.get(str(DEMO.wine_vinegar_jug), [])

    def test_wine_vinegar_large_inferred_from_properties(self, tmp_path):
        """Vinegar2209 + WineVinegarQuality + (hasPart LargeContainer)
        → WineVinegarLargeContainer22090019 (CN 2209 00 19)."""
        types = _realize(tmp_path)
        ind = str(DEMO.wine_vinegar_large)
        inferred = types.get(ind, [])
        assert str(EUCN.WineVinegarLargeContainer22090019) in inferred, (
            f"Expected WineVinegarLargeContainer22090019 in {inferred}"
        )
        assert str(EUCN.Vinegar2209) in inferred

    def test_wine_vinegar_small_not_large_container(self, tmp_path):
        """Same product, different container → different leaf class (not both)."""
        types = _realize(tmp_path)
        small_inferred = types.get(str(DEMO.wine_vinegar_small), [])
        large_inferred = types.get(str(DEMO.wine_vinegar_large), [])
        assert str(EUCN.WineVinegarSmallContainer22090011) not in large_inferred
        assert str(EUCN.WineVinegarLargeContainer22090019) not in small_inferred

    # ── Sparkling wine — two-level classification chain ───────────────────

    def test_sparkling_bottle_inferred_as_small_container(self, tmp_path):
        types = _realize(tmp_path)
        assert str(EUCN.SmallContainer) in types.get(str(DEMO.sparkling_bottle), [])

    def test_sparkling_wine_small_inferred_from_properties(self, tmp_path):
        """WineFreshGrapesGrapeMust2204 + SparklingWineQuality + OtherSparklingWineDesignationQuality
        + (hasPart SmallContainer) → OtherSparklingWineSmallContainer22041094 (CN 2204 10 94)."""
        types = _realize(tmp_path)
        ind = str(DEMO.sparkling_wine_small)
        inferred = types.get(ind, [])
        assert str(EUCN.OtherSparklingWineSmallContainer22041094) in inferred, (
            f"Expected OtherSparklingWineSmallContainer22041094 in {inferred}"
        )

    def test_sparkling_tank_inferred_as_large_container(self, tmp_path):
        types = _realize(tmp_path)
        assert str(EUCN.LargeContainer) in types.get(str(DEMO.sparkling_tank), [])

    def test_sparkling_wine_large_inferred_from_properties(self, tmp_path):
        """WineFreshGrapesGrapeMust2204 + sparkling qualities + (hasPart LargeContainer)
        → OtherSparklingWineLargeContainer22041096 (CN 2204 10 96)."""
        types = _realize(tmp_path)
        ind = str(DEMO.sparkling_wine_large)
        inferred = types.get(ind, [])
        assert str(EUCN.OtherSparklingWineLargeContainer22041096) in inferred, (
            f"Expected OtherSparklingWineLargeContainer22041096 in {inferred}"
        )

    def test_no_individual_classified_as_nothing(self, tmp_path):
        """No individual may be inferred as owl:Nothing (would mean inconsistency)."""
        import xml.etree.ElementTree as ET
        from src.reasoning.konclude import realize as _realize_fn
        xml_out = tmp_path / "realization.xml"
        _realize_fn(_build_combined_ttl(tmp_path), xml_out)
        OWL_NS = "http://www.w3.org/2002/07/owl#"
        for ca in ET.parse(xml_out).getroot().iter(f"{{{OWL_NS}}}ClassAssertion"):
            cls_el = ca.find(f"{{{OWL_NS}}}Class")
            if cls_el is not None:
                assert cls_el.get("IRI", "") != f"{OWL_NS}Nothing"

    def test_combined_ttl_is_consistent(self, tmp_path):
        """TBox + demo ABox must be consistent."""
        from src.reasoning.konclude import KoncludeConsistencyError, check_consistency
        ttl = _build_combined_ttl(tmp_path)
        assert check_consistency(ttl) is True
