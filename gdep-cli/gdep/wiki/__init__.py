"""
gdep.wiki
게임 프로젝트 분석 결과를 마크다운 위키 노드로 저장/조회하는 레이어.

구조:
  .gdep/wiki/
  ├── OVERVIEW.md          - 프로젝트 분석 개요 (init_context.py 생성)
  ├── index.md             - 전체 노드 목차
  ├── log.md               - 변경 타임라인
  ├── .wiki_index.db       - SQLite (노드 메타 + FTS5 + 엣지) — 파생 인덱스
  ├── classes/             - 클래스별 노드
  ├── assets/              - 에셋별 노드
  ├── systems/             - 시스템 종합 노드
  ├── patterns/            - 디자인 패턴 노드
  └── conversations/       - Agent 대화 요약 노드

참고: .wiki_meta.json은 SQLite로 마이그레이션됨.
      DB 손상 시 WikiStore.rebuild_from_files()로 .md 파일에서 복구 가능.
"""

from .store import WikiStore
from .models import WikiNode, WikiEdge, EDGE_DEPENDS_ON, EDGE_REFERENCED_BY, EDGE_INHERITS, EDGE_USES_ASSET
from .edge_extractor import extract_edges

__all__ = [
    "WikiStore", "WikiNode", "WikiEdge",
    "EDGE_DEPENDS_ON", "EDGE_REFERENCED_BY", "EDGE_INHERITS", "EDGE_USES_ASSET",
    "extract_edges",
]
