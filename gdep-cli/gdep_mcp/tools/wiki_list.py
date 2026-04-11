"""
gdep-mcp/tools/wiki_list.py

위키 노드 목록 조회.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))


def run(project_path: str,
        node_type: str | None = None,
        limit: int = 50) -> str:
    """
    List all wiki nodes for this project (previously analyzed classes, assets, systems).

    Use this to see what has already been analyzed before starting fresh analysis.
    Stale nodes have changed source files and need re-analysis.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        node_type:    Optional filter: 'class', 'asset', 'system', 'pattern', 'conversation'.
                      If None, lists all node types.
        limit:        Maximum nodes to show (default 50).

    Returns:
        Table of wiki nodes with type, title, staleness, and last update date.
    """
    try:
        from gdep.wiki.store import WikiStore

        store = WikiStore(project_path)
        nodes = store.list_nodes(node_type=node_type, limit=limit)

        if not nodes:
            type_note = f" of type '{node_type}'" if node_type else ""
            return (
                f"No wiki nodes found{type_note}.\n\n"
                "The wiki is empty. Run analysis tools to populate it:\n"
                "  - `explore_class_semantics(path, 'ClassName')` → creates class node\n"
                "  - `analyze_ue5_gas(path)` → creates GAS system node\n"
                "  - `detect_patterns(path)` → creates pattern nodes\n"
                "  - `analyze_ue5_blueprint_mapping(path)` → creates asset nodes"
            )

        # 타입별로 그룹화
        by_type: dict[str, list] = {}
        for node in nodes:
            by_type.setdefault(node.type, []).append(node)

        lines = [f"## Wiki Nodes ({len(nodes)} total)\n"]

        type_labels = {
            "class": "Classes",
            "asset": "Assets",
            "system": "Systems",
            "pattern": "Patterns",
            "conversation": "Conversations",
        }
        type_order = ["class", "asset", "system", "pattern", "conversation"]
        for t in type_order:
            type_nodes = by_type.get(t, [])
            if not type_nodes:
                continue
            label = type_labels.get(t, t.capitalize() + "s")
            lines.append(f"### {label} ({len(type_nodes)})")
            lines.append("")
            lines.append("| Node ID | Updated | Stale |")
            lines.append("|---------|---------|-------|")
            for n in sorted(type_nodes, key=lambda x: x.title):
                stale = "⚠ Yes" if n.stale else "✓ No"
                lines.append(f"| `{n.id}` | {n.updated_at} | {stale} |")
            lines.append("")

        lines.append(
            "> Use `wiki_get(project_path, node_id)` to read a node's full content.\n"
            "> Use `wiki_search(project_path, query)` to search by keyword."
        )

        return "\n".join(lines)

    except Exception as e:
        return f"[wiki_list] Error: {e}"
