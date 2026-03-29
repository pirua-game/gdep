"""
gdep-mcp/tools/detect_patterns.py

High-level tool: 게임 엔진 디자인 패턴 감지.
프로젝트 코드에서 사용 중인 아키텍처 패턴을 식별한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep.confidence import ConfidenceTier, confidence_footer
from gdep.detector import ProjectKind, detect


def run(project_path: str, max_results: int = 30) -> str:
    """
    Detect design patterns and architectural patterns used in the project.

    Scans the codebase for common game engine patterns:
    - UE5: Subsystem, Component Composition, GAS, Delegates, Replication,
           Interface Implementation, Behavior Tree nodes
    - Unity: Singleton, Coroutine Workflow, ScriptableObject, Event/Observer,
            Object Pooling, State Machine

    Unlike the linter (which finds anti-patterns), this tool identifies
    *positive* patterns to help understand the codebase architecture.

    Use this tool to:
    - Understand "what architectural patterns does this project use?"
    - Onboard to an unfamiliar codebase quickly
    - Review architecture choices before refactoring
    - Generate an architecture overview for documentation

    Args:
        project_path: Absolute path to Scripts/Source folder.
        max_results:  Maximum patterns to show (default 30). Pass 0 for unlimited.

    Returns:
        Summary of detected patterns grouped by category.
    """
    try:
        profile = detect(project_path)
        src = str(profile.source_dirs[0]) if profile.source_dirs else str(profile.root)

        from gdep.analyzer.pattern_detector import (
            detect_ue5_patterns,
            detect_unity_patterns,
            format_patterns,
        )

        patterns = []

        if profile.kind == ProjectKind.UNREAL:
            from gdep.ue5_runner import _get_project
            proj = _get_project(src)
            patterns = detect_ue5_patterns(proj)

        elif profile.kind == ProjectKind.UNITY:
            patterns = detect_unity_patterns(src)

        elif profile.kind == ProjectKind.CPP:
            # Use generic C++ patterns (subset of UE5 patterns)
            from gdep.cpp_runner import _get_project
            proj = _get_project(src)
            patterns = detect_ue5_patterns(proj)  # Reuse — works for generic C++ too

        else:
            return (f"[detect_patterns] Pattern detection not yet supported "
                    f"for {profile.display} projects.")

        output = format_patterns(patterns,
                                 max_results=max_results if max_results > 0 else 9999)

        return output + confidence_footer(
            ConfidenceTier.MEDIUM if profile.kind == ProjectKind.UNITY else ConfidenceTier.HIGH,
            "source pattern matching"
        )

    except Exception as e:
        return f"[detect_patterns] Error: {e}"
