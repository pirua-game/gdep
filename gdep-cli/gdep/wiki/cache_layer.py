"""
gdep.wiki.cache_layer
MCP 도구용 wiki-first 캐시 래퍼.

사용 패턴:
    result = wiki_cached_class(
        project_path="...",
        class_name="PlayerCharacter",
        analyzer_fn=runner_describe_fn,
    )

흐름:
  1. WikiStore에서 노드 조회
  2. fresh 노드가 있으면 → 위키 내용 바로 반환
  3. stale / 없으면 → analyzer_fn() 실행 → 위키에 저장 → 반환
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from .models import WikiNode
from .store import WikiStore, make_node_id, make_file_path
from .node_writer import make_class_page, make_asset_page, make_system_page, make_pattern_page
from .staleness import is_node_stale, get_class_fingerprint, get_project_fingerprint
from .edge_extractor import extract_edges
from .index import rebuild_index
from pathlib import Path


def _wiki_dir(project_path: str) -> Path:
    from gdep.detector import detect
    profile = detect(project_path)
    return Path(profile.root) / ".gdep" / "wiki"


def wiki_cached_class(project_path: str, class_name: str,
                      analyzer_fn: Callable[[], str],
                      engine: str = "",
                      refresh: bool = False) -> str:
    """
    클래스 분석 결과를 위키에서 먼저 확인하고, stale이면 재분석 후 저장.

    Args:
        project_path: 프로젝트 경로
        class_name:   클래스 이름
        analyzer_fn:  실제 분석 함수 (인자 없이 호출, str 반환)
        engine:       엔진 이름 (frontmatter용)
        refresh:      True이면 위키 캐시를 무시하고 재분석 (결과는 위키에 다시 저장)

    Returns:
        분석 결과 문자열 (위키에서 읽거나 새로 생성)
    """
    store = WikiStore(project_path)
    node_id = make_node_id("class", class_name)
    node = store.get(node_id)

    current_fp = get_class_fingerprint(project_path, class_name)

    was_cached = (not refresh and node
                  and not node.stale
                  and not is_node_stale(node.source_fingerprint, current_fp))

    if was_cached:
        # fresh → 위키 본문 반환 (frontmatter 제거됨)
        cached = store.read_content(node)
        return cached + "\n\n> *[wiki] Returned from wiki cache. Run with refresh=True to force re-analysis.*"

    # stale 또는 refresh=True → 재분석 실행
    result = analyzer_fn()

    # 위키에 저장
    today = date.today().strftime("%Y-%m-%d")
    file_path = make_file_path("class", class_name)
    page_content = make_class_page(class_name, result, current_fp, engine)

    new_node = WikiNode(
        id=node_id,
        type="class",
        title=class_name,
        file_path=file_path,
        source_fingerprint=current_fp,
        created_at=node.created_at if node else today,
        updated_at=today,
        stale=False,
    )
    store.upsert(new_node, page_content)
    store.append_log("analyze", f"class:{class_name}")

    # 의존성 엣지 추출 및 저장 (분석 결과에서 References/Referenced By 파싱)
    try:
        edges = extract_edges(node_id, result)
        if edges:
            store.upsert_edges(node_id, edges)
    except Exception:
        pass

    # index.md 갱신
    try:
        rebuild_index(_wiki_dir(project_path))
    except Exception:
        pass

    footer = "\n\n> *[wiki] Re-analyzed and wiki updated.*" if node else "\n\n> *[wiki] Analyzed and saved to wiki.*"
    return result + footer


def wiki_cached_asset(project_path: str, asset_name: str,
                      analyzer_fn: Callable[[], str],
                      asset_kind: str = "", engine: str = "") -> str:
    """에셋 분석 결과를 위키에서 먼저 확인하고, stale이면 재분석 후 저장."""
    store = WikiStore(project_path)
    node_id = make_node_id("asset", asset_name)
    node = store.get(node_id)

    current_fp = get_project_fingerprint(project_path)

    if node and not node.stale and not is_node_stale(node.source_fingerprint, current_fp):
        cached = store.read_content(node)
        return cached + "\n\n> *[wiki] Returned from wiki cache. Run with refresh=True to force re-analysis.*"

    result = analyzer_fn()

    today = date.today().strftime("%Y-%m-%d")
    file_path = make_file_path("asset", asset_name)
    page_content = make_asset_page(asset_name, result, current_fp, asset_kind, engine)

    new_node = WikiNode(
        id=node_id,
        type="asset",
        title=asset_name,
        file_path=file_path,
        source_fingerprint=current_fp,
        created_at=node.created_at if node else today,
        updated_at=today,
        stale=False,
    )
    store.upsert(new_node, page_content)
    store.append_log("analyze", f"asset:{asset_name}")

    # 에셋 분석 결과에서도 엣지 추출 시도
    try:
        edges = extract_edges(node_id, result)
        if edges:
            store.upsert_edges(node_id, edges)
    except Exception:
        pass

    try:
        rebuild_index(_wiki_dir(project_path))
    except Exception:
        pass

    footer = "\n\n> *[wiki] Re-analyzed and wiki updated.*" if node else "\n\n> *[wiki] Analyzed and saved to wiki.*"
    return result + footer


def wiki_cached_system(project_path: str, system_name: str,
                       analyzer_fn: Callable[[], str],
                       engine: str = "") -> str:
    """엔진 시스템(GAS, BT 등) 분석 결과를 위키에서 먼저 확인하고, stale이면 재분석 후 저장."""
    store = WikiStore(project_path)
    node_id = make_node_id("system", system_name)
    node = store.get(node_id)

    current_fp = get_project_fingerprint(project_path)

    if node and not node.stale and not is_node_stale(node.source_fingerprint, current_fp):
        cached = store.read_content(node)
        return cached + "\n\n> *[wiki] Returned from wiki cache. Run with refresh=True to force re-analysis.*"

    result = analyzer_fn()

    today = date.today().strftime("%Y-%m-%d")
    file_path = make_file_path("system", system_name)
    page_content = make_system_page(system_name, result, current_fp, engine)

    new_node = WikiNode(
        id=node_id,
        type="system",
        title=system_name,
        file_path=file_path,
        source_fingerprint=current_fp,
        created_at=node.created_at if node else today,
        updated_at=today,
        stale=False,
    )
    store.upsert(new_node, page_content)
    store.append_log("analyze", f"system:{system_name}")

    try:
        edges = extract_edges(node_id, result)
        if edges:
            store.upsert_edges(node_id, edges)
    except Exception:
        pass

    try:
        rebuild_index(_wiki_dir(project_path))
    except Exception:
        pass

    footer = "\n\n> *[wiki] Re-analyzed and wiki updated.*" if node else "\n\n> *[wiki] Analyzed and saved to wiki.*"
    return result + footer
