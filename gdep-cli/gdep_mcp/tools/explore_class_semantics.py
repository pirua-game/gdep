"""
gdep-mcp/tools/explore_class_semantics.py

High-level tool: 클래스 구조 탐색.
runner.describe 래퍼.

LLM이 설정되어 있으면(gdep config llm) 캐시된 AI 요약을 포함하고,
설정되어 있지 않으면 파싱된 클래스 구조 데이터만 반환한다.

compact=True (기본값)이면 섹션별 항목 수를 제한하여
AI 에이전트가 소비하기 적합한 크기로 출력을 줄인다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep import runner
from gdep.confidence import ConfidenceTier, confidence_footer
from gdep.detector import detect


def run(project_path: str, class_name: str,
        summarize: bool = True, refresh: bool = False,
        include_source: bool = False, max_source_chars: int = 6000,
        compact: bool = True) -> str:
    """
    Explore the full semantic structure of a class.

    Provides fields, methods, dependencies (in/out-degree), and engine asset usages.
    When summarize=True and an internal LLM is configured (gdep config llm),
    prepends a cached 3-line AI role summary. If LLM is not configured, returns
    the raw class structure only — the calling AI agent can summarize from context.

    Results are cached in the project wiki (.gdep/wiki/classes/).
    On subsequent calls with the same class, the cached wiki page is returned
    immediately (no re-analysis) unless the source file has changed or refresh=True.

    Use this tool to:
    - Quickly understand what an unfamiliar class does
    - Get structured context before asking deeper questions about a class
    - Prepare context for code review or refactoring tasks

    Args:
        project_path:     Absolute path to the project Scripts/Source directory.
        class_name:       The class name to explore.
                          Examples: "ManagerBattle", "AHSAttributeSet"
        summarize:        Generate AI 3-line summary if LLM is configured (gdep config llm).
                          If not configured, returns structure only. Default True.
        refresh:          Ignore wiki cache and re-analyze. Default False.
        include_source:   Also return the class source code appended after the structure.
                          Eliminates the need for a separate read_class_source call.
                          Default False (backward compatible).
        max_source_chars: Max characters for the appended source code (default 6000).
        compact:          Limit items per section for AI-friendly output (default True).
                          Fields: 15, Methods: 25, ExtRefs: 10.
                          Use compact=False for the complete untruncated listing.

    Returns:
        Full class structure (fields, methods, refs) with optional AI summary and source.
    """
    try:
        # include_source가 아니면 항상 wiki 레이어를 통과 (refresh=True여도 저장)
        if not include_source:
            try:
                from gdep.wiki.cache_layer import wiki_cached_class
                from gdep.detector import detect as _detect

                def _analyze():
                    return _do_analyze(project_path, class_name, summarize,
                                       refresh, include_source, max_source_chars, compact)

                profile = _detect(project_path)
                engine = profile.display if profile else ""
                return wiki_cached_class(project_path, class_name, _analyze, engine,
                                         refresh=refresh)
            except Exception:
                pass  # wiki 레이어 실패 시 기존 방식으로 fall-through

        return _do_analyze(project_path, class_name, summarize, refresh,
                           include_source, max_source_chars, compact)

    except Exception as e:
        return f"[explore_class_semantics] Error: {e}"


def _do_analyze(project_path: str, class_name: str,
                summarize: bool, refresh: bool,
                include_source: bool, max_source_chars: int,
                compact: bool) -> str:
    """실제 분석 로직 (wiki 레이어 없이 바로 실행)."""
    profile = detect(project_path)

    # LLM 설정 여부 사전 확인 — stdin 대화형 설정(_configure_interactively) 방지
    llm_available = False
    if summarize:
        try:
            from gdep.llm_provider import load_config
            llm_available = load_config() is not None
        except Exception:
            pass

    result = runner.describe(profile, class_name,
                             fmt="console",
                             summarize=(summarize and llm_available),
                             refresh=refresh)
    if not result.ok:
        return f"Could not describe class '{class_name}': {result.error_message}"

    output = result.stdout

    if compact:
        output = _compact_output(output)

    output += confidence_footer(ConfidenceTier.HIGH, "source parsing")

    if include_source:
        src_result = runner.read_source(profile, class_name, max_chars=max_source_chars)
        if src_result.ok and src_result.stdout.strip():
            output += f"\n\n## Source Code: {class_name}\n{src_result.stdout}"
        elif not src_result.ok:
            output += f"\n\n[Source not available: {src_result.error_message}]"

    return output


# ── Compact output post-processor ─────────────────────────────

# Section limits: max items (table rows) per section
_SECTION_LIMITS = {
    "fields":  15,
    "methods": 25,
    "refs":    10,
}

# Markers that appear in new table rows (not continuation lines)
_ITEM_MARKERS = frozenset({
    "public", "private", "protected", "internal",  # access modifiers
    "field", "prop",  # field/property kind
    "async", "override", "virtual", "static", "abstract", "sealed",  # method modifiers
})


def _detect_section(header: str) -> str | None:
    """Map a section header line to a section key."""
    h = header.lower()
    if "field" in h or "prop" in h:
        return "fields"
    if "method" in h:
        return "methods"
    if "external" in h or "out-degree" in h:
        return "refs"
    return None


def _is_new_item(line: str) -> bool:
    """Detect new table row vs continuation line in Rich tables.

    New rows have access/kind/modifier keywords in the right columns.
    Continuation lines have those columns empty (spaces only).
    """
    words = line.split()
    if not words:
        return False
    # Check last 4 words for item markers (access, kind, modifiers)
    tail = words[-4:] if len(words) >= 4 else words
    return any(w in _ITEM_MARKERS for w in tail)


def _compact_output(text: str, max_chars: int = 12000) -> str:
    """Truncate each section to its item limit for AI-friendly output."""
    lines = text.split("\n")
    result: list[str] = []
    section: str | None = None
    limit = 999
    count = 0
    skipped = 0
    suppressing = False  # True when we've exceeded the limit

    for line in lines:
        stripped = line.strip()

        # Section header: lines containing ── AND alphabetic text.
        # Excludes pure table separators (─────) and box-drawing frames (╭╰).
        is_header = (
            "──" in stripped
            and len(stripped) > 4
            and any(c.isalpha() for c in stripped)
            and not stripped.startswith("╭")
            and not stripped.startswith("╰")
        )
        if is_header:
            # Flush skip message for previous section
            if skipped > 0:
                result.append(
                    f"  ... ({skipped} more items omitted"
                    f" — use compact=False for full list)"
                )
                skipped = 0

            section = _detect_section(stripped)
            limit = _SECTION_LIMITS.get(section, 999) if section else 999
            count = 0
            suppressing = False
            result.append(line)
            continue

        if section and limit < 999:
            # Table separators (────) and blank lines always pass through
            if "────" in stripped or not stripped:
                if not suppressing:
                    result.append(line)
                continue

            # Count only new items (not continuation lines of multi-line rows)
            is_new = _is_new_item(line)
            if is_new:
                count += 1

            if count <= limit:
                result.append(line)
            else:
                if is_new:
                    skipped += 1
                suppressing = True
        else:
            result.append(line)

    # Final flush
    if skipped > 0:
        result.append(
            f"  ... ({skipped} more items omitted"
            f" — use compact=False for full list)"
        )

    output = "\n".join(result)
    if len(output) > max_chars:
        output = (
            output[:max_chars]
            + f"\n... (output truncated at {max_chars} chars"
            + f" — use compact=False for full)"
        )
    return output
