"""
gdep.wiki.staleness
위키 노드의 stale 여부를 판단한다.

기존 gdep의 fingerprint 시스템(_agents_fingerprint)과 동일한 방식을 사용:
  - 소스 파일의 mtime MD5 fingerprint와 노드의 source_fingerprint 비교
  - 불일치 시 stale로 판단 → 재분석 필요
"""
from __future__ import annotations

from pathlib import Path


def get_project_fingerprint(project_path: str) -> str:
    """프로젝트 소스 파일 fingerprint 계산 (init_context._agents_fingerprint 재사용)."""
    try:
        from gdep.detector import detect
        from gdep.init_context import _agents_fingerprint
        profile = detect(project_path)
        return _agents_fingerprint(profile)
    except Exception:
        return ""


def is_node_stale(node_fingerprint: str, current_fingerprint: str) -> bool:
    """노드의 fingerprint와 현재 소스 fingerprint를 비교해 stale 여부 반환."""
    if not node_fingerprint or not current_fingerprint:
        return True
    return node_fingerprint != current_fingerprint


def build_class_fingerprint_map(project_path: str) -> dict[str, str]:
    """
    src_path 아래 소스 파일을 한 번만 walk해서 {stem_lower: fingerprint} 맵 반환.
    wiki_list에서 N개 노드를 O(1) 조회할 수 있도록 일괄 계산에 사용.

    .h / .cpp 같은 stem이 여러 파일에 존재하는 경우(UE5 등) 전부 수집 후
    경로 정렬 → combined hash를 사용해 get_class_fingerprint()와 일치시킨다.
    """
    import hashlib
    import os

    try:
        from gdep.detector import detect
        from gdep.runner import _src

        profile = detect(project_path)
        src_path = _src(profile)
        # Phase 1: stem별 파일 목록 수집 (덮어쓰지 않음)
        stem_files: dict[str, list[tuple[str, int]]] = {}
        extensions = {".cs", ".h", ".cpp"}

        for root, _, files in os.walk(src_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext not in extensions:
                    continue
                stem = os.path.splitext(f)[0].lower()
                fpath = os.path.join(root, f)
                try:
                    stat = os.stat(fpath)
                    stem_files.setdefault(stem, []).append((fpath, stat.st_mtime_ns))
                except Exception:
                    pass

        # Phase 2: stem별 combined fingerprint 계산
        result: dict[str, str] = {}
        for stem, entries in stem_files.items():
            entries.sort(key=lambda x: x[0])  # 경로 정렬 → 결정론적 순서
            combined = "|".join(f"{fp}:{mt}" for fp, mt in entries)
            result[stem] = hashlib.md5(combined.encode()).hexdigest()

        return result
    except Exception:
        return {}


def get_class_fingerprint(project_path: str, class_name: str) -> str:
    """
    특정 클래스 파일의 fingerprint 계산.
    .h / .cpp 양쪽이 존재하는 경우 전부 수집 후 경로 정렬 → combined hash.
    build_class_fingerprint_map()과 동일한 방식으로 계산해 일관성을 보장한다.
    파일을 특정할 수 없으면 프로젝트 전체 fingerprint를 사용한다.
    """
    try:
        from gdep.detector import detect
        from gdep.runner import _src
        import hashlib
        import os

        profile = detect(project_path)
        src_path = _src(profile)
        class_lower = class_name.lower()

        # 매칭되는 파일 전부 수집 (첫 번째 매칭에서 즉시 반환하지 않음)
        matched: list[tuple[str, int]] = []
        for root, _, files in os.walk(src_path):
            for f in files:
                name_lower = f.lower()
                if (name_lower == f"{class_lower}.cs" or
                        name_lower == f"{class_lower}.h" or
                        name_lower == f"{class_lower}.cpp"):
                    fpath = os.path.join(root, f)
                    try:
                        stat = os.stat(fpath)
                        matched.append((fpath, stat.st_mtime_ns))
                    except Exception:
                        pass

        if matched:
            matched.sort(key=lambda x: x[0])  # 경로 정렬 → 결정론적 순서
            combined = "|".join(f"{fp}:{mt}" for fp, mt in matched)
            return hashlib.md5(combined.encode()).hexdigest()

    except Exception:
        pass

    # 파일 특정 불가 → 전체 fingerprint 사용
    return get_project_fingerprint(project_path)
