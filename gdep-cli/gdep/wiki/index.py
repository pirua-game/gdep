"""
gdep.wiki.index
index.md 자동 갱신.

WikiStore에 노드가 추가/수정될 때 index.md를 최신 상태로 유지한다.
SQLite wiki_nodes 테이블에서 직접 읽어 구성한다.
.wiki_meta.json fallback 제거 — DB가 source of truth.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def rebuild_index(wiki_dir: Path) -> None:
    """
    .wiki_index.db의 모든 노드를 읽어 index.md를 재생성한다.
    노드가 추가/수정될 때마다 WikiStore.upsert() 이후 호출한다.
    """
    db_path = wiki_dir / ".wiki_index.db"

    if not db_path.exists():
        # DB가 없으면 index 갱신 불가 (초기화 전)
        return

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, type, title, file_path, stale FROM wiki_nodes"
        ).fetchall()
        conn.close()
    except Exception:
        return

    by_type: dict[str, list[dict]] = {}
    for row in rows:
        t = row["type"] or "other"
        by_type.setdefault(t, []).append({
            "id":        row["id"],
            "type":      t,
            "title":     row["title"],
            "file_path": row["file_path"],
            "stale":     bool(row["stale"]),
        })

    type_headers = {
        "class":        "Classes",
        "asset":        "Assets",
        "system":       "Systems",
        "pattern":      "Patterns",
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
                file_path  = n.get("file_path", "")
                title      = n.get("title", n.get("id", "?"))
                stale_mark = " *(stale)*" if n.get("stale") else ""
                link_target = file_path.replace(".md", "")
                lines.append(f"- [[{link_target}|{title}]]{stale_mark}")
        else:
            lines.append("<!-- Auto-populated as analysis tools are called -->")
        lines.append("")

    index_path = wiki_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
