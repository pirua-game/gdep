"""
gdep.wiki.models
WikiNode / WikiEdge 데이터 모델.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Edge relation constants ────────────────────────────────────
EDGE_DEPENDS_ON    = "depends_on"
EDGE_REFERENCED_BY = "referenced_by"
EDGE_INHERITS      = "inherits"
EDGE_USES_ASSET    = "uses_asset"


@dataclass
class WikiNode:
    """위키 노드 하나를 나타낸다.

    id 형식:
      'class:PlayerCharacter'
      'asset:BP_GA_BasicAttack'
      'system:gas'
      'pattern:Singleton'
      'conversation:2026-04-11-session'
    """
    id: str                        # 'class:PlayerCharacter'
    type: str                      # 'class' | 'asset' | 'system' | 'pattern' | 'conversation'
    title: str                     # 사람이 읽기 좋은 이름
    file_path: str                 # wiki/ 디렉토리 내 상대 경로 (예: 'classes/PlayerCharacter.md')
    source_fingerprint: str        # 이 노드를 만든 소스의 fingerprint (stale 감지용)
    created_at: str                # ISO 날짜 'YYYY-MM-DD'
    updated_at: str                # ISO 날짜 'YYYY-MM-DD'
    stale: bool = False

    # 타입별 추가 메타데이터 (직렬화용)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "file_path": self.file_path,
            "source_fingerprint": self.source_fingerprint,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "stale": self.stale,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WikiNode":
        return cls(
            id=d["id"],
            type=d["type"],
            title=d["title"],
            file_path=d["file_path"],
            source_fingerprint=d.get("source_fingerprint", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            stale=d.get("stale", False),
            meta=d.get("meta", {}),
        )


@dataclass
class WikiEdge:
    """위키 노드 간 의존성 엣지.

    source / target: 'class:BattleCore', 'asset:BP_GA_BasicAttack' 등 위키 노드 ID.
    relation: EDGE_* 상수 중 하나.
    """
    source: str      # 'class:BattleCore'
    target: str      # 'class:PlayingCard'
    relation: str    # 'depends_on' | 'referenced_by' | 'inherits' | 'uses_asset'
    weight: float = 1.0
