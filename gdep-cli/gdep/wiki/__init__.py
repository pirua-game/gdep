"""
gdep.wiki
게임 프로젝트 분석 결과를 마크다운 위키 노드로 저장/조회하는 레이어.

구조:
  .gdep/wiki/
  ├── OVERVIEW.md          - 프로젝트 분석 개요 (init_context.py 생성)
  ├── index.md             - 전체 노드 목차
  ├── log.md               - 변경 타임라인
  ├── .wiki_meta.json      - 노드 인덱스 + fingerprint
  ├── classes/             - 클래스별 노드
  ├── assets/              - 에셋별 노드
  ├── systems/             - 시스템 종합 노드
  ├── patterns/            - 디자인 패턴 노드
  └── conversations/       - Agent 대화 요약 노드
"""

from .store import WikiStore
from .models import WikiNode

__all__ = ["WikiStore", "WikiNode"]
