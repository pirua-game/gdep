"""
gdep-mcp/tools/read_class_source.py

High-level tool: 클래스 또는 메서드 소스 코드 반환.
runner.read_source() 래퍼 — 4개 엔진(C#/UE5/C++/Axmol) 모두 지원.
"""
from __future__ import annotations

import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep import runner
from gdep.detector import detect, ProjectKind


def run(project_path: str, class_name: str,
        max_chars: int = 8000,
        method_name: str | None = None) -> str:
    """
    Return the actual source code of a class or a specific method within it.

    USE THIS TOOL WHEN:
    - You need to read the actual implementation of a class after identifying it
      with explore_class_semantics or find_method_callers
    - You want to understand the business logic, not just the structure
    - You want to see field initializations, exception handling, or state mutations
    - method_name is provided: returns only that method's body (token-efficient)

    Args:
        project_path: Absolute path to Scripts/Source folder (or project root).
        class_name:   Class whose source to return. E.g. "BattleManager", "AHSCharacterBase"
        max_chars:    Maximum characters to return (default 8000, max recommended 15000).
                      Truncates at the last complete line within the limit.
        method_name:  Optional — if provided, extracts and returns only this method's body.
                      Much more token-efficient than returning the whole class.
                      E.g. "PlayHand", "BeginPlay", "ActivateAbility"

    Returns:
        Source code text. If method_name is given, returns only that method's body
        with a language code block header. Returns error message if not found.
    """
    try:
        profile = detect(project_path)
        is_cpp = profile.kind in (ProjectKind.UNREAL, ProjectKind.CPP)

        if method_name:
            return _read_method(profile, class_name, method_name, max_chars, is_cpp)

        result = runner.read_source(profile, class_name, max_chars=max_chars)
        if not result.ok:
            return f"[read_class_source] Could not read source for '{class_name}': {result.error_message}"
        return result.stdout

    except Exception as e:
        return f"[read_class_source] Error: {e}"


def _read_method(profile, class_name: str, method_name: str,
                 max_chars: int, is_cpp: bool) -> str:
    """특정 메서드 본문만 추출하여 반환."""
    from gdep.method_extractor import extract_method_body

    # 소스 로드 (본문 추출용으로 무제한)
    if is_cpp:
        src_result = runner.read_source(profile, class_name, max_chars=200_000)
    else:
        from gdep.source_reader import find_class_files
        src = str(profile.source_dirs[0]) if profile.source_dirs else str(profile.root)
        cs_result = find_class_files(src, class_name)
        if not cs_result.chunks:
            return f"[read_class_source] Could not find source for '{class_name}'."
        src_result = type('R', (), {
            'ok': True,
            'stdout': "\n".join(c.content for c in cs_result.chunks)
        })()

    if not src_result.ok:
        return f"[read_class_source] Could not read source for '{class_name}'."

    source = src_result.stdout
    result = extract_method_body(source, method_name, is_cpp)
    if result is None:
        return (
            f"[read_class_source] Method '{method_name}' not found in '{class_name}'.\n"
            "Tip: use explain_method_logic to find where the method may actually be defined."
        )

    body, _ = result
    lang = "cpp" if is_cpp else "csharp"
    truncated = body[:max_chars]
    suffix = ""
    if len(body) > max_chars:
        suffix = f"\n... ({len(body) - max_chars} chars truncated, increase max_chars to see more)"

    return f"## {class_name}.{method_name}()\n```{lang}\n{truncated}{suffix}\n```"
