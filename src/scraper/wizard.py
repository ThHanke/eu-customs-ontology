from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Callable

from src.schema.wizard import AnswerOption, ClassificationNode, WizardTree
from src.scraper.checkpoint import (
    append_node_jsonl,
    load_checkpoint,
    load_nodes_jsonl,
    save_checkpoint,
)

ENTRY_URL = "https://auskunft.ezt-online.de/ezto/SeqEinreihungSucheAnzeige.do"
CN_CODE_RE = re.compile(r"\b(\d{8,10})\b")
CHECKPOINT_INTERVAL = 50


def state_key(url: str, form_data: dict[str, str]) -> str:
    param_str = "&".join(f"{k}={v}" for k, v in sorted(form_data.items()))
    return hashlib.sha256(f"{url}|{param_str}".encode()).hexdigest()


def scrape_chapter(
    chapter: int,
    intermediate_dir: Path,
    *,
    headless: bool = True,
    storage_state_path: Path | None = None,
    on_node: Callable[[dict], None] | None = None,
) -> WizardTree:
    """DFS traversal of the EZT wizard for the given chapter.

    Writes completed nodes to wizard_ch{chapter:02d}.jsonl and checkpoint state
    to checkpoint_ch{chapter:02d}.json every CHECKPOINT_INTERVAL nodes.

    Returns a WizardTree built from all completed nodes.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    import datetime

    jsonl_path = intermediate_dir / f"wizard_ch{chapter:02d}.jsonl"
    ckpt_path = intermediate_dir / f"checkpoint_ch{chapter:02d}.json"
    err_dir = intermediate_dir

    chapter_prefix = f"{chapter:02d}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx_kwargs: dict = {}
        ss_path = storage_state_path or (intermediate_dir / "session_state.json")
        if ss_path.exists():
            ctx_kwargs["storage_state"] = str(ss_path)
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        def _navigate_entry():
            page.goto(ENTRY_URL)
            page.wait_for_load_state("networkidle")
            context.storage_state(path=str(ss_path))

        def _select_chapter():
            # Try to find a chapter dropdown or link for the given chapter
            # EZT uses a form with chapter selection; look for chapter 22 option
            try:
                # Select by value if a <select> exists
                page.select_option("select[name*='kapitel'], select[name*='chapter']",
                                   value=str(chapter), timeout=5000)
            except Exception:
                # Fall back: click a link matching the chapter number
                page.click(f"a:has-text('{chapter_prefix}')", timeout=5000)
            page.wait_for_load_state("networkidle")

        def _extract_node(url: str, path_from_root: list[str]) -> ClassificationNode | None:
            content = page.content()
            # Extract question text from the main question element
            q_el = page.query_selector(".frage, .question, #question, [class*='frage']")
            question_text = q_el.inner_text().strip() if q_el else ""

            # Extract answer options — look for radio buttons or submit buttons with answer labels
            options: list[AnswerOption] = []
            answer_els = page.query_selector_all("input[type='radio'], button[type='submit']")
            for el in answer_els:
                label = ""
                el_id = el.get_attribute("id")
                if el_id:
                    lbl = page.query_selector(f"label[for='{el_id}']")
                    if lbl:
                        label = lbl.inner_text().strip()
                if not label:
                    label = el.get_attribute("value") or el.inner_text().strip()
                if label:
                    options.append(AnswerOption(answer_text=label, next_node_id=None))

            # Detect terminal node: CN code in page
            cn_match = CN_CODE_RE.search(content)
            cn_code = cn_match.group(1) if (cn_match and not options) else None
            is_terminal = cn_code is not None or len(options) == 0

            # Build node_id from path
            node_id = hashlib.sha256("|".join(path_from_root).encode()).hexdigest()[:16]

            return ClassificationNode(
                node_id=node_id,
                question_text=question_text or "(no question)",
                answer_options=options if not is_terminal else [],
                is_terminal=is_terminal,
                cn_code=cn_code if is_terminal else None,
                path_from_root=list(path_from_root),
            )

        # Load checkpoint if exists
        ckpt = load_checkpoint(ckpt_path)
        visited: set[str] = set(ckpt["visited"]) if ckpt else set()
        frontier: list[tuple[str, dict, list[str]]] = []
        if ckpt:
            for item in ckpt["frontier"]:
                frontier.append((item["url"], item["form_data"], item["path"]))

        if not frontier:
            _navigate_entry()
            _select_chapter()
            initial_url = page.url
            initial_forms = {}  # entry form data after chapter selection
            frontier = [(initial_url, initial_forms, [])]

        nodes: dict[str, ClassificationNode] = {}
        # Load already-completed nodes from JSONL
        for nd in load_nodes_jsonl(jsonl_path):
            node = ClassificationNode.model_validate(nd)
            nodes[node.node_id] = node

        root_node_id: str | None = None
        node_count = 0

        while frontier:
            url, form_data, path = frontier.pop()
            sk = state_key(url, form_data)
            if sk in visited:
                continue
            visited.add(sk)

            try:
                if form_data:
                    # POST the form
                    page.goto(url)
                    page.wait_for_load_state("networkidle")

                node = _extract_node(page.url, path)
                nodes[node.node_id] = node
                if on_node:
                    on_node(node.model_dump())
                append_node_jsonl(jsonl_path, node.model_dump())
                node_count += 1

                if root_node_id is None and not path:
                    root_node_id = node.node_id

                if not node.is_terminal:
                    # Click each answer option to discover next states
                    answer_els = page.query_selector_all("input[type='radio'], button[type='submit']")
                    for i, el in enumerate(answer_els):
                        answer_text = ""
                        el_id = el.get_attribute("id")
                        if el_id:
                            lbl = page.query_selector(f"label[for='{el_id}']")
                            if lbl:
                                answer_text = lbl.inner_text().strip()
                        if not answer_text:
                            answer_text = el.get_attribute("value") or el.inner_text().strip()

                        next_path = path + [answer_text]
                        # Push the state: we'll navigate to it by replaying from entry
                        next_state = state_key(page.url, {str(i): answer_text})
                        if next_state not in visited:
                            frontier.append((page.url, {"_answer_idx": str(i), "_text": answer_text}, next_path))

            except PlaywrightTimeout as exc:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                page.screenshot(path=str(err_dir / f"error_{ts}.png"))
                save_checkpoint(ckpt_path, visited, [
                    {"url": u, "form_data": fd, "path": p} for u, fd, p in frontier
                ])
                raise RuntimeError(
                    f"Timeout after {node_count} nodes. Checkpoint saved to {ckpt_path}."
                ) from exc

            # Detect session expiry: response URL reverted to entry despite being mid-traversal
            if path and ENTRY_URL in page.url:
                save_checkpoint(ckpt_path, visited, [
                    {"url": u, "form_data": fd, "path": p} for u, fd, p in frontier
                ])
                raise RuntimeError(
                    f"Session expired after {node_count} nodes. "
                    f"Resume from checkpoint {ckpt_path}."
                )

            if node_count % CHECKPOINT_INTERVAL == 0:
                save_checkpoint(ckpt_path, visited, [
                    {"url": u, "form_data": fd, "path": p} for u, fd, p in frontier
                ])

        browser.close()

    return WizardTree(
        chapter=chapter,
        nodes=nodes,
        root_node_id=root_node_id or (next(iter(nodes)) if nodes else ""),
    )
