"""
gdep-mcp/tools/wiki_search.py

위키 노드 FTS5 전문 검색 + 관계 기반 확장 검색.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))


def run(project_path: str, query: str,
        node_type: str | list[str] | None = None,
        related: bool = False,
        limit: int = 20) -> str:
    """
    Search the project wiki for previously analyzed classes, assets, and systems.

    Uses FTS5 full-text search (BM25 ranking) when available — finds nodes
    even when you don't know the exact class name. Multi-word queries use OR logic.

    The wiki accumulates analysis results across sessions. Use this tool FIRST
    to check if a class or asset has already been analyzed before calling
    explore_class_semantics or other analysis tools.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        query:        Search keyword or phrase. Multi-word searches are OR'd.
                      Examples: "damage", "PlayerCharacter", "GAS ability", "좀비 AI"
        node_type:    Optional filter. Single string or list:
                        'class', 'asset', 'system', 'pattern', 'conversation'
                        or e.g. ['class', 'asset'] to search multiple types.
                      None = search all types.
        related:      If True, also returns nodes connected via dependency edges
                      (depends_on, referenced_by, inherits, uses_asset).
                      Useful for finding related classes without knowing their names.
        limit:        Maximum number of results to return (default 20).

    Returns:
        List of matching wiki nodes with BM25 scores and content snippets.
    """
    try:
        from gdep.wiki.store import WikiStore

        store = WikiStore(project_path)
        matches = store.search(query, node_type=node_type, related=related, limit=limit)

        if not matches:
            type_note = ""
            if isinstance(node_type, list):
                type_note = f" (type filter: {node_type})"
            elif node_type:
                type_note = f" (type filter: {node_type})"
            return (
                f"No wiki nodes found matching '{query}'.{type_note}\n\n"
                "Tip: Run analysis tools (explore_class_semantics, analyze_ue5_gas, etc.) "
                "to populate the wiki, then search again."
            )

        # 헤더
        type_label = ""
        if isinstance(node_type, list):
            type_label = f" [type: {'/'.join(node_type)}]"
        elif node_type:
            type_label = f" [type: {node_type}]"
        related_label = " +related" if related else ""
        lines = [
            f"## Wiki Search: '{query}'{type_label}{related_label}",
            f"Found {len(matches)} result(s)\n",
        ]

        fts_mode = store._fts_available
        for node, snippet, score in matches:
            stale_mark = " *(stale)*" if node.stale else ""
            is_related = snippet.startswith("[related via")

            # BM25 스코어 표시 (FTS5 모드, 관련 노드 제외)
            score_str = ""
            if fts_mode and not is_related and score != 0.0:
                # bm25는 음수 → 절댓값이 클수록 관련성 높음
                score_str = f" *(relevance: {abs(score):.2f})*"

            lines.append(f"### [{node.type}] {node.title}{stale_mark}{score_str}")
            lines.append(f"- **ID**: `{node.id}`")
            lines.append(f"- **File**: `.gdep/wiki/{node.file_path}`")
            lines.append(f"- **Updated**: {node.updated_at}")
            if is_related:
                lines.append(f"- **Link**: {snippet}")
            elif snippet:
                lines.append(f"- **Snippet**: {snippet}")
            lines.append(
                f"\n> Use `wiki_get(project_path, \"{node.id}\")` to read full content."
            )
            lines.append("")

        if not fts_mode:
            lines.append(
                "> ℹ FTS5 unavailable — using substring search. "
                "Upgrade SQLite for BM25 full-text ranking."
            )

        return "\n".join(lines)

    except Exception as e:
        return f"[wiki_search] Error: {e}"
