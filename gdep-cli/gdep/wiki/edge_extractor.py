"""
gdep.wiki.edge_extractor
분석 결과 마크다운에서 의존성 엣지를 추출한다.

지원 섹션/패턴:
  - "── Behavioral Dependencies" 섹션  → depends_on  (• ClassName 불릿)
  - "── External References" 섹션      → depends_on  (테이블 행)
  - "── Referenced By" 섹션           → referenced_by
  - "Inheritance: A, B, C" 한 줄      → inherits    (콤마 구분)
  - "Inheritance chain: A → B → C"    → inherits    (화살표 구분)
  - UPROPERTY 타입 내 클래스           → depends_on
"""
from __future__ import annotations

import re

from .models import WikiEdge, EDGE_DEPENDS_ON, EDGE_REFERENCED_BY, EDGE_INHERITS


def extract_edges(node_id: str, content: str) -> list[WikiEdge]:
    """분석 결과 텍스트에서 WikiEdge 목록 추출.

    Args:
        node_id: 소스 노드 ID (예: 'class:BattleCore')
        content: explore_class_semantics 등 분석 도구의 결과 문자열

    Returns:
        WikiEdge 목록
    """
    edges: list[WikiEdge] = []
    _extract_behavioral_deps(node_id, content, edges)
    _extract_external_refs(node_id, content, edges)
    _extract_referenced_by(node_id, content, edges)
    _extract_inheritance(node_id, content, edges)
    _extract_uproperty_types(node_id, content, edges)
    # 중복 제거 (source+target+relation 기준)
    seen: set[tuple[str, str, str]] = set()
    deduped: list[WikiEdge] = []
    for e in edges:
        key = (e.source, e.target, e.relation)
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


# ── 섹션 패턴 ─────────────────────────────────────────────────
# ^[ \t]*─+ : 줄 앞 공백 허용 (MULTILINE)

# "── Behavioral Dependencies (--deep, N items) ──" 섹션
# 불릿: "  • ULyraAbilitySystemComponent"
_DEP_SECTION_PAT = re.compile(
    r'^[ \t]*─+[ \t]*Behavioral Dependencies[^\n]*\n(.*?)(?=^[ \t]*─+|^##|\Z)',
    re.DOTALL | re.MULTILINE,
)
_BULLET_CLS_PAT = re.compile(
    r'^[ \t]*[•·*\-]\s+`?([A-Z][A-Za-z0-9_]+)`?',
    re.MULTILINE,
)

# "── External References (out-degree...)" 섹션 (구형 포맷)
_EXT_SECTION_PAT = re.compile(
    r'^[ \t]*─+[ \t]*External References[^\n]*\n(.*?)(?=^[ \t]*─+|\Z)',
    re.DOTALL | re.MULTILINE,
)
# "── Referenced By (in-degree: N)" 섹션
_REF_BY_SECTION_PAT = re.compile(
    r'^[ \t]*─+[ \t]*Referenced By[^\n]*\n(.*?)(?=^[ \t]*─+|\nInheritance|\Z)',
    re.DOTALL | re.MULTILINE,
)

# "Inheritance: ACharacter, IAbilitySystemInterface" (콤마 구분)
# OR "Inheritance chain: A → B → C" (화살표 구분)
_INHERIT_LINE_PAT = re.compile(
    r'Inheritance(?:\s+chain)?:\s*(.+)'
)

# UPROPERTY 섹션에서 TObjectPtr<ClassName> 패턴
# "TObjectPtr<ULyraAbilitySystemComponent> FieldName"
_UPROP_TYPE_PAT = re.compile(
    r'TObjectPtr<([A-Z][A-Za-z0-9_]+)>'
    r'|TSubclassOf<([A-Z][A-Za-z0-9_]+)>'
    r'|TArray<TObjectPtr<([A-Z][A-Za-z0-9_]+)>>'
)

# 마크다운 테이블 첫 번째 열에서 클래스 이름 추출
_TABLE_ROW_PAT = re.compile(r'^\|\s*`?([A-Z][A-Za-z0-9_]+)`?\s*\|', re.MULTILINE)

# "ClassName1 · ClassName2 ..." 형태
_DOT_SEP_CLS_PAT = re.compile(r'`?([A-Z][A-Za-z0-9_]+)`?')

# 제외할 일반 단어 (마크다운 / 테이블 헤더 등)
_EXCLUDE_WORDS: frozenset[str] = frozenset({
    "Type", "Name", "Value", "None", "True", "False",
    "Class", "Score", "Count", "Total", "File", "Path",
    "Module", "Source", "Target", "Method", "Field",
    "Param", "Return", "Result", "Error", "Note",
    "Summary", "Details", "Description", "Blueprint",
    "Override", "Event", "Confidence", "High", "Low",
    "UPROPERTY", "UFUNCTION", "UCLASS", "Lifecycle",
    "General", "Behavioral", "Dependencies", "Methods",
})


# ── 파서 ──────────────────────────────────────────────────────

def _extract_behavioral_deps(node_id: str, content: str,
                              edges: list[WikiEdge]) -> None:
    """Behavioral Dependencies 섹션 → depends_on 엣지 (불릿 형식)."""
    for m in _DEP_SECTION_PAT.finditer(content):
        section = m.group(1)
        for bm in _BULLET_CLS_PAT.finditer(section):
            target_name = bm.group(1).strip()
            if _is_valid_class(target_name):
                target_id = f"class:{target_name}"
                if target_id != node_id:
                    edges.append(WikiEdge(
                        source=node_id,
                        target=target_id,
                        relation=EDGE_DEPENDS_ON,
                    ))


def _extract_external_refs(node_id: str, content: str,
                            edges: list[WikiEdge]) -> None:
    """External References 섹션 → depends_on 엣지 (테이블 형식, 구형 포맷)."""
    for m in _EXT_SECTION_PAT.finditer(content):
        section = m.group(1)
        for row_m in _TABLE_ROW_PAT.finditer(section):
            target_name = row_m.group(1).strip()
            if _is_valid_class(target_name):
                target_id = f"class:{target_name}"
                if target_id != node_id:
                    edges.append(WikiEdge(
                        source=node_id,
                        target=target_id,
                        relation=EDGE_DEPENDS_ON,
                    ))


def _extract_referenced_by(node_id: str, content: str,
                            edges: list[WikiEdge]) -> None:
    """Referenced By 섹션 → referenced_by 엣지."""
    for m in _REF_BY_SECTION_PAT.finditer(content):
        section = m.group(1)
        for cls_m in _DOT_SEP_CLS_PAT.finditer(section):
            target_name = cls_m.group(1).strip()
            if _is_valid_class(target_name):
                target_id = f"class:{target_name}"
                if target_id != node_id:
                    edges.append(WikiEdge(
                        source=node_id,
                        target=target_id,
                        relation=EDGE_REFERENCED_BY,
                    ))


def _extract_inheritance(node_id: str, content: str,
                          edges: list[WikiEdge]) -> None:
    """Inheritance 한 줄에서 부모 클래스 → inherits 엣지.

    형식 1 (콤마 구분): Inheritance: ACharacter, IAbilitySystemInterface
    형식 2 (화살표 구분): Inheritance chain: A → B → C
    """
    for m in _INHERIT_LINE_PAT.finditer(content):
        chain_str = m.group(1)
        # 화살표 구분인지 콤마 구분인지 판단
        if '→' in chain_str or '->' in chain_str:
            parts = [p.strip() for p in re.split(r'→|->', chain_str)]
            parents = parts[1:]  # 첫 번째는 현재 클래스
        else:
            parts = [p.strip() for p in chain_str.split(',')]
            parents = parts  # 전부 부모 (UE5 Inheritance: 형식)
        for parent_raw in parents:
            parent_name = re.sub(r'[^A-Za-z0-9_]', '', parent_raw)
            if _is_valid_class(parent_name):
                parent_id = f"class:{parent_name}"
                if parent_id != node_id:
                    edges.append(WikiEdge(
                        source=node_id,
                        target=parent_id,
                        relation=EDGE_INHERITS,
                    ))


def _extract_uproperty_types(node_id: str, content: str,
                              edges: list[WikiEdge]) -> None:
    """UPROPERTY 섹션의 TObjectPtr<T>, TSubclassOf<T> → depends_on 엣지."""
    for m in _UPROP_TYPE_PAT.finditer(content):
        target_name = m.group(1) or m.group(2) or m.group(3) or ""
        if _is_valid_class(target_name):
            target_id = f"class:{target_name}"
            if target_id != node_id:
                edges.append(WikiEdge(
                    source=node_id,
                    target=target_id,
                    relation=EDGE_DEPENDS_ON,
                ))


def _is_valid_class(name: str) -> bool:
    """유효한 클래스 이름 (C++ / C# 컨벤션) 여부."""
    if not name or len(name) < 2 or len(name) > 100:
        return False
    if name in _EXCLUDE_WORDS:
        return False
    return bool(re.match(r'^[A-Z][A-Za-z0-9_]+$', name))
