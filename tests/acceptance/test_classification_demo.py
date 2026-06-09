"""ABox realization demo: native Konclude classifies beverage individuals.

Loads the flat chapter TTL plus tests/fixtures/beverages_demo.ttl, runs native
Konclude realization, and asserts each individual is inferred under the expected
product class hierarchy.

Skip conditions:
  - Native Konclude binary absent (KONCLUDE_NATIVE_PATH or default path).
  - pytest mark: konclude_native.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from rdflib import Graph, Namespace

from src.ontology.tbox import build_tbox
from src.reasoning.konclude import KONCLUDE_NATIVE_PATH, parse_realization, realize

EUCN = Namespace("https://w3id.org/eucn/")
FIXTURES = Path(__file__).parent.parent / "fixtures"
DEMO_TTL = FIXTURES / "beverages_demo.ttl"
DATA_ONTOLOGY = Path(__file__).parent.parent.parent / "data" / "ontology"

NATIVE_AVAILABLE = Path(KONCLUDE_NATIVE_PATH).exists()
skip_no_native = pytest.mark.skipif(
    not NATIVE_AVAILABLE,
    reason="Native Konclude binary not found — run scripts/acquire-native-konclude.sh",
)

# Expected inferred types per individual (must be subset of actual inferred types).
# Hierarchy after hierarchy fix: agent class → heading class (2201-2209) → eucn:Beverage
EXPECTED: dict[str, set[str]] = {
    # Champagne: 3-level chain → Beverage
    "https://w3id.org/eucn/demo/champagne-brut": {
        "https://w3id.org/eucn/Champagne22041011",
        "https://w3id.org/eucn/WineOfFreshGrapes2204",
        "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/bordeaux-rouge": {
        "https://w3id.org/eucn/WineOfFreshGrapes2204",
        "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/port-wine": {
        "https://w3id.org/eucn/FortifiedWine2204",
        "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204",
        "https://w3id.org/eucn/Beverage",
    },
    # Vermouth is under chapter 2205, directly subClassOf Beverage
    "https://w3id.org/eucn/demo/dry-vermouth": {
        "https://w3id.org/eucn/VermouthWineFreshGrapesFlavouredPlants2205",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/apple-cider": {
        "https://w3id.org/eucn/CiderPerryMeadSakFermentedBeverages2206",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/sparkling-lemonade": {
        "https://w3id.org/eucn/NonAlcoholicFlavouredBeverage2202",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/scotch-whisky": {
        "https://w3id.org/eucn/ScotchWhisky2208",
        "https://w3id.org/eucn/SpiritsBeverages2208",
        "https://w3id.org/eucn/Beverage",
    },
    # SingleMaltWhisky22083030: newly approved node; also infers 4 restriction superclasses
    "https://w3id.org/eucn/demo/single-malt-glenlivet": {
        "https://w3id.org/eucn/SingleMaltWhisky22083030",
        "https://w3id.org/eucn/SpiritsBeverages2208",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/gin-small": {
        "https://w3id.org/eucn/GinSmallContainer22085011",
        "https://w3id.org/eucn/Gin2208",
        "https://w3id.org/eucn/SpiritsBeverages2208",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/gin-large": {
        "https://w3id.org/eucn/GinLargeContainer22085019",
        "https://w3id.org/eucn/Gin2208",
        "https://w3id.org/eucn/SpiritsBeverages2208",
        "https://w3id.org/eucn/Beverage",
    },
    # Vinegar: subClassOf Vinegar2209 → BFO material entity (vinegar is not a beverage)
    "https://w3id.org/eucn/demo/wine-vinegar-small": {
        "https://w3id.org/eucn/WineVinegarSmallContainer22090011",
        "https://w3id.org/eucn/WineVinegar2209",
        "https://w3id.org/eucn/Vinegar2209",
    },
    # Packaging equivalence inference
    "https://w3id.org/eucn/demo/bottle-075": {
        "https://w3id.org/eucn/SmallContainer",
    },
    "https://w3id.org/eucn/demo/keg-20": {
        "https://w3id.org/eucn/LargeContainer",
    },
    # Bordeaux wine: subClassOf chain → Beverage; its bottle inferred as SmallContainer
    "https://w3id.org/eucn/demo/bordeaux-small-bottle-wine": {
        "https://w3id.org/eucn/WinesProducedBordeauxContainersActualAlcoholic22042142",
        "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/bordeaux-bottle": {
        "https://w3id.org/eucn/SmallContainer",
    },
}


def _find_flat_ttl() -> Path:
    """Return the most recent flat chapter-22 TTL from data/ontology/."""
    candidates = sorted(DATA_ONTOLOGY.glob("eucn-ch22-*-flat.ttl"))
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(
        f"No eucn-ch22-*-flat.ttl found in {DATA_ONTOLOGY}. "
        "Run: python -m src.pipeline --chapter 22 --force"
    )


def _build_combined_ttl(tmp_path: Path) -> Path:
    """Merge built chapter ontology + demo ABox into a single flat TTL."""
    g = Graph()
    g.parse(_find_flat_ttl(), format="turtle")
    g.parse(DEMO_TTL, format="turtle")
    out = tmp_path / "combined.ttl"
    out.write_text(g.serialize(format="longturtle"))
    return out


@skip_no_native
class TestBeverageRealization:
    def _realize(self, tmp_path: Path) -> dict[str, list[str]]:
        ttl = _build_combined_ttl(tmp_path)
        xml_out = tmp_path / "realization.xml"
        realize(ttl, xml_out)
        return parse_realization(xml_out)

    def test_consistent_with_demo_individuals(self, tmp_path):
        """Combined TBox + demo ABox must be consistent."""
        from src.reasoning.konclude import KoncludeConsistencyError, check_consistency
        from src.reasoning.konclude import KONCLUDE_CLI_PATH
        cli = Path(KONCLUDE_CLI_PATH)
        if not cli.exists():
            pytest.skip("WASM Konclude CLI not found")
        ttl = _build_combined_ttl(tmp_path)
        assert check_consistency(ttl) is True

    def test_champagne_inferred_full_chain(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/champagne-brut"
        assert "https://w3id.org/eucn/Champagne22041011" in types.get(ind, [])
        assert "https://w3id.org/eucn/WineOfFreshGrapes2204" in types.get(ind, [])
        assert "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_port_inferred_as_fortified_wine(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/port-wine"
        assert "https://w3id.org/eucn/FortifiedWine2204" in types.get(ind, [])
        assert "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_vermouth_inferred_as_beverage(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/dry-vermouth"
        assert "https://w3id.org/eucn/VermouthWineFreshGrapesFlavouredPlants2205" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_cider_inferred_as_beverage(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/apple-cider"
        assert "https://w3id.org/eucn/CiderPerryMeadSakFermentedBeverages2206" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_lemonade_inferred_as_beverage(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/sparkling-lemonade"
        assert "https://w3id.org/eucn/NonAlcoholicFlavouredBeverage2202" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_scotch_whisky_inferred_chain(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/scotch-whisky"
        assert "https://w3id.org/eucn/ScotchWhisky2208" in types.get(ind, [])
        assert "https://w3id.org/eucn/SpiritsBeverages2208" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_single_malt_inferred_chain(self, tmp_path):
        """SingleMaltWhisky22083030 (newly approved node) inferred through SpiritsBeverages2208."""
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/single-malt-glenlivet"
        assert "https://w3id.org/eucn/SingleMaltWhisky22083030" in types.get(ind, [])
        assert "https://w3id.org/eucn/SpiritsBeverages2208" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_gin_small_inferred_chain(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/gin-small"
        assert "https://w3id.org/eucn/GinSmallContainer22085011" in types.get(ind, [])
        assert "https://w3id.org/eucn/Gin2208" in types.get(ind, [])
        assert "https://w3id.org/eucn/SpiritsBeverages2208" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_gin_large_inferred_chain(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/gin-large"
        assert "https://w3id.org/eucn/GinLargeContainer22085019" in types.get(ind, [])
        assert "https://w3id.org/eucn/Gin2208" in types.get(ind, [])

    def test_wine_vinegar_inferred_chain(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/wine-vinegar-small"
        assert "https://w3id.org/eucn/WineVinegarSmallContainer22090011" in types.get(ind, [])
        assert "https://w3id.org/eucn/WineVinegar2209" in types.get(ind, [])
        assert "https://w3id.org/eucn/Vinegar2209" in types.get(ind, [])

    def test_small_bottle_inferred_as_small_container(self, tmp_path):
        """Packaging with Volume < 2 L inferred as SmallContainer via equivalence axiom."""
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/SmallContainer" in types.get(
            "https://w3id.org/eucn/demo/bottle-075", []
        )

    def test_large_keg_inferred_as_large_container(self, tmp_path):
        """Packaging with Volume ≥ 2 L inferred as LargeContainer via equivalence axiom."""
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/LargeContainer" in types.get(
            "https://w3id.org/eucn/demo/keg-20", []
        )

    def test_bordeaux_wine_inferred_as_beverage(self, tmp_path):
        """Bordeaux wine individual classified through heading class to Beverage."""
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/bordeaux-small-bottle-wine"
        assert "https://w3id.org/eucn/WinesProducedBordeauxContainersActualAlcoholic22042142" in types.get(ind, [])
        assert "https://w3id.org/eucn/WineFreshGrapesInclFortifiedWines2204" in types.get(ind, [])
        assert "https://w3id.org/eucn/Beverage" in types.get(ind, [])

    def test_bordeaux_bottle_inferred_as_small_container(self, tmp_path):
        """The 0.75 L bottle associated with the Bordeaux wine is inferred as SmallContainer."""
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/SmallContainer" in types.get(
            "https://w3id.org/eucn/demo/bordeaux-bottle", []
        )

    def test_no_individual_classified_as_nothing(self, tmp_path):
        """Any individual in owl:Nothing means inconsistency."""
        import xml.etree.ElementTree as ET
        xml_out = tmp_path / "realization.xml"
        realize(_build_combined_ttl(tmp_path), xml_out)
        root = ET.parse(xml_out).getroot()
        OWL_NS = "http://www.w3.org/2002/07/owl#"
        for ca in root.iter(f"{{{OWL_NS}}}ClassAssertion"):
            cls_el = ca.find(f"{{{OWL_NS}}}Class")
            if cls_el is not None:
                iri = cls_el.get("IRI", "")
                assert iri != f"{OWL_NS}Nothing", (
                    "Individual classified as owl:Nothing — ontology inconsistent"
                )

    def test_expected_types_subset_of_inferred(self, tmp_path):
        """Each individual must have at least its expected types inferred."""
        types = self._realize(tmp_path)
        for ind_iri, expected_set in EXPECTED.items():
            actual = set(types.get(ind_iri, []))
            missing = expected_set - actual
            assert not missing, f"{ind_iri}: missing inferred types {missing}"
