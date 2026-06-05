import pytest

pytestmark = pytest.mark.skip(reason="requires live EZT-Online access and Playwright browser")


def test_spot_traversal_10_nodes(tmp_path):
    from src.scraper.wizard import scrape_chapter

    nodes_seen = []

    def record(n):
        nodes_seen.append(n)

    tree = scrape_chapter(22, tmp_path, headless=True, on_node=record)
    assert len(nodes_seen) >= 5, f"Expected at least 5 nodes, got {len(nodes_seen)}"
    assert tree.root_node_id in tree.nodes
    depths = [len(n.path_from_root) for n in tree.nodes.values()]
    print(f"Max depth: {max(depths)}, nodes: {len(nodes_seen)}")
