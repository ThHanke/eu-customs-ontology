from __future__ import annotations

import os
import subprocess
from pathlib import Path

KONCLUDE_CLI_PATH = os.environ.get(
    "KONCLUDE_CLI_PATH",
    "/home/hanke/rdf-reasoner-konclude/dist/cli.js",
)
TIMEOUT_SECONDS = 120


class KoncludeConsistencyError(Exception):
    pass


def check_consistency(ttl_path: Path) -> bool:
    """Run Konclude consistency check on a Turtle file.

    Returns True if ontology is consistent.
    Raises KoncludeConsistencyError if inconsistent (exit code 1).
    Raises FileNotFoundError if Konclude CLI not found.
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
