"""
gdep.wiki.store
위키 노드 읽기/쓰기/검색.

저장 방식:
  - .gdep/wiki/.wiki_meta.json  : 전체 노드 인덱스 (id → 메타데이터)
  - .gdep/wiki/{type}s/{name}.md : 마크다운 파일 (YAML frontmatter 포함)
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Iterator

from gdep import __version__
from .models import WikiNode


class WikiStore:
    """게임 프로젝트의 위키 노드를 관리한다."""

    def __init__(self, project_path: str) -> None:
        from gdep.detector import detect
        profile = detect(project_path)
        self._wiki_dir = Path(profile.root) / ".gdep" / "wiki"
        self._meta_path = self._wiki_dir / ".wiki_meta.json"
        self._meta: dict | None = None  # lazy load

    # ── Meta JSON ─────────────────────────────────────────────

    def _load_meta(self) -> dict:
        if self._meta is None:
            try:
                self._meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            except Exception:
                self._meta = {"version": 1, "gdep_version": __version__, "nodes": {}}
        return self._meta

    def _save_meta(self) -> None:
        meta = self._load_meta()
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        self._meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # ── Node CRUD ─────────────────────────────────────────────

    def get(self, node_id: str) -> WikiNode | None:
        """노드 ID로 WikiNode 메타데이터 조회. 파일 내용은 read_content()로."""
        meta = self._load_meta()
        node_data = meta.get("nodes", {}).get(node_id)
        if node_data is None:
            return None
        return WikiNode.from_dict(node_data)

    def exists(self, node_id: str) -> bool:
        return node_id in self._load_meta().get("nodes", {})

    def upsert(self, node: WikiNode, content: str) -> None:
        """노드 메타데이터 저장 + 마크다운 파일 작성."""
        # 마크다운 파일 작성
        md_path = self._wiki_dir / node.file_path
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(content, encoding="utf-8")

        # 메타 업데이트
        meta = self._load_meta()
        meta["nodes"][node.id] = node.to_dict()
        self._save_meta()

    def read_content(self, node: WikiNode) -> str:
        """노드의 마크다운 파일 내용 반환."""
        md_path = self._wiki_dir / node.file_path
        try:
            return md_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"[Wiki node '{node.id}' file not found: {node.file_path}]"

    def mark_stale(self, node_id: str) -> None:
        meta = self._load_meta()
        if node_id in meta.get("nodes", {}):
            meta["nodes"][node_id]["stale"] = True
            self._save_meta()

    def list_nodes(self, node_type: str | None = None,
                   limit: int = 100) -> list[WikiNode]:
        """노드 목록 반환. node_type으로 필터링 가능."""
        meta = self._load_meta()
        results = []
        for node_data in meta.get("nodes", {}).values():
            if node_type and node_data.get("type") != node_type:
                continue
            results.append(WikiNode.from_dict(node_data))
            if len(results) >= limit:
                break
        return results

    def search(self, query: str, node_type: str | None = None,
               limit: int = 20) -> list[tuple[WikiNode, str]]:
        """
        위키 노드 텍스트 검색 (간단한 키워드 매칭).
        반환: [(node, snippet), ...]
        """
        query_lower = query.lower()
        results: list[tuple[WikiNode, str]] = []

        for node in self.list_nodes(node_type=node_type, limit=1000):
            # 제목에서 매칭
            if query_lower in node.title.lower():
                results.append((node, f"Title match: {node.title}"))
                continue

            # 파일 내용에서 매칭
            md_path = self._wiki_dir / node.file_path
            try:
                content = md_path.read_text(encoding="utf-8")
                idx = content.lower().find(query_lower)
                if idx >= 0:
                    start = max(0, idx - 60)
                    end = min(len(content), idx + len(query) + 60)
                    snippet = "..." + content[start:end].replace("\n", " ") + "..."
                    results.append((node, snippet))
            except Exception:
                pass

            if len(results) >= limit:
                break

        return results

    # ── Log ────────────────────────────────────────────────────

    def append_log(self, action: str, description: str) -> None:
        """log.md에 타임라인 엔트리 추가."""
        log_path = self._wiki_dir / "log.md"
        today = date.today().strftime("%Y-%m-%d")
        entry = f"\n## [{today}] {action} | {description}\n"
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass


def make_node_id(node_type: str, name: str) -> str:
    """위키 노드 ID 생성. 예: make_node_id('class', 'PlayerCharacter') → 'class:PlayerCharacter'"""
    return f"{node_type}:{name}"


def make_file_path(node_type: str, name: str) -> str:
    """위키 파일 경로 생성. 예: make_file_path('class', 'PlayerCharacter') → 'classes/PlayerCharacter.md'"""
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
    type_to_dir = {
        "class": "classes",
        "asset": "assets",
        "system": "systems",
        "pattern": "patterns",
        "conversation": "conversations",
    }
    dir_name = type_to_dir.get(node_type, node_type + "s")
    return f"{dir_name}/{safe_name}.md"
