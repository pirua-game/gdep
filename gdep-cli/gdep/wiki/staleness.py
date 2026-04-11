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


def get_class_fingerprint(project_path: str, class_name: str) -> str:
    """
    특정 클래스 파일의 fingerprint 계산.
    파일을 특정할 수 없으면 프로젝트 전체 fingerprint를 사용한다.
    """
    try:
        from gdep.detector import detect
        from gdep.runner import _cs_fingerprint, _src
        import hashlib
        import os

        profile = detect(project_path)
        src_path = _src(profile)

        # 클래스 파일 찾기
        for root, _, files in os.walk(src_path):
            for f in files:
                if f.lower() == f"{class_name.lower()}.cs" or \
                   f.lower() == f"{class_name.lower()}.h" or \
                   f.lower() == f"{class_name.lower()}.cpp":
                    fpath = os.path.join(root, f)
                    try:
                        stat = os.stat(fpath)
                        h = hashlib.md5(f"{fpath}:{stat.st_mtime_ns}".encode())
                        return h.hexdigest()
                    except Exception:
                        pass
    except Exception:
        pass

    # 파일 특정 불가 → 전체 fingerprint 사용
    return get_project_fingerprint(project_path)
