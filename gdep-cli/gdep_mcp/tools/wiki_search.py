"""
gdep-mcp/tools/wiki_search.py

위키 노드 텍스트 검색.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))


def run(project_path: str, query: str,
        node_type: str | None = None,
        limit: int = 20) -> str:
    """
    Search the project wiki for previously analyzed classes, assets, and systems.

    The wiki accumulates analysis results across sessions. Use this tool FIRST
    to check if a class or asset has already been analyzed before calling
    explore_class_semantics or other analysis tools.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        query:        Search keyword or phrase.
                      Examples: "damage", "PlayerCharacter", "GAS ability"
        node_type:    Optional filter: 'class', 'asset', 'system', 'pattern', 'conversation'.
                      If None, searches all node types.
        limit:        Maximum number of results to return (default 20).

    Returns:
        List of matching wiki nodes with snippets.
    """
    try:
        from gdep.wiki.store import WikiStore

        store = WikiStore(project_path)
        matches = store.search(query, node_type=node_type, limit=limit)

        if not matches:
            return (
                f"No wiki nodes found matching '{query}'."
                + (f" (type filter: {node_type})" if node_type else "")
                + "\n\nTip: Run analysis tools (explore_class_semantics, analyze_ue5_gas, etc.) "
                + "to populate the wiki, then search again."
            )

        lines = [f"## Wiki Search: '{query}'", f"Found {len(matches)} result(s)\n"]
        for node, snippet in matches:
            stale_mark = " *(stale)*" if node.stale else ""
            lines.append(f"### [{node.type}] {node.title}{stale_mark}")
            lines.append(f"- **ID**: `{node.id}`")
            lines.append(f"- **File**: `.gdep/wiki/{node.file_path}`")
            lines.append(f"- **Updated**: {node.updated_at}")
            lines.append(f"- **Snippet**: {snippet}")
            lines.append(
                f"\n> Use `wiki_get(project_path, \"{node.id}\")` to read full content."
            )
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"[wiki_search] Error: {e}"
