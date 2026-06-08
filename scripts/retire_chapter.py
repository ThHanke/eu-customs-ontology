#!/usr/bin/env python3
"""Retire a hand-authored chapter module after LLM agent output has been validated.

Usage (once agent output for the chapter has been manually validated and a
Konclude consistency check passes)::

    python scripts/retire_chapter.py 22
    python scripts/retire_chapter.py 23

What this script does
---------------------
1. Replaces the body of every ``add_*(g)`` function in the chapter's
   hand-authored ontology modules with ``pass  # retired YYYY-MM-DD``.
2. Sets ``add_equivalence_axioms=None`` for the chapter in
   ``src/ontology/chapter_registry.py``.
3. Prints a reminder to run the Konclude consistency check.

PREREQUISITES
-------------
- Agent output for the chapter must have been reviewed and approved.
- A Konclude (or owlrl) consistency check must pass *before* this script is
  run, and again *after* to confirm the ontology is still coherent.

If any tests fail after retirement, the hand-authored modules can be restored
from git history.
"""
from __future__ import annotations

import ast
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
TODAY = date.today().isoformat()

# Map chapter number → the modules that belong to it
CHAPTER_MODULES: dict[int, list[str]] = {
    22: [
        "src/ontology/product_classes_beverages.py",
        "src/ontology/process_classes_beverages.py",
        "src/ontology/equivalence_axioms_beverages.py",
    ],
    23: [
        "src/ontology/product_classes_ch23_feed.py",
        "src/ontology/process_classes_ch23_feed.py",
        "src/ontology/equivalence_axioms_ch23_feed.py",
    ],
}

# Regex that matches a top-level def add_*(g): (possibly with type hints)
_FUNC_DEF_RE = re.compile(r"^(def add_\w+\([^)]*\)[^:]*:)\s*$", re.MULTILINE)


def _retire_module(path: Path, retirement_date: str) -> None:
    """Replace every add_* function body with ``pass  # retired DATE``."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        print(f"  ERROR: could not parse {path}: {exc}", file=sys.stderr)
        return

    # Collect (lineno, end_lineno) for each top-level add_* function
    func_spans: list[tuple[int, int]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("add_"):
            func_spans.append((node.lineno, node.end_lineno))

    if not func_spans:
        print(f"  WARNING: no add_* functions found in {path}")
        return

    lines = source.splitlines(keepends=True)

    # Work backwards so that line numbers stay valid as we replace content
    for start_lineno, end_lineno in reversed(func_spans):
        # The def line is start_lineno (1-based); body starts at start_lineno+1
        body_start = start_lineno  # 0-based index of the line after def
        body_end = end_lineno      # 0-based inclusive last line of body

        # Determine indentation of body from first non-empty body line
        indent = "    "
        for i in range(body_start, body_end):
            stripped = lines[i].lstrip()
            if stripped and not stripped.startswith("#"):
                indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
                break

        # Replace body lines (index body_start .. body_end-1, 0-based) with stub
        replacement = f"{indent}pass  # retired {retirement_date}\n"
        lines[body_start:body_end] = [replacement]

    path.write_text("".join(lines), encoding="utf-8")
    print(f"  Retired {path.name} ({len(func_spans)} function(s) → pass stub)")


def _retire_registry_entry(chapter: int, retirement_date: str) -> None:
    """Set add_equivalence_axioms=None for the chapter in chapter_registry.py."""
    registry_path = ROOT / "src" / "ontology" / "chapter_registry.py"
    source = registry_path.read_text(encoding="utf-8")

    # Pattern: add_equivalence_axioms=add_equivalence_axioms_beverages,
    # We want to replace the callable with None
    # Match the specific assignment inside the ChapterModule(...) for this chapter.
    # We look for the callable name pattern and replace with None.
    # Strategy: find slug for chapter and locate its ChapterModule block.
    slug_map = {22: "beverages", 23: "residues-feed"}
    if chapter not in slug_map:
        print(f"  WARNING: unknown chapter {chapter}, cannot update registry.")
        return

    # Replace: add_equivalence_axioms=add_equivalence_axioms_<slug_variant>,
    # The callable names follow the pattern add_equivalence_axioms_<suffix>
    # where suffix is derived from the module filename.
    suffix_map = {22: "beverages", 23: "ch23_feed"}
    suffix = suffix_map.get(chapter)
    if suffix is None:
        print(f"  WARNING: no suffix mapping for chapter {chapter}.")
        return

    old = f"add_equivalence_axioms=add_equivalence_axioms_{suffix},"
    new = f"add_equivalence_axioms=None,  # retired {retirement_date}"

    if old not in source:
        print(f"  WARNING: pattern not found in chapter_registry.py — already retired?")
        return

    updated = source.replace(old, new)
    registry_path.write_text(updated, encoding="utf-8")
    print(f"  Updated chapter_registry.py: add_equivalence_axioms=None for ch{chapter}")


def retire_chapter(chapter: int, retirement_date: str = TODAY) -> None:
    """Retire the hand-authored modules for *chapter*.

    Parameters
    ----------
    chapter:
        The CN chapter number (22 or 23).
    retirement_date:
        ISO date string recorded in the stub comment (default: today).
    """
    if chapter not in CHAPTER_MODULES:
        raise ValueError(
            f"Chapter {chapter} not in retirement map. "
            f"Known chapters: {sorted(CHAPTER_MODULES)}"
        )

    print(f"\nRetiring ch{chapter} hand-authored modules (date: {retirement_date})")
    print("=" * 60)
    print("WARNING: Only run this after manual validation of agent output")
    print("         AND a passing Konclude/owlrl consistency check.")
    print("=" * 60)

    for rel_path in CHAPTER_MODULES[chapter]:
        module_path = ROOT / rel_path
        if not module_path.exists():
            print(f"  SKIP: {rel_path} not found")
            continue
        _retire_module(module_path, retirement_date)

    _retire_registry_entry(chapter, retirement_date)

    print()
    print(f"ch{chapter} retirement complete. NEXT STEPS:")
    print(f"  1. Run: python3 -m pytest tests/ -q --ignore=tests/unit/test_wizard_scraper.py --ignore=tests/acceptance/")
    print(f"  2. Run Konclude consistency check on the generated ontology TTL.")
    print(f"  3. If tests or Konclude fail, restore from git: git checkout src/ontology/")


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <chapter_number>", file=sys.stderr)
        print(f"  e.g.: {sys.argv[0]} 22", file=sys.stderr)
        sys.exit(1)

    try:
        chapter = int(sys.argv[1])
    except ValueError:
        print(f"ERROR: chapter must be an integer, got {sys.argv[1]!r}", file=sys.stderr)
        sys.exit(1)

    retire_chapter(chapter)


if __name__ == "__main__":
    main()
