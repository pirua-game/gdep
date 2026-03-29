"""
gdep-mcp/tools/query_project_api.py

High-level tool: 프로젝트 코드 API 레퍼런스 검색.
파싱된 클래스/메서드/프로퍼티를 검색 가능한 API 인덱스로 변환하여
관련도 점수 기반으로 결과를 반환한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep.confidence import ConfidenceTier, confidence_footer
from gdep.detector import ProjectKind, detect


def run(project_path: str, query: str,
        scope: str = "all",
        max_results: int = 20) -> str:
    """
    Search the project's parsed code as an API reference.

    Searches class names, method names, property names, and parameter types
    across all parsed source files. Returns ranked results with signatures.

    Use this tool to:
    - Find all methods related to "Health" or "Damage" in the project
    - Look up a class's method signatures without reading the full source
    - Find all classes that have a specific property type
    - Quickly discover project APIs before writing integration code

    Note: Searches *project code only* (not engine source). For engine API
    documentation, ask the AI agent directly.

    Args:
        project_path: Absolute path to Scripts/Source folder.
        query:        Search term. E.g. "Health", "Attack", "Save", "Inventory"
        scope:        "all" (default), "classes", "methods", or "properties"
        max_results:  Maximum results to return (default 20). Pass 0 for unlimited.

    Returns:
        Ranked list of matching API entries with signatures and file locations.
    """
    if not query or not query.strip():
        return "[query_project_api] Error: query must not be empty."

    try:
        profile = detect(project_path)
        src = str(profile.source_dirs[0]) if profile.source_dirs else str(profile.root)

        if profile.kind == ProjectKind.UNREAL:
            return _search_cpp(src, query, scope, max_results, is_ue5=True)
        elif profile.kind == ProjectKind.CPP:
            return _search_cpp(src, query, scope, max_results, is_ue5=False)
        elif profile.kind in (ProjectKind.UNITY, ProjectKind.DOTNET):
            return _search_cs(src, query, scope, max_results, profile)
        else:
            return f"[query_project_api] Not supported for {profile.display} projects."

    except Exception as e:
        return f"[query_project_api] Error: {e}"


def _score(query: str, text: str) -> int:
    """Compute relevance score. Higher is better."""
    q = query.lower()
    t = text.lower()
    if t == q:
        return 100  # Exact match
    if t.startswith(q):
        return 80
    if q in t:
        return 60 + (10 if len(q) > 3 else 0)
    return 0


def _categorize_ue5(class_name: str) -> str:
    """Categorize UE5 class by prefix convention."""
    if not class_name:
        return ""
    if class_name.startswith('A'):
        return "Actor"
    if class_name.startswith('U'):
        return "Object"
    if class_name.startswith('F'):
        return "Struct"
    if class_name.startswith('E'):
        return "Enum"
    if class_name.startswith('I'):
        return "Interface"
    return ""


def _search_cpp(src: str, query: str, scope: str,
                max_results: int, is_ue5: bool) -> str:
    """Search C++/UE5 parsed classes/methods/properties."""
    if is_ue5:
        from gdep.ue5_runner import _get_project
    else:
        from gdep.cpp_runner import _get_project
    proj = _get_project(src)
    all_items = {**proj.classes, **proj.structs, **proj.enums}

    results: list[tuple[int, str]] = []  # (score, formatted_line)

    for cls_name, cls in all_items.items():
        # Search classes
        if scope in ("all", "classes"):
            s = _score(query, cls_name)
            if s > 0:
                cat = _categorize_ue5(cls_name) if is_ue5 else cls.kind
                bases = f" : {', '.join(cls.bases)}" if cls.bases else ""
                file_name = Path(cls.source_file).name if cls.source_file else ""
                results.append((s, f"[{cat}] {cls_name}{bases}  ({file_name})"))

        # Search methods
        if scope in ("all", "methods"):
            for func in getattr(cls, 'functions', []):
                s = _score(query, func.name)
                if s == 0:
                    # Also search in return type and params
                    s = max(_score(query, func.return_type),
                            max((_score(query, p) for p in func.params), default=0))
                    if s > 0:
                        s = s // 2  # Lower priority for type/param matches
                if s > 0:
                    params_str = ", ".join(func.params[:4])
                    if len(func.params) > 4:
                        params_str += ", ..."
                    virt = "virtual " if getattr(func, 'is_virtual', False) else ""
                    results.append((s, f"  {virt}{func.return_type} {cls_name}::{func.name}({params_str})"))

        # Search properties
        if scope in ("all", "properties"):
            for prop in getattr(cls, 'properties', []):
                s = _score(query, prop.name)
                if s == 0:
                    s = _score(query, prop.type_) // 2
                if s > 0:
                    results.append((s, f"  {prop.type_} {cls_name}::{prop.name}"))

    # Sort by score (descending), then alphabetically
    results.sort(key=lambda x: (-x[0], x[1]))
    limit = max_results if max_results > 0 else len(results)
    shown = results[:limit]

    if not shown:
        return (f"No API entries matching '{query}' found in project.\n"
                f"(Searched {len(all_items)} classes)"
                + confidence_footer(ConfidenceTier.HIGH, "source parsing"))

    lines = [
        f"## API Search: \"{query}\" ({len(results)} matches, showing {len(shown)})",
        "",
    ]
    for score, text in shown:
        lines.append(text)

    if len(results) > limit:
        lines.append(f"\n... {len(results) - limit} more results omitted"
                     f" (use max_results=0 to see all)")

    return "\n".join(lines) + confidence_footer(ConfidenceTier.HIGH, "source parsing")


def _search_cs(src: str, query: str, scope: str,
               max_results: int, profile) -> str:
    """Search C# parsed classes/methods using gdep.exe describe."""
    from gdep import runner

    # Use scan to get class list first
    scan_result = runner.scan(profile, fmt="json")
    if not scan_result.ok or not scan_result.data:
        return f"Failed to scan project: {scan_result.error_message}"

    coupling = scan_result.data.get("coupling", [])
    class_names = [c["name"] for c in coupling]

    results: list[tuple[int, str]] = []
    q = query.lower()

    # Search class names
    if scope in ("all", "classes"):
        for cls_info in coupling:
            name = cls_info["name"]
            s = _score(query, name)
            if s > 0:
                file_name = Path(cls_info.get("file", "")).name if cls_info.get("file") else ""
                score_val = cls_info.get("score", 0)
                results.append((s, f"[class] {name}  (coupling: {score_val}, {file_name})"))

    # For method/property search, we need to describe matching classes
    if scope in ("all", "methods", "properties"):
        # Find classes likely to contain matching methods
        # Check top matching classes + scan all class names for the query
        candidates = [n for n in class_names if q in n.lower()]
        if not candidates:
            # Search all classes — limit to avoid excessive subprocess calls
            candidates = class_names[:50]

        for cls_name in candidates[:20]:
            desc_result = runner.describe(profile, cls_name, fmt="console")
            if not desc_result.ok:
                continue

            # Parse methods and fields from describe output
            for line in desc_result.stdout.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                s = _score(query, stripped)
                if s > 0 and s >= 30:
                    results.append((s, f"  {cls_name}: {stripped}"))

    results.sort(key=lambda x: (-x[0], x[1]))
    limit = max_results if max_results > 0 else len(results)
    shown = results[:limit]

    if not shown:
        return (f"No API entries matching '{query}' found.\n"
                f"(Searched {len(class_names)} classes)"
                + confidence_footer(ConfidenceTier.HIGH, "Roslyn parsing"))

    lines = [
        f"## API Search: \"{query}\" ({len(results)} matches, showing {len(shown)})",
        "",
    ]
    for score, text in shown:
        lines.append(text)

    if len(results) > limit:
        lines.append(f"\n... {len(results) - limit} more results omitted")

    return "\n".join(lines) + confidence_footer(ConfidenceTier.HIGH, "source parsing")
