"""
gdep-mcp/tools/wiki_get.py

특정 위키 노드 내용 조회.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))


def run(project_path: str, node_id: str) -> str:
    """
    Read the full content of a wiki node by its ID.

    Wiki nodes contain previously analyzed class structures, asset mappings,
    system overviews, and pattern documentation accumulated across sessions.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        node_id:      The wiki node ID to retrieve.
                      Format: 'class:ClassName', 'asset:AssetName',
                               'system:gas', 'pattern:Singleton'
                      Examples: 'class:PlayerCharacter', 'asset:BP_GA_BasicAttack',
                                'system:gas', 'class:DamageManager'

    Returns:
        Full markdown content of the wiki node, including frontmatter.
        Returns an error message if the node is not found.
    """
    try:
        from gdep.wiki.store import WikiStore

        store = WikiStore(project_path)
        node = store.get(node_id)

        if node is None:
            # 가능한 노드 ID 제안
            all_nodes = store.list_nodes(limit=10)
            suggestions = [n.id for n in all_nodes[:5]]
            suggestion_str = (
                "\n\nAvailable nodes (first 5):\n"
                + "\n".join(f"  - `{s}`" for s in suggestions)
                if suggestions else ""
            )
            return (
                f"Wiki node not found: `{node_id}`\n"
                f"Use `wiki_list(project_path)` to see all available nodes."
                + suggestion_str
            )

        content = store.read_content(node)

        stale_warning = ""
        if node.stale:
            stale_warning = (
                "\n\n> ⚠ **This wiki node is stale** — the source may have changed. "
                "Re-run the analysis tool to update it.\n"
            )

        header = f"## Wiki Node: `{node_id}`\n> Type: {node.type} | Updated: {node.updated_at}\n\n"
        return header + stale_warning + content

    except Exception as e:
        return f"[wiki_get] Error: {e}"
