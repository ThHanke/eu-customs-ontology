"""ABox realization demo: native Konclude classifies beverage individuals.

Loads the TBox plus tests/fixtures/beverages_demo.ttl, runs native Konclude
realization, and asserts that each individual is inferred under the expected
product class hierarchy.

Skip conditions:
  - Native Konclude binary absent (KONCLUDE_NATIVE_PATH or default path).
  - pytest mark: konclude_native.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from rdflib import Graph, Namespace

from src.ontology.equivalence_axioms import add_ch22_equivalence_axioms
from src.ontology.tbox import build_tbox
from src.reasoning.konclude import KONCLUDE_NATIVE_PATH, parse_realization, realize

EUCN = Namespace("https://w3id.org/eucn/")
FIXTURES = Path(__file__).parent.parent / "fixtures"
DEMO_TTL = FIXTURES / "beverages_demo.ttl"

NATIVE_AVAILABLE = Path(KONCLUDE_NATIVE_PATH).exists()
skip_no_native = pytest.mark.skipif(
    not NATIVE_AVAILABLE,
    reason="Native Konclude binary not found — run scripts/acquire-native-konclude.sh",
)

# Expected inferred types per individual (must be subset of actual)
EXPECTED: dict[str, set[str]] = {
    "https://w3id.org/eucn/demo/champagne-brut": {
        "https://w3id.org/eucn/SparklingWine",
        "https://w3id.org/eucn/Wine",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/bordeaux-rouge": {
        "https://w3id.org/eucn/StillWine",
        "https://w3id.org/eucn/Wine",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/apple-cider": {
        "https://w3id.org/eucn/FermentedBeverage",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/dry-vermouth": {
        "https://w3id.org/eucn/FlavouredWine",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/malt-vinegar": {
        "https://w3id.org/eucn/Vinegar",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/sparkling-lemonade": {
        "https://w3id.org/eucn/NonAlcoholicBeverage",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/czech-lager": {
        "https://w3id.org/eucn/Beer",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/whisky-12y": {
        "https://w3id.org/eucn/Spirit",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/grain-spirit-96": {
        "https://w3id.org/eucn/EthylAlcohol",
        "https://w3id.org/eucn/Beverage",
    },
    "https://w3id.org/eucn/demo/still-water": {
        "https://w3id.org/eucn/Water",
        "https://w3id.org/eucn/Beverage",
    },
}


def _build_combined_ttl(tmp_path: Path) -> Path:
    g = Graph()
    build_tbox(g)
    add_ch22_equivalence_axioms(g)
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

    def test_champagne_inferred_as_sparkling_wine(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/champagne-brut"
        assert "https://w3id.org/eucn/SparklingWine" in types.get(ind, [])

    def test_bordeaux_inferred_as_still_wine(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/bordeaux-rouge"
        assert "https://w3id.org/eucn/StillWine" in types.get(ind, [])

    def test_cider_inferred_as_fermented_beverage(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/apple-cider"
        assert "https://w3id.org/eucn/FermentedBeverage" in types.get(ind, [])

    def test_vermouth_inferred_as_flavoured_wine(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/dry-vermouth"
        assert "https://w3id.org/eucn/FlavouredWine" in types.get(ind, [])

    def test_vinegar_inferred_as_vinegar(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/malt-vinegar"
        assert "https://w3id.org/eucn/Vinegar" in types.get(ind, [])

    def test_lemonade_inferred_as_nonalcoholic_beverage(self, tmp_path):
        types = self._realize(tmp_path)
        ind = "https://w3id.org/eucn/demo/sparkling-lemonade"
        assert "https://w3id.org/eucn/NonAlcoholicBeverage" in types.get(ind, [])

    def test_lager_inferred_as_beer(self, tmp_path):
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/Beer" in types.get(
            "https://w3id.org/eucn/demo/czech-lager", []
        )

    def test_whisky_inferred_as_spirit(self, tmp_path):
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/Spirit" in types.get(
            "https://w3id.org/eucn/demo/whisky-12y", []
        )

    def test_grain_spirit_inferred_as_ethyl_alcohol(self, tmp_path):
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/EthylAlcohol" in types.get(
            "https://w3id.org/eucn/demo/grain-spirit-96", []
        )

    def test_still_water_inferred_as_water(self, tmp_path):
        types = self._realize(tmp_path)
        assert "https://w3id.org/eucn/Water" in types.get(
            "https://w3id.org/eucn/demo/still-water", []
        )

    def test_all_demo_individuals_inferred_as_beverage(self, tmp_path):
        types = self._realize(tmp_path)
        for ind_iri in EXPECTED:
            assert "https://w3id.org/eucn/Beverage" in types.get(ind_iri, []), (
                f"{ind_iri} not inferred as eucn:Beverage"
            )

    def test_no_individual_classified_as_nothing(self, tmp_path):
        """If any individual lands in owl:Nothing the ontology is inconsistent."""
        xml_out = tmp_path / "realization.xml"
        realize(_build_combined_ttl(tmp_path), xml_out)
        import xml.etree.ElementTree as ET
        root = ET.parse(xml_out).getroot()
        OWL_NS = "http://www.w3.org/2002/07/owl#"
        for ca in root.iter(f"{{{OWL_NS}}}ClassAssertion"):
            cls_el = ca.find(f"{{{OWL_NS}}}Class")
            if cls_el is not None:
                iri = cls_el.get("IRI", "")
                assert iri != f"{OWL_NS}Nothing", (
                    f"Individual classified as owl:Nothing — ontology inconsistent"
                )

    def test_expected_types_are_superset_of_inferred(self, tmp_path):
        """Each individual must have AT LEAST its expected types inferred."""
        types = self._realize(tmp_path)
        for ind_iri, expected_set in EXPECTED.items():
            actual = set(types.get(ind_iri, []))
            missing = expected_set - actual
            assert not missing, f"{ind_iri}: missing inferred types {missing}"
