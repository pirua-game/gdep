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
        node_type: str | list[str] | None = None,
        limit: int = 50) -> str:
    """
    List all wiki nodes for this project (previously analyzed classes, assets, systems).

    Use this to see what has already been analyzed before starting fresh analysis.
    Stale nodes have changed source files and need re-analysis.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        node_type:    Optional filter. Single string or list:
                        'class', 'asset', 'system', 'pattern', 'conversation'
                        or e.g. ['class', 'asset'] to list multiple types.
                      None = lists all node types.
        limit:        Maximum nodes to show (default 50).

    Returns:
        Table of wiki nodes with type, title, staleness, and last update date.
    """
    try:
        from gdep.wiki.store import WikiStore
        from gdep.wiki.staleness import (
            build_class_fingerprint_map,
            get_project_fingerprint,
            is_node_stale,
        )

        store = WikiStore(project_path)
        nodes = store.list_nodes(node_type=node_type, limit=limit)

        if not nodes:
            if isinstance(node_type, list):
                type_note = f" of types {node_type}"
            else:
                type_note = f" of type '{node_type}'" if node_type else ""
            return (
                f"No wiki nodes found{type_note}.\n\n"
                "The wiki is empty. Run analysis tools to populate it:\n"
                "  - `explore_class_semantics(path, 'ClassName')` → creates class node\n"
                "  - `analyze_ue5_gas(path)` → creates GAS system node\n"
                "  - `detect_patterns(path)` → creates pattern nodes\n"
                "  - `analyze_ue5_blueprint_mapping(path)` → creates asset nodes"
            )

        # ── Live staleness 계산 ──────────────────────────────────
        # class 노드가 있으면 단일 walk로 전체 fingerprint 맵 구성
        has_class = any(n.type == "class" for n in nodes)

        class_fp_map: dict[str, str] = (
            build_class_fingerprint_map(project_path) if has_class else {}
        )
        # project_fp는 lazy: class 파일이 없는 경우(DLL 등)와 non-class 노드에 공통 사용
        _project_fp: list[str] = []  # mutable box for lazy init

        def _get_project_fp() -> str:
            if not _project_fp:
                _project_fp.append(get_project_fingerprint(project_path))
            return _project_fp[0]

        def _is_stale_live(n) -> bool:
            if n.type == "class":
                current = class_fp_map.get(n.title.lower())
                if current is None:
                    # 파일 없음(DLL/어셈블리) → project fingerprint로 fallback
                    current = _get_project_fp()
                return is_node_stale(n.source_fingerprint, current)
            return is_node_stale(n.source_fingerprint, _get_project_fp())

        # 타입별로 그룹화
        by_type: dict[str, list] = {}
        for node in nodes:
            by_type.setdefault(node.type, []).append(node)

        stale_count = sum(1 for n in nodes if _is_stale_live(n))
        header = f"## Wiki Nodes ({len(nodes)} total"
        if stale_count:
            header += f", ⚠ {stale_count} stale"
        header += ")\n"
        lines = [header]

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
                if _is_stale_live(n):
                    since = f" since {n.updated_at}" if n.updated_at else ""
                    stale = f"⚠ stale (source changed{since})"
                else:
                    stale = "✓ fresh"
                lines.append(f"| `{n.id}` | {n.updated_at} | {stale} |")
            lines.append("")

        lines.append(
            "> Use `wiki_get(project_path, node_id)` to read a node's full content.\n"
            "> Use `wiki_search(project_path, query)` to search by keyword."
        )
        if stale_count:
            lines.append(
                f"\n> ⚠ **{stale_count} node(s) are stale** — source files have changed since last analysis."
                " Re-run `explore_class_semantics` (or the relevant analysis tool) with `refresh=True` to update."
            )

        return "\n".join(lines)

    except Exception as e:
        return f"[wiki_list] Error: {e}"
