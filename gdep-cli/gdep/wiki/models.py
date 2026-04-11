"""
gdep.wiki.models
WikiNode 데이터 모델.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
