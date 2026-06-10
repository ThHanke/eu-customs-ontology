from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

KONCLUDE_CLI_PATH = os.environ.get(
    "KONCLUDE_CLI_PATH",
    "/home/hanke/rdf-reasoner-konclude/dist/cli.js",
)
KONCLUDE_NATIVE_PATH = os.environ.get(
    "KONCLUDE_NATIVE_PATH",
    "/home/hanke/rdf-reasoner-konclude/vendor/konclude/Binaries/Konclude",
)
TIMEOUT_SECONDS = 120
_OWL_NS = "http://www.w3.org/2002/07/owl#"


class KoncludeConsistencyError(Exception):
    pass


def check_consistency(ttl_path: Path) -> bool:
    """Run Konclude WASM consistency check on a Turtle file.

    Returns True if consistent. Raises KoncludeConsistencyError if inconsistent.
    Fast (<5s) on lean per-node TBoxes; may approach timeout on large flat files.
    """
    cli = Path(KONCLUDE_CLI_PATH)
    if not cli.exists():
        raise FileNotFoundError(
            f"Konclude CLI not found at {cli}. "
            "Set KONCLUDE_CLI_PATH environment variable or clone rdf-reasoner-konclude."
        )

    result = subprocess.run(
        ["node", str(cli), "--input", str(ttl_path), "--mode", "consistency"],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        raise KoncludeConsistencyError(
            f"Ontology is inconsistent or Konclude reported an error.\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )

    return True


def classify(ttl_path: Path) -> str:
    """Run Konclude TBox classification, return inferred triples as Turtle string."""
    cli = Path(KONCLUDE_CLI_PATH)
    if not cli.exists():
        raise FileNotFoundError(
            f"Konclude CLI not found at {cli}. "
            "Set KONCLUDE_CLI_PATH environment variable."
        )

    result = subprocess.run(
        ["node", str(cli), "--input", str(ttl_path), "--mode", "classify", "--format", "ttl"],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        raise KoncludeConsistencyError(
            f"Konclude classify failed.\nstderr: {result.stderr}"
        )

    return result.stdout


def realize(ttl_path: Path, output_xml_path: Path) -> None:
    """Run Konclude ABox realization on a Turtle file.

    Uses WASM CLI (rdf-reasoner-konclude) when available. The WASM realization
    mode is currently bugged upstream and will be fixed in an upcoming release.
    Falls back to native binary if WASM CLI is absent.

    Writes OWL/XML with ClassAssertion triples to output_xml_path.
    """
    cli = Path(KONCLUDE_CLI_PATH)
    if cli.exists():
        result = subprocess.run(
            [
                "node", str(cli),
                "--input", str(ttl_path),
                "--mode", "realization",
                "--output", str(output_xml_path),
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Konclude WASM realization failed.\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )
        return

    binary = Path(KONCLUDE_NATIVE_PATH)
    if not binary.exists():
        raise FileNotFoundError(
            f"Neither WASM CLI ({cli}) nor native binary ({binary}) found. "
            "Set KONCLUDE_CLI_PATH or KONCLUDE_NATIVE_PATH."
        )
    result = subprocess.run(
        [str(binary), "realization", "-i", str(ttl_path), "-o", str(output_xml_path)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Konclude native realization failed.\nstderr: {result.stderr}\nstdout: {result.stdout}"
        )


def parse_realization(owl_xml_path: Path) -> dict[str, list[str]]:
    """Parse ClassAssertion triples from native Konclude OWL/XML realization output.

    Returns {individual_iri: [class_iri, ...]} excluding owl:Thing and owl:Nothing.
    """
    tree = ET.parse(owl_xml_path)
    root = tree.getroot()
    result: dict[str, list[str]] = {}
    skip = {f"{_OWL_NS}Thing", f"{_OWL_NS}Nothing"}
    for ca in root.iter(f"{{{_OWL_NS}}}ClassAssertion"):
        cls_el = ca.find(f"{{{_OWL_NS}}}Class")
        ind_el = ca.find(f"{{{_OWL_NS}}}NamedIndividual")
        if cls_el is None or ind_el is None:
            continue
        class_iri = cls_el.get("IRI") or cls_el.get("abbreviatedIRI", "")
        ind_iri = ind_el.get("IRI") or ind_el.get("abbreviatedIRI", "")
        if not class_iri or not ind_iri or class_iri in skip:
            continue
        result.setdefault(ind_iri, []).append(class_iri)
    return result
