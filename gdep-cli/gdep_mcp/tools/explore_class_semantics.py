"""
gdep-mcp/tools/explore_class_semantics.py

High-level tool: 클래스 구조 탐색.
runner.describe(summarize=False) 래퍼.

MCP 경유 호출 시 내부 LLM을 사용하지 않는다.
파싱된 클래스 구조 데이터를 그대로 반환하고,
호출한 LLM(Claude Code / Cursor 등)이 직접 요약을 생성하도록 안내 섹션을 덧붙인다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep import runner
from gdep.detector import detect

_SUMMARY_GUIDANCE = """\

── AI Role Summary ──────────────────────────────────────────────────
Based on the class structure above, please provide a 3-line role summary:
  1. Core identity   — what type of class this is (e.g. Singleton Manager, Data Model, UI Controller)
  2. Responsibility  — its main algorithm or business logic
  3. Interactions    — key dependencies or how other systems use it
─────────────────────────────────────────────────────────────────────
"""


def run(project_path: str, class_name: str,
        summarize: bool = True, refresh: bool = False) -> str:
    """
    Explore the full semantic structure of a class.

    Provides fields, methods, dependencies (in/out-degree), and engine asset usages.
    When summarize=True (default), appends a guidance section so the calling AI
    assistant produces a 3-line role summary from the returned context — no separate
    LLM configuration required.

    Use this tool to:
    - Quickly understand what an unfamiliar class does
    - Get structured context before asking deeper questions about a class
    - Prepare context for code review or refactoring tasks

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        class_name:   The class name to explore.
                      Examples: "ManagerBattle", "AHSAttributeSet"
        summarize:    If True (default), append a summary guidance section for the AI.
        refresh:      Unused in MCP context (kept for API compatibility).

    Returns:
        Full class structure (fields, methods, refs) with optional summary guidance.
    """
    try:
        profile = detect(project_path)
        # Always fetch raw structure without an internal LLM call.
        # The calling LLM (Claude Code, Cursor, Gemini CLI, …) handles summarization.
        result = runner.describe(profile, class_name,
                                 fmt="console",
                                 summarize=False,
                                 refresh=False)
        if not result.ok:
            return f"Could not describe class '{class_name}': {result.error_message}"

        output = result.stdout
        if summarize:
            output += _SUMMARY_GUIDANCE
        return output

    except Exception as e:
        return f"[explore_class_semantics] Error: {e}"
