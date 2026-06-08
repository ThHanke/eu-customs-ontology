from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.scraper.checkpoint import (
    append_node_jsonl,
    load_nodes_jsonl,
)

BASE_URL = "https://auskunft.ezt-online.de/ezto"
SEARCH_URL = f"{BASE_URL}/EztSuche.do"
CHECKPOINT_INTERVAL = 50


def _parent_code(code: str) -> str | None:
    """Return the parent 8-digit code by zeroing the rightmost non-zero digit pair.

    Hierarchy: CCNN0000 → CC000000 (heading → chapter)
               CCNNSS00 → CCNN0000 (subheading → heading)
               CCNNSSXX → CCNNSS00 (CN code → subheading)
    """
    if len(code) != 8:
        return None
    for suffix_len in (2, 4, 6):
        candidate = code[: 8 - suffix_len] + "0" * suffix_len
        if candidate != code:
            return candidate
    return None


def _build_hierarchy(codes_8: list[str]) -> dict[str, list[str]]:
    """Return {parent_code: [child_codes]} mapping."""
    code_set = set(codes_8)
    children: dict[str, list[str]] = {c: [] for c in codes_8}
    for code in sorted(codes_8):
        p = _parent_code(code)
        while p is not None:
            if p in code_set:
                children[p].append(code)
                break
            p = _parent_code(p)
    return children


def _lookup_description(page, code: str) -> tuple[str, bool]:
    """POST code to EztSuche.do; return (description, is_endlinie)."""
    page.fill("input[name='warennummer']", code)
    page.click("input[name='doSearch']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)
    body = page.inner_text("body")
    desc = ""
    if "Warenbeschreibung" in body:
        idx = body.find("Warenbeschreibung")
        # Description may be on same line after colon or on next non-empty line
        after = body[idx + len("Warenbeschreibung") :]
        first_line = after.split("\n")[0].strip().lstrip(":").strip()
        if first_line:
            desc = first_line
        else:
            for line in after.split("\n")[1:]:
                stripped = line.strip()
                if stripped and stripped != ":":
                    desc = stripped
                    break
    is_endlinie = "Endlinie" in body
    return desc or f"CN {code}", is_endlinie


def scrape_chapter(
    chapter: int,
    intermediate_dir: Path,
    *,
    headless: bool = True,
    storage_state_path: Path | None = None,
    on_node: Callable[[dict], None] | None = None,
) -> WizardTree:
    """Build WizardTree from TARIC codes + EZT Ausfuhr description lookup.

    Reads taric_ch{chapter:02d}.json from intermediate_dir for code list.
    Writes completed nodes to wizard_ch{chapter:02d}.jsonl.
    Returns a WizardTree with proper descriptions.
    """
    from playwright.sync_api import sync_playwright

    jsonl_path = intermediate_dir / f"wizard_ch{chapter:02d}.jsonl"
    taric_path = intermediate_dir / f"taric_ch{chapter:02d}.json"

    # Load TARIC codes
    taric_data = json.loads(taric_path.read_text()) if taric_path.exists() else {}
    measures = taric_data.get("measures", [])
    codes_10 = sorted(set(m["commodity_code"] for m in measures))
    # Deduplicate to 8-digit codes; keep codes that start with this chapter
    prefix = f"{chapter:02d}"
    codes_8 = sorted(
        set(c[:8] for c in codes_10 if c.startswith(prefix))
    )

    # Add chapter root if missing
    root_8 = f"{chapter:02d}000000"
    if root_8 not in codes_8:
        codes_8 = [root_8] + codes_8

    children_map = _build_hierarchy(codes_8)
    # Identify leaf codes: codes with no children in our set
    leaf_codes = {c for c in codes_8 if not children_map.get(c)}

    # Load already-scraped nodes; ignore orphan stubs from prior runs
    code_set = set(codes_8)
    existing: dict[str, ClassificationNode] = {}
    for nd in load_nodes_jsonl(jsonl_path):
        node = ClassificationNode.model_validate(nd)
        if node.node_id in code_set:
            existing[node.node_id] = node
    scraped_codes = {n.node_id for n in existing.values()}

    # If file has no valid nodes (e.g. old-format stub), truncate so we start clean
    if jsonl_path.exists() and not existing:
        jsonl_path.write_text("")

    nodes: dict[str, ClassificationNode] = dict(existing)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx_kwargs: dict = {}
        ss_path = storage_state_path or (intermediate_dir / "session_state_ausfuhr.json")
        if ss_path.exists():
            ctx_kwargs["storage_state"] = str(ss_path)
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        # Establish Ausfuhr session
        page.goto(f"{BASE_URL}/Init.do")
        page.wait_for_load_state("networkidle")
        page.click("input[value='zur Ausfuhr']")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(300)

        # Save session state for resumption
        context.storage_state(path=str(ss_path))

        for code in codes_8:
            if code in scraped_codes:
                continue

            desc, is_endlinie = _lookup_description(page, code)

            # Determine children answer options
            child_codes = children_map.get(code, [])
            answer_options = [
                AnswerOption(answer_text=c, next_node_id=c)
                for c in child_codes
            ]

            is_terminal = code in leaf_codes or is_endlinie
            cn_code = code if is_terminal else None

            # path_from_root: list of ancestor codes
            path: list[str] = []
            p = _parent_code(code)
            while p is not None:
                if p in {c for c in codes_8}:
                    path.insert(0, p)
                p = _parent_code(p)

            node = ClassificationNode(
                node_id=code,
                question_text=desc,
                answer_options=answer_options,
                is_terminal=is_terminal,
                cn_code=cn_code,
                path_from_root=path,
            )
            nodes[code] = node
            append_node_jsonl(jsonl_path, node.model_dump())
            if on_node:
                on_node(node.model_dump())

        browser.close()

    return WizardTree(
        chapter=chapter,
        nodes=nodes,
        root_node_id=root_8,
    )
