"""
gdep-mcp/tools/wiki_save_conversation.py

에이전트 세션 대화 요약을 위키 노드로 저장.
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import date
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))


def _make_slug(title: str) -> str:
    """제목을 파일명/ID에 사용 가능한 slug로 변환 (40자 제한)."""
    s = re.sub(r"[^\w\s-]", "", title.lower())
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s[:40]


def run(project_path: str,
        title: str,
        content: str,
        referenced_classes: list[str] | None = None,
        tags: list[str] | None = None,
        tools_used: list[str] | None = None) -> str:
    """
    Save an agent conversation summary to the project wiki.

    Call this at the end of a session (or at any meaningful checkpoint)
    to persist what was discussed, decided, and discovered.
    Conversations accumulate across sessions — future agents can search
    and build on previous session context.

    Args:
        project_path:       Absolute path to the project Scripts/Source directory.
        title:              Session title — brief and descriptive.
                            Example: "Zombie AI GAS ability analysis"
        content:            Conversation summary in markdown. Recommended structure:
                            ## Summary — 1-3 bullet overview
                            ## Key Findings — discoveries, dependencies, issues
                            ## Decisions — architectural choices + rationale
                            ## Open Questions — unresolved items
                            ## Next Steps — what to investigate next
        referenced_classes: Optional list of class names discussed in this session.
                            Creates 'discussed_in' edges → discoverable with related=True.
                            Example: ["ULyraAbilitySystemComponent", "ZombieCharacter"]
        tags:               Optional keyword tags for search.
                            Example: ["gas", "ability", "zombie-ai"]
        tools_used:         Optional list of gdep tools used during this session.
                            Example: ["explore_class_semantics", "analyze_ue5_gas"]

    Returns:
        Confirmation message with node ID, file path, and edge count.
    """
    try:
        from gdep.wiki.store import WikiStore, make_node_id, make_file_path
        from gdep.wiki.models import WikiNode, WikiEdge, EDGE_DISCUSSED_IN
        from gdep.wiki.node_writer import make_conversation_page
        from gdep.wiki.edge_extractor import extract_edges
        from gdep.wiki.index import rebuild_index
        from gdep.detector import detect

        store = WikiStore(project_path)

        # 1. slug + 노드 ID 생성
        slug = _make_slug(title)
        today = date.today().strftime("%Y-%m-%d")
        session_id = f"{today}-{slug}"
        node_id = make_node_id("conversation", session_id)

        # 2. 기존 노드 확인 (같은 날 같은 title → upsert, created_at 유지)
        existing = store.get(node_id)

        # 3. content MD5를 fingerprint로 사용 (소스 파일 연동 없음)
        fp = hashlib.md5(content.encode("utf-8")).hexdigest()

        # 4. 페이지 생성 + 저장
        page = make_conversation_page(title, content, fp, tags, tools_used)
        file_path = make_file_path("conversation", session_id)
        node = WikiNode(
            id=node_id,
            type="conversation",
            title=title,
            file_path=file_path,
            source_fingerprint=fp,
            created_at=existing.created_at if existing else today,
            updated_at=today,
            stale=False,
            meta={
                "tags": tags or [],
                "tools_used": tools_used or [],
                "session_date": today,
            },
        )
        store.upsert(node, page)
        store.append_log("save_conversation", node_id)

        # 5. 엣지 수집 — 명시적 referenced_classes → discussed_in
        edges: list[WikiEdge] = []
        for cls in (referenced_classes or []):
            cls = cls.strip()
            if cls:
                edges.append(WikiEdge(
                    source=node_id,
                    target=f"class:{cls}",
                    relation=EDGE_DISCUSSED_IN,
                ))

        # 6. content에서 자동 엣지 추출 (Behavioral Dependencies / Inheritance 등)
        try:
            auto_edges = extract_edges(node_id, content)
            edges.extend(auto_edges)
        except Exception:
            pass

        if edges:
            store.upsert_edges(node_id, edges)

        # 7. index.md 갱신
        try:
            profile = detect(project_path)
            wiki_dir = Path(profile.root) / ".gdep" / "wiki"
            rebuild_index(wiki_dir)
        except Exception:
            pass

        # 8. 결과 요약
        edge_count = len(edges)
        result_lines = [
            f"Conversation saved: `{node_id}`",
            f"File: `.gdep/wiki/{file_path}`",
            f"Edges: {edge_count} relationship(s) indexed",
        ]
        if existing:
            result_lines.append(
                f"Updated existing node (originally created {existing.created_at})"
            )
        result_lines += [
            "",
            f"> Use `wiki_get(project_path, \"{node_id}\")` to read full content.",
            f"> Use `wiki_search(project_path, \"{title}\", node_type=\"conversation\")` to search.",
        ]
        return "\n".join(result_lines)

    except Exception as e:
        return f"[wiki_save_conversation] Error: {e}"
