"""
gdep.wiki.index
index.md 자동 갱신.
WikiStore에 노드가 추가/수정될 때 index.md를 최신 상태로 유지한다.
"""
from __future__ import annotations

from pathlib import Path


def rebuild_index(wiki_dir: Path) -> None:
    """
    .wiki_meta.json의 모든 노드를 읽어 index.md를 재생성한다.
    노드가 추가/수정될 때마다 WikiStore.upsert() 이후 호출한다.
    """
    import json

    meta_path = wiki_dir / ".wiki_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return

    nodes = meta.get("nodes", {})
    by_type: dict[str, list[dict]] = {}
    for node_data in nodes.values():
        t = node_data.get("type", "other")
        by_type.setdefault(t, []).append(node_data)

    type_headers = {
        "class": "Classes",
        "asset": "Assets",
        "system": "Systems",
        "pattern": "Patterns",
        "conversation": "Conversations",
    }

    lines = [
        "# Wiki Index",
        "",
        "> Auto-maintained by gdep. Updated when analysis tools run.",
        "> Read `OVERVIEW.md` for the project architecture overview.",
        "",
        "## Overview",
        "- [[OVERVIEW]] — Project architecture overview (class count, coupling, engine systems)",
        "",
    ]

    for type_key, header in type_headers.items():
        type_nodes = by_type.get(type_key, [])
        lines.append(f"## {header}")
        lines.append("")
        if type_nodes:
            for n in sorted(type_nodes, key=lambda x: x.get("title", "")):
                file_path = n.get("file_path", "")
                title = n.get("title", n.get("id", "?"))
                stale_mark = " *(stale)*" if n.get("stale") else ""
                # Obsidian 링크 형식
                link_target = file_path.replace(".md", "")
                lines.append(f"- [[{link_target}|{title}]]{stale_mark}")
        else:
            lines.append("<!-- Auto-populated as analysis tools are called -->")
        lines.append("")

    index_path = wiki_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
