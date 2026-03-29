"""
/api/analysis  — 신규 분석 도구 라우터
find_class_hierarchy / find_unused_assets / query_project_api /
detect_patterns / find_method_callers / find_call_path
"""
from __future__ import annotations
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

router = APIRouter()


# ── Class Hierarchy ──────────────────────────────────────────

class HierarchyRequest(BaseModel):
    path:      str
    class_name: str
    direction: str = "both"
    max_depth: int = 10


@router.post("/hierarchy")
def class_hierarchy(req: HierarchyRequest):
    try:
        from gdep_mcp.tools.find_class_hierarchy import run
        result = run(req.path, req.class_name, req.direction, req.max_depth)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}


# ── Unused Assets ────────────────────────────────────────────

class UnusedAssetsRequest(BaseModel):
    path:        str
    scan_dir:    Optional[str] = None
    max_results: int = 50


@router.post("/unused-assets")
def unused_assets(req: UnusedAssetsRequest):
    try:
        from gdep_mcp.tools.find_unused_assets import run
        result = run(req.path, req.scan_dir, req.max_results)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}


# ── Query Project API ────────────────────────────────────────

class QueryApiRequest(BaseModel):
    path:        str
    query:       str
    scope:       str = "all"
    max_results: int = 20


@router.post("/query-api")
def query_api(req: QueryApiRequest):
    try:
        from gdep_mcp.tools.query_project_api import run
        result = run(req.path, req.query, req.scope, req.max_results)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}


# ── Detect Patterns ──────────────────────────────────────────

class DetectPatternsRequest(BaseModel):
    path:        str
    max_results: int = 30


@router.post("/detect-patterns")
def detect_patterns(req: DetectPatternsRequest):
    try:
        from gdep_mcp.tools.detect_patterns import run
        result = run(req.path, req.max_results)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}


# ── Method Callers ───────────────────────────────────────────

class MethodCallersRequest(BaseModel):
    path:        str
    class_name:  str
    method_name: str
    max_results: int = 30


@router.post("/method-callers")
def method_callers(req: MethodCallersRequest):
    try:
        from gdep_mcp.tools.find_method_callers import run
        result = run(req.path, req.class_name, req.method_name, req.max_results)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}


# ── Call Path ────────────────────────────────────────────────

class CallPathRequest(BaseModel):
    path:        str
    from_class:  str
    from_method: str
    to_class:    str
    to_method:   str
    depth:       int = 10


@router.post("/call-path")
def call_path(req: CallPathRequest):
    try:
        from gdep_mcp.tools.find_call_path import run
        result = run(req.path, req.from_class, req.from_method,
                     req.to_class, req.to_method, req.depth)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}


# ── Explore Class Semantics ──────────────────────────────────

class ExploreSemanticRequest(BaseModel):
    path:             str
    class_name:       str
    compact:          bool = True
    include_source:   bool = False
    max_source_chars: int = 6000


@router.post("/explore-semantics")
def explore_semantics(req: ExploreSemanticRequest):
    try:
        from gdep_mcp.tools.explore_class_semantics import run
        result = run(req.path, req.class_name,
                     compact=req.compact,
                     include_source=req.include_source,
                     max_source_chars=req.max_source_chars)
        return {"result": result}
    except Exception as e:
        return {"result": f"Error: {e}"}
