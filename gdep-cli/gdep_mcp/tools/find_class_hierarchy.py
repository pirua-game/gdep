"""
gdep-mcp/tools/find_class_hierarchy.py

High-level tool: 클래스 상속 계층 트리 조회.
주어진 클래스의 조상(ancestor) 체인과 자손(descendant) 트리를 반환한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep import runner
from gdep.confidence import ConfidenceTier, confidence_footer
from gdep.detector import detect


def run(project_path: str, class_name: str,
        direction: str = "both",
        max_depth: int = 10) -> str:
    """
    Find the full inheritance hierarchy of a class.

    Returns the ancestor chain (parents → grandparents → engine base) and/or
    the descendant tree (all classes that directly or transitively inherit from
    the target class). Useful for understanding class taxonomy and planning
    safe refactors.

    Use this tool to:
    - Understand "what does this class inherit from?" (ancestor chain)
    - Find "which classes extend this class?" (descendant tree)
    - Plan safe refactoring by knowing the full inheritance tree
    - Quickly see interfaces and secondary bases

    Args:
        project_path: Absolute path to Scripts (Unity) or Source (UE5) folder.
        class_name:   The class to explore. E.g. "APlayerCharacter", "ManagerBattle"
        direction:    "up" = ancestors only, "down" = descendants only,
                      "both" = full hierarchy (default).
        max_depth:    Maximum traversal depth (default 10).

    Returns:
        Formatted hierarchy tree with file locations and interface markers.
    """
    if direction not in ("up", "down", "both"):
        return (f"[find_class_hierarchy] Invalid direction '{direction}'. "
                "Must be 'up', 'down', or 'both'.")

    try:
        profile = detect(project_path)
        result = runner.hierarchy(profile, class_name,
                                  direction=direction,
                                  max_depth=max_depth)
        if not result.ok:
            return f"Could not build hierarchy for '{class_name}': {result.error_message}"

        return result.stdout + confidence_footer(ConfidenceTier.HIGH, "source parsing")

    except Exception as e:
        return f"[find_class_hierarchy] Error: {e}"
