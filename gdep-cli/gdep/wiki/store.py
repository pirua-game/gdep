"""
gdep.wiki.store
위키 노드 읽기/쓰기/검색.

저장 방식:
  - .gdep/wiki/.wiki_index.db   : SQLite (노드 메타 + FTS5 전문 검색 + 엣지) — 파생 인덱스
  - .gdep/wiki/{type}s/{name}.md : 마크다운 파일 (YAML frontmatter 포함) — source of truth

DB 손상 시 rebuild_from_files()로 .md 파일에서 완전 복구 가능.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from .models import WikiNode, WikiEdge

_SCHEMA_VERSION = "2"  # FTS5 + edges 추가 시 버전 올림

# ── DDL ────────────────────────────────────────────────────────

_BASE_DDL = """\
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS wiki_nodes (
    id                 TEXT PRIMARY KEY,
    type               TEXT NOT NULL,
    title              TEXT NOT NULL,
    file_path          TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    stale              INTEGER NOT NULL DEFAULT 0,
    meta               TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON wiki_nodes(type);

CREATE TABLE IF NOT EXISTS wiki_edges (
    source   TEXT NOT NULL,
    target   TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight   REAL NOT NULL DEFAULT 1.0,
    UNIQUE(source, target, relation)
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON wiki_edges(source);
CREATE INDEX IF NOT EXISTS idx_edges_target ON wiki_edges(target);

CREATE TABLE IF NOT EXISTS wiki_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_FTS_DDL = """\
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    title,
    content,
    node_type UNINDEXED,
    node_id   UNINDEXED,
    tokenize  = 'unicode61'
);
"""


class WikiStore:
    """게임 프로젝트의 위키 노드를 관리한다."""

    def __init__(self, project_path: str) -> None:
        from gdep.detector import detect
        profile = detect(project_path)
        self._wiki_dir = Path(profile.root) / ".gdep" / "wiki"
        self._db_path = self._wiki_dir / ".wiki_index.db"
        self._conn: sqlite3.Connection | None = None
        self._fts_available: bool = True
        self._ensure_db()

    # ── Connection ─────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path), check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Schema + Migration ─────────────────────────────────────

    def _ensure_db(self) -> None:
        """DB 스키마 생성 + JSON → SQLite 마이그레이션."""
        self._wiki_dir.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()

        # 기본 테이블
        conn.executescript(_BASE_DDL)

        # FTS5 — 없는 환경(구형 SQLite 빌드) 대비 폴백
        try:
            conn.executescript(_FTS_DDL)
            self._fts_available = True
        except sqlite3.OperationalError:
            self._fts_available = False

        # 스키마 버전
        try:
            ver = conn.execute(
                "SELECT value FROM wiki_config WHERE key='schema_version'"
            ).fetchone()
            if ver is None:
                conn.execute(
                    "INSERT INTO wiki_config VALUES ('schema_version', ?)",
                    (_SCHEMA_VERSION,),
                )
                conn.commit()
        except Exception:
            pass

        # JSON 마이그레이션 (기존 .wiki_meta.json 존재 시)
        meta_path = self._wiki_dir / ".wiki_meta.json"
        if meta_path.exists():
            self._migrate_from_json(meta_path)

        # FTS 인덱스가 비어있지만 wiki_nodes에 데이터가 있으면 자동 rebuild
        # (JSON→SQLite 마이그레이션 이후 FTS가 구성되지 않았던 이전 버전 DB 복구)
        if self._fts_available:
            try:
                node_count = conn.execute("SELECT COUNT(*) FROM wiki_nodes").fetchone()[0]
                fts_count = conn.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0]
                if node_count > 0 and fts_count == 0:
                    self.rebuild_from_files()
            except Exception:
                pass

        # FTS 본문 CamelCase 분리 포맷 버전 확인 (fts_body_version=3 미적용 시 자동 rebuild)
        # v2: _split_camel_in_text 도입 / v3: _parse_node_from_md created/updated 키 호환 수정
        if self._fts_available:
            try:
                fts_ver = conn.execute(
                    "SELECT value FROM wiki_config WHERE key='fts_body_version'"
                ).fetchone()
                if fts_ver is None or fts_ver[0] != "3":
                    self.rebuild_from_files()
                    conn.execute(
                        "INSERT OR REPLACE INTO wiki_config VALUES ('fts_body_version', '3')"
                    )
                    conn.commit()
            except Exception:
                pass

    def _migrate_from_json(self, meta_path: Path) -> None:
        """기존 .wiki_meta.json → SQLite 마이그레이션."""
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return

        nodes = meta.get("nodes", {})
        if not nodes:
            # 빈 파일이면 그냥 백업
            try:
                meta_path.rename(meta_path.with_suffix(".json.bak"))
            except Exception:
                pass
            return

        conn = self._get_conn()
        migrated = 0
        for node_data in nodes.values():
            try:
                node = WikiNode.from_dict(node_data)
                conn.execute(
                    """INSERT OR IGNORE INTO wiki_nodes
                       (id, type, title, file_path, source_fingerprint,
                        created_at, updated_at, stale, meta)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        node.id, node.type, node.title, node.file_path,
                        node.source_fingerprint, node.created_at, node.updated_at,
                        1 if node.stale else 0, json.dumps(node.meta),
                    ),
                )
                # FTS 인덱싱
                if self._fts_available:
                    md_path = self._wiki_dir / node.file_path
                    try:
                        body = _strip_frontmatter(md_path.read_text(encoding="utf-8"))
                    except Exception:
                        body = node.title
                    conn.execute("DELETE FROM wiki_fts WHERE node_id=?", (node.id,))
                    fts_content = _split_camel(node.title) + "\n" + _split_camel_in_text(body)
                    conn.execute(
                        "INSERT INTO wiki_fts(title, content, node_type, node_id) "
                        "VALUES (?,?,?,?)",
                        (node.title, fts_content, node.type, node.id),
                    )
                migrated += 1
            except Exception:
                pass

        conn.commit()

        if migrated > 0:
            # 마이그레이션 성공 → JSON 백업
            try:
                meta_path.rename(meta_path.with_suffix(".json.bak"))
            except Exception:
                pass

    def rebuild_from_files(self) -> int:
        """.md 파일 스캔으로 DB 재구축. DB 손상/삭제 시 복구용."""
        conn = self._get_conn()
        rebuilt = 0
        skip_names = {"index.md", "OVERVIEW.md", "log.md"}

        for md_path in self._wiki_dir.rglob("*.md"):
            if md_path.name in skip_names:
                continue
            try:
                content = md_path.read_text(encoding="utf-8")
                node = _parse_node_from_md(content, md_path, self._wiki_dir)
                if node is None:
                    continue
                conn.execute(
                    """INSERT OR REPLACE INTO wiki_nodes
                       (id, type, title, file_path, source_fingerprint,
                        created_at, updated_at, stale, meta)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        node.id, node.type, node.title, node.file_path,
                        node.source_fingerprint, node.created_at, node.updated_at,
                        1 if node.stale else 0, json.dumps(node.meta),
                    ),
                )
                if self._fts_available:
                    body = _strip_frontmatter(content)
                    fts_content = _split_camel(node.title) + "\n" + _split_camel_in_text(body)
                    conn.execute("DELETE FROM wiki_fts WHERE node_id=?", (node.id,))
                    conn.execute(
                        "INSERT INTO wiki_fts(title, content, node_type, node_id) "
                        "VALUES (?,?,?,?)",
                        (node.title, fts_content, node.type, node.id),
                    )
                rebuilt += 1
            except Exception:
                pass

        conn.commit()
        return rebuilt

    # ── Node CRUD ─────────────────────────────────────────────

    def get(self, node_id: str) -> WikiNode | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM wiki_nodes WHERE id=?", (node_id,)
        ).fetchone()
        return _row_to_node(row) if row else None

    def exists(self, node_id: str) -> bool:
        conn = self._get_conn()
        return conn.execute(
            "SELECT 1 FROM wiki_nodes WHERE id=?", (node_id,)
        ).fetchone() is not None

    def upsert(self, node: WikiNode, content: str) -> None:
        """노드 저장: .md 파일 + wiki_nodes + FTS 갱신."""
        # 1. .md 파일 작성 (source of truth)
        md_path = self._wiki_dir / node.file_path
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(content, encoding="utf-8")

        # 2. wiki_nodes INSERT OR REPLACE
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO wiki_nodes
               (id, type, title, file_path, source_fingerprint,
                created_at, updated_at, stale, meta)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                node.id, node.type, node.title, node.file_path,
                node.source_fingerprint, node.created_at, node.updated_at,
                1 if node.stale else 0, json.dumps(node.meta),
            ),
        )

        # 3. FTS 갱신 (frontmatter 제거한 본문 + CamelCase 분리 제목)
        if self._fts_available:
            body = _strip_frontmatter(content)
            fts_content = _split_camel(node.title) + "\n" + _split_camel_in_text(body)
            conn.execute("DELETE FROM wiki_fts WHERE node_id=?", (node.id,))
            conn.execute(
                "INSERT INTO wiki_fts(title, content, node_type, node_id) "
                "VALUES (?,?,?,?)",
                (node.title, fts_content, node.type, node.id),
            )

        conn.commit()

    def read_content(self, node: WikiNode) -> str:
        """노드의 마크다운 본문 반환 (YAML frontmatter 제거)."""
        md_path = self._wiki_dir / node.file_path
        try:
            raw = md_path.read_text(encoding="utf-8")
            return _strip_frontmatter(raw)
        except FileNotFoundError:
            return f"[Wiki node '{node.id}' file not found: {node.file_path}]"

    def mark_stale(self, node_id: str) -> None:
        conn = self._get_conn()
        conn.execute("UPDATE wiki_nodes SET stale=1 WHERE id=?", (node_id,))
        conn.commit()

    def list_nodes(self, node_type: str | list[str] | None = None,
                   limit: int = 100) -> list[WikiNode]:
        """노드 목록 반환. node_type은 str 또는 list[str]로 필터링 가능."""
        conn = self._get_conn()
        if isinstance(node_type, list) and node_type:
            placeholders = ",".join("?" * len(node_type))
            rows = conn.execute(
                f"SELECT * FROM wiki_nodes WHERE type IN ({placeholders}) LIMIT ?",
                [*node_type, limit],
            ).fetchall()
        elif node_type:
            rows = conn.execute(
                "SELECT * FROM wiki_nodes WHERE type=? LIMIT ?",
                (node_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM wiki_nodes LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_node(r) for r in rows]

    # ── Search ─────────────────────────────────────────────────

    def search(self, query: str,
               node_type: str | list[str] | None = None,
               related: bool = False,
               limit: int = 20,
               mode: str = "or") -> list[tuple[WikiNode, str, float]]:
        """
        위키 노드 검색.

        Args:
            query:     검색 키워드 (멀티워드 검색)
            node_type: 'class', ['class','asset'] 등 타입 필터
            related:   True이면 엣지 기반으로 관련 노드도 포함
            limit:     최대 결과 수
            mode:      'or' (기본) | 'and' | 'phrase'
                       or    — 단어 중 하나라도 포함
                       and   — 모든 단어 포함
                       phrase — 정확한 구문 순서 매칭

        Returns:
            [(node, snippet, bm25_score), ...]
            score가 낮을수록 관련성 높음 (BM25 부호 반전됨)
        """
        if mode not in ("or", "and", "phrase"):
            mode = "or"
        if self._fts_available:
            results = self._search_fts(query, node_type, related, limit, mode)
            if results:
                return results
            # FTS5가 CamelCase 합성어를 단일 토큰으로 처리해 0 결과일 수 있음
            # → LIKE 기반 부분 매칭으로 폴백
        return self._search_like(query, node_type, limit, mode)

    def _search_fts(self, query: str,
                    node_type: str | list[str] | None,
                    related: bool,
                    limit: int,
                    mode: str = "or") -> list[tuple[WikiNode, str, float]]:
        """FTS5 BM25 기반 검색."""
        conn = self._get_conn()
        escaped = _escape_fts(query, mode)

        params: list = [escaped]
        type_clause = ""
        if isinstance(node_type, list) and node_type:
            ph = ",".join("?" * len(node_type))
            type_clause = f" AND f.node_type IN ({ph})"
            params.extend(node_type)
        elif node_type:
            type_clause = " AND f.node_type = ?"
            params.append(node_type)
        params.append(limit)

        sql = (
            "SELECT f.node_id,"
            "       snippet(wiki_fts, 1, '**', '**', '...', 15) AS snip,"
            "       bm25(wiki_fts, 10.0, 1.0) AS rank"
            " FROM wiki_fts f"
            f" WHERE wiki_fts MATCH ?{type_clause}"
            " ORDER BY rank"
            " LIMIT ?"
        )
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS 쿼리 오류 → LIKE 폴백
            return self._search_like(query, node_type, limit, mode)

        results: list[tuple[WikiNode, str, float]] = []
        seen_ids: set[str] = set()

        for row in rows:
            node_id = row[0]
            snip = row[1] or ""
            rank = float(row[2] or 0.0)
            node = self.get(node_id)
            if node:
                results.append((node, snip, rank))
                seen_ids.add(node_id)

        # related=True: 1차 결과의 엣지 이웃 노드 추가
        if related and results:
            primary_ids = [r[0].id for r in results]
            related_pairs = self._expand_related(primary_ids, seen_ids)
            remaining = limit - len(results)
            for node, rel in related_pairs[:remaining]:
                results.append((node, f"[related via {rel}]", 0.0))

        return results

    def _search_like(self, query: str,
                     node_type: str | list[str] | None,
                     limit: int,
                     mode: str = "or") -> list[tuple[WikiNode, str, float]]:
        """LIKE 기반 부분 매칭 검색 (FTS 미지원 또는 FTS 0결과 폴백).
        mode: 'or' — 단어 중 하나, 'and' — 모든 단어, 'phrase' — 구문 매칭."""
        results: list[tuple[WikiNode, str, float]] = []
        words = [w.lower() for w in query.split() if w]
        if not words:
            words = [query.lower()]
        phrase = " ".join(words)  # phrase 모드용

        for node in self.list_nodes(node_type=node_type, limit=1000):
            title_lower = node.title.lower()
            # CamelCase 분리 버전도 함께 검사
            split_title = _split_camel(node.title).lower()

            if mode == "phrase":
                title_match = phrase in title_lower or phrase in split_title
            elif mode == "and":
                title_match = all(w in title_lower or w in split_title for w in words)
            else:  # "or"
                title_match = any(w in title_lower or w in split_title for w in words)

            if title_match:
                results.append((node, f"Title match: {node.title}", -1.0))
                if len(results) >= limit:
                    break
                continue

            md_path = self._wiki_dir / node.file_path
            try:
                # frontmatter 제거 후 본문만 검색 (type/source_fingerprint 등 키 오탐 방지)
                content = _strip_frontmatter(md_path.read_text(encoding="utf-8")).lower()
                if mode == "phrase":
                    idx = content.find(phrase)
                    if idx >= 0:
                        start = max(0, idx - 60)
                        end = min(len(content), idx + len(phrase) + 60)
                        snip = "..." + content[start:end].replace("\n", " ") + "..."
                        results.append((node, snip, -1.0))
                elif mode == "and":
                    if all(w in content for w in words):
                        idx = content.find(words[0])
                        start = max(0, idx - 60)
                        end = min(len(content), idx + len(words[0]) + 60)
                        snip = "..." + content[start:end].replace("\n", " ") + "..."
                        results.append((node, snip, -1.0))
                else:  # "or"
                    for w in words:
                        idx = content.find(w)
                        if idx >= 0:
                            start = max(0, idx - 60)
                            end = min(len(content), idx + len(w) + 60)
                            snip = "..." + content[start:end].replace("\n", " ") + "..."
                            results.append((node, snip, -1.0))
                            break
            except Exception:
                pass
            if len(results) >= limit:
                break

        return results[:limit]

    def _expand_related(self, primary_ids: list[str],
                        seen_ids: set[str]) -> list[tuple[WikiNode, str]]:
        """엣지 테이블에서 1홉 관련 노드 확장.
        wiki에 없는 타겟은 stub 노드로 반환 — 에이전트가 미분석 관계를 인지할 수 있도록."""
        if not primary_ids:
            return []
        conn = self._get_conn()
        ph = ",".join("?" * len(primary_ids))
        rows = conn.execute(
            f"SELECT target, relation FROM wiki_edges WHERE source IN ({ph})",
            primary_ids,
        ).fetchall()
        expanded: list[tuple[WikiNode, str]] = []
        for row in rows:
            target_id, relation = row[0], row[1]
            if target_id not in seen_ids:
                seen_ids.add(target_id)
                node = self.get(target_id)
                if node:
                    expanded.append((node, relation))
                else:
                    # 엣지 타겟이 wiki에 없을 때 stub으로 힌트 제공
                    parts = target_id.split(":", 1)
                    stub_type = parts[0] if len(parts) == 2 else "class"
                    stub_title = parts[1] if len(parts) == 2 else target_id
                    stub = WikiNode(
                        id=target_id,
                        type=stub_type,
                        title=stub_title,
                        file_path="",  # sentinel: 미분석 노드
                        source_fingerprint="",
                        created_at="",
                        updated_at="",
                    )
                    expanded.append((stub, f"{relation} (not yet analyzed)"))
        return expanded

    # ── Edges ──────────────────────────────────────────────────

    def upsert_edges(self, source_id: str, edges: list[WikiEdge]) -> None:
        """소스 노드의 엣지를 교체 저장 (DELETE + INSERT)."""
        if not edges:
            return
        conn = self._get_conn()
        conn.execute("DELETE FROM wiki_edges WHERE source = ?", (source_id,))
        conn.executemany(
            "INSERT OR IGNORE INTO wiki_edges (source, target, relation, weight) "
            "VALUES (?,?,?,?)",
            [(e.source, e.target, e.relation, e.weight) for e in edges],
        )
        conn.commit()

    def get_related(self, node_id: str,
                    relation: str | None = None,
                    depth: int = 1) -> list[tuple[str, str]]:
        """BFS로 관련 노드 탐색. 반환: [(target_id, relation), ...]"""
        conn = self._get_conn()
        visited: set[str] = {node_id}
        frontier: list[str] = [node_id]
        results: list[tuple[str, str]] = []

        for _ in range(depth):
            if not frontier:
                break
            ph = ",".join("?" * len(frontier))
            sql = (
                f"SELECT target, relation FROM wiki_edges WHERE source IN ({ph})"
            )
            params: list = frontier[:]
            if relation:
                sql += " AND relation = ?"
                params.append(relation)
            rows = conn.execute(sql, params).fetchall()
            new_frontier: list[str] = []
            for row in rows:
                target, rel = row[0], row[1]
                if target not in visited:
                    visited.add(target)
                    new_frontier.append(target)
                    results.append((target, rel))
            frontier = new_frontier

        return results

    # ── Log ────────────────────────────────────────────────────

    def append_log(self, action: str, description: str) -> None:
        log_path = self._wiki_dir / "log.md"
        today = date.today().strftime("%Y-%m-%d")
        entry = f"\n## [{today}] {action} | {description}\n"
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass


# ── 공개 헬퍼 ─────────────────────────────────────────────────

def make_node_id(node_type: str, name: str) -> str:
    """위키 노드 ID 생성. 예: make_node_id('class', 'PlayerCharacter') → 'class:PlayerCharacter'"""
    return f"{node_type}:{name}"


def make_file_path(node_type: str, name: str) -> str:
    """위키 파일 경로 생성. 예: 'classes/PlayerCharacter.md'"""
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
    type_to_dir = {
        "class":        "classes",
        "asset":        "assets",
        "system":       "systems",
        "pattern":      "patterns",
        "conversation": "conversations",
    }
    dir_name = type_to_dir.get(node_type, node_type + "s")
    return f"{dir_name}/{safe_name}.md"


# ── 내부 헬퍼 ─────────────────────────────────────────────────

def _row_to_node(row: sqlite3.Row) -> WikiNode:
    d = dict(row)
    return WikiNode(
        id=d["id"],
        type=d["type"],
        title=d["title"],
        file_path=d["file_path"],
        source_fingerprint=d.get("source_fingerprint", ""),
        created_at=d.get("created_at", ""),
        updated_at=d.get("updated_at", ""),
        stale=bool(d.get("stale", 0)),
        meta=json.loads(d.get("meta") or "{}"),
    )


def _strip_frontmatter(content: str) -> str:
    """YAML frontmatter (--- ... ---) 제거 후 본문 반환."""
    if not content.startswith("---"):
        return content
    end = content.find("\n---", 4)
    if end < 0:
        return content
    return content[end + 4:].lstrip("\n")


def _split_camel(name: str) -> str:
    """CamelCase 식별자를 공백 분리 단어로 변환.
    예: ULyraGameplayAbility → U Lyra Gameplay Ability
    """
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    return s


_RE_CAMELCASE = re.compile(r'\b([A-Z]+[a-z]+(?:[A-Z][a-z]*)+)\b')


def _split_camel_in_text(text: str) -> str:
    """본문 내 CamelCase 식별자를 원본 + 분리형으로 보강.

    예: "Uses AbilitySystemComponent" → "Uses AbilitySystemComponent Ability System Component"
    FTS5가 합성어(AbilitySystemComponent)와 분리 단어(ability, system, component) 모두 매칭 가능.
    단일 대문자어(GAS, AI, BP)나 단일 단어(Component)는 변환하지 않음.
    """
    def _augment(m: re.Match) -> str:
        original = m.group(0)
        split = _split_camel(original)
        if split == original:
            return original
        return original + " " + split

    return _RE_CAMELCASE.sub(_augment, text)


def _escape_fts(query: str, mode: str = "or") -> str:
    """FTS5 쿼리 이스케이프.
    mode='or'    — CamelCase 분리 후 OR 토큰 결합 (기본)
    mode='and'   — CamelCase 분리 후 AND 토큰 결합
    mode='phrase'— CamelCase 분리 없이 원문 구문 매칭

    예 (or):    'GAS ability zombie'    → '"GAS" OR "ability" OR "zombie"'
    예 (and):   'GAS ability zombie'    → '"GAS" AND "ability" AND "zombie"'
    예 (phrase):'GAS ability zombie'    → '"GAS ability zombie"'
    예 (or):    'GameplayAbility'       → '"Gameplay" OR "Ability"'
    예 (or):    'Lyra*'                 → '"Lyra"*'
    """
    if mode == "phrase":
        # phrase: CamelCase 분리 없이 원문 그대로 구문 매칭
        raw_words = re.sub(r"[^\w\s]", "", query).split()
        return '"' + " ".join(raw_words) + '"' if raw_words else f'"{query}"'

    # or / and: CamelCase 분리 + 토큰화
    # * 는 prefix 연산자이므로 보존, 그 외 특수문자 제거
    words = re.sub(r"[^\w\s*]", "", query).split()
    if not words:
        return f'"{query}"'

    expanded: list[str] = []
    for w in words:
        prefix = w.endswith("*")
        clean = w.rstrip("*")
        if not clean:
            continue
        # CamelCase 분리 → 인덱스 시 적용한 _split_camel과 대칭
        parts = _split_camel(clean).split()
        for part in parts:
            token = f'"{part}"' + ("*" if prefix else "")
            expanded.append(token)

    joiner = " AND " if mode == "and" else " OR "
    return joiner.join(expanded) if expanded else f'"{query}"'


def _parse_node_from_md(content: str, md_path: Path,
                         wiki_dir: Path) -> WikiNode | None:
    """YAML frontmatter에서 WikiNode 재구성. rebuild_from_files()용."""
    try:
        if not content.startswith("---"):
            return None
        end = content.find("\n---", 4)
        if end < 0:
            return None
        frontmatter = content[3:end]

        def _get(key: str, default: str = "") -> str:
            m = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
            return m.group(1).strip().strip("\"'") if m else default

        node_type  = _get("type")
        title      = _get("title")
        if not (node_type and title):
            return None
        # id 필드가 없으면 type:title 형식으로 구성 (구형 frontmatter 호환)
        node_id = _get("id") or f"{node_type}:{title}"

        rel_path = str(md_path.relative_to(wiki_dir)).replace("\\", "/")
        return WikiNode(
            id=node_id,
            type=node_type,
            title=title,
            file_path=rel_path,
            source_fingerprint=_get("source_fingerprint", ""),
            created_at=_get("created_at") or _get("created", ""),
            updated_at=_get("updated_at") or _get("updated", ""),
            stale=_get("stale", "false").lower() == "true",
            meta={},
        )
    except Exception:
        return None
