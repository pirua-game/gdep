"""
gdep-mcp/server.py

gdep MCP Server — Game Engine Dependency & AI Analysis
FastMCP 기반. Claude Desktop / Cursor / Continue.dev에서 즉시 사용 가능.

실행 방법:
    cd gdep-cli
    pip install -e .
    pip install mcp[cli]
    python -m gdep_mcp.server
    # 또는
    mcp run gdep-mcp/server.py

Claude Desktop 설정 (~/.config/claude/config.json):
    {
      "mcpServers": {
        "gdep": {
          "command": "python",
          "args": ["-m", "gdep_mcp.server"],
          "cwd": "/path/to/gdep/gdep-cli"
        }
      }
    }
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ── 경로 설정 ──────────────────────────────────────────────────
# gdep-mcp/server.py → gdep-cli/ 가 sys.path에 있어야 gdep 패키지를 import할 수 있음
_HERE      = Path(__file__).parent          # gdep-cli/gdep-mcp/
_GDEP_ROOT = _HERE.parent                   # gdep-cli/
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

import anyio
from mcp.server.fastmcp import FastMCP
from gdep.confidence import ConfidenceTier, confidence_footer
from gdep_mcp.tools.analyze_impact_and_risk import run as _impact_run
from gdep_mcp.tools.explore_class_semantics import run as _semantics_run
from gdep_mcp.tools.inspect_architectural_health import run as _health_run
from gdep_mcp.tools.trace_gameplay_flow import run as _flow_run
from gdep_mcp.tools.suggest_test_scope import run as _test_scope_run
from gdep_mcp.tools.suggest_lint_fixes import run as _lint_fixes_run
from gdep_mcp.tools.summarize_project_diff import run as _diff_summary_run
from gdep_mcp.tools.analyze_axmol_events import run as _axmol_events_run
from gdep_mcp.tools.explain_method_logic import run as _explain_logic_run
from gdep_mcp.tools.find_method_callers import run as _callers_run
from gdep_mcp.tools.find_call_path import run as _path_run
from gdep_mcp.tools.find_class_hierarchy import run as _hierarchy_run
from gdep_mcp.tools.find_unused_assets import run as _unused_assets_run
from gdep_mcp.tools.read_class_source import run as _read_source_run
from gdep_mcp.tools.query_project_api import run as _query_api_run
from gdep_mcp.tools.detect_patterns import run as _detect_patterns_run
from gdep_mcp.tools.wiki_search import run as _wiki_search_run
from gdep_mcp.tools.wiki_list import run as _wiki_list_run
from gdep_mcp.tools.wiki_get import run as _wiki_get_run
from gdep_mcp.tools.wiki_save_conversation import run as _wiki_save_conv_run

# ── 추가 분석 모듈 (3~7단계 기능) — 로드 실패해도 서버는 기동됨 ──
try:
    from gdep.unity_event_refs import build_event_map, format_event_result
    _UNITY_EVENTS_AVAILABLE = True
except ImportError:
    _UNITY_EVENTS_AVAILABLE = False

try:
    from gdep.unity_animator import analyze_animator
    _UNITY_ANIMATOR_AVAILABLE = True
except ImportError:
    _UNITY_ANIMATOR_AVAILABLE = False

try:
    from gdep.ue5_gas_analyzer import analyze_gas
    _UE5_GAS_AVAILABLE = True
except ImportError:
    _UE5_GAS_AVAILABLE = False

try:
    from gdep.ue5_ai_analyzer import analyze_behavior_tree, analyze_state_tree
    _UE5_AI_AVAILABLE = True
except ImportError:
    _UE5_AI_AVAILABLE = False

try:
    from gdep.ue5_animator import analyze_abp, analyze_montage
    _UE5_ANIMATOR_AVAILABLE = True
except ImportError:
    _UE5_ANIMATOR_AVAILABLE = False

try:
    from gdep.ue5_blueprint_mapping import (
        build_bp_map,
        format_full_project_map,
        format_mapping,
    )
    _UE5_BP_MAPPING_AVAILABLE = True
except ImportError:
    _UE5_BP_MAPPING_AVAILABLE = False

# ── MCP 서버 초기화 ────────────────────────────────────────────
mcp = FastMCP("gdep")


# ════════════════════════════════════════════════════════════════
# CONTEXT TOOL — 항상 먼저 호출 권장
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_project_context(project_path: str) -> str:
    """
    Get a complete AI-ready overview of the game project. CALL THIS FIRST.

    Returns project type, source path, class count, high-coupling classes,
    GAS summary (UE5), Animator controllers (Unity), and a decision guide
    for which gdep tool to use for each type of question.

    If .gdep/AGENTS.md exists in the project root (created by 'gdep init'),
    returns its content. Otherwise generates context on the fly.

    Use this tool at the start of any coding session on a game project to
    understand the codebase structure before diving into specific tasks.

    Args:
        project_path: Any path within the game project (root, Source, or Assets).
    """
    def _run():
        try:
            from gdep.init_context import build_context_output
            return build_context_output(project_path)
        except Exception as e:
            return f"[get_project_context] Error: {e}"
    return await anyio.to_thread.run_sync(_run)

@mcp.tool()
async def analyze_impact_and_risk(project_path: str, class_name: str,
                                   method_name: str | None = None,
                                   detail_level: str = "summary",
                                   query: str | None = None,
                                   max_results: int = 0) -> str:
    """
    Analyze the blast radius and risks before modifying a class or method.

    ⚠️ CRITICAL: Always call with detail_level="summary" first.
    Only use detail_level="full" if the user explicitly asks for the complete impact tree.
    Use query= to narrow results before escalating to "full".

    USE THIS TOOL WHEN:
    - User says "I want to refactor / modify / rename / delete class X"
    - User asks "what will break if I change X?" or "who calls X::method?"
    - User asks "is it safe to modify X?"
    - Before any non-trivial code change to understand side effects

    Returns:
    - Reverse dependency tree: all classes that directly or indirectly use X
    - Method-level callers (if method_name is provided): which methods call X::method
    - Unity prefab / UE5 blueprint assets that reference X
    - Lint issues already present in or around X (anti-patterns to fix)

    Args:
        project_path: Absolute path to Scripts (Unity) or Source (UE5) folder.
        class_name:   Class to analyze. E.g. "BattleManager", "APlayerCharacter"
        method_name:  Optional method name for method-level impact analysis.
                      E.g. "checkCollision", "Update". Shows which methods call this one.
        detail_level: "summary" (default) — affected class count + top-5 risk items (fast).
                      "full"    — complete impact tree + all lint issues (expensive, use sparingly).
        query:        Optional filter string — only results containing this
                      class name or pattern are included. E.g. "Battle", "Manager"
        max_results:  Maximum lint issues to show (default 0 = auto: 5 summary / 20 full).
    """
    return await anyio.to_thread.run_sync(
        lambda: _impact_run(project_path, class_name, method_name, detail_level, query, max_results)
    )


@mcp.tool()
async def trace_gameplay_flow(project_path: str,
                               class_name: str,
                               method_name: str,
                               depth: int = 5,
                               include_source: bool = True,
                               summary: bool = False) -> str:

    """
    Trace a method's full call chain and show relevant source code.

    USE THIS TOOL WHEN:
    - User asks "how does feature X work?"
    - User asks "trace the flow of method Y"
    - User is debugging and wants to see the execution path
    - User asks "what happens when Z is called?"
    - User wants to understand async chains, locks, or event dispatches

    Returns:
    - Call tree from CLASS.METHOD with async/lock/dispatch annotations
    - Source code of the entry-point class for immediate reference

    Args:
        project_path:   Absolute path to Scripts/Source folder.
        class_name:     Entry-point class. E.g. "ManagerBattle", "AHSCharacterBase"
        method_name:    Entry-point method. E.g. "PlayHand", "BeginPlay", "ActivateAbility"
        depth:          Tracing depth (default 4, max recommended 6).
        include_source: Append source code of entry class (default True).
        summary:        Compact 2-level tree with stats. Saves tokens for agent use.
                        When True, include_source is forced False.
    """
    return await anyio.to_thread.run_sync(
        lambda: _flow_run(project_path, class_name, method_name, depth, include_source, summary)
    )


@mcp.tool()
async def inspect_architectural_health(project_path: str, include_dead_code: bool = True,
                                        include_refs: bool = True, top: int = 15) -> str:
    """
    Full architectural health check: coupling, cycles, dead code, and anti-patterns.

    USE THIS TOOL WHEN:
    - User asks "is the codebase in good shape?"
    - User asks "what's the technical debt here?"
    - User asks "are there circular dependencies?"
    - User asks "what code is dead / unused?"
    - At the start of a refactoring session for an overview

    Note: May take 10-60 seconds on large projects (>500 files).

    Args:
        project_path:      Absolute path to Scripts/Source folder.
        include_dead_code: Detect unreferenced classes (default True).
        include_refs:      Factor in engine asset refs for dead-code filtering (default True).
        top:               Number of high-coupling classes to show (default 15).
    """
    return await anyio.to_thread.run_sync(
        lambda: _health_run(project_path, include_dead_code, include_refs, top)
    )


@mcp.tool()
async def explore_class_semantics(project_path: str, class_name: str,
                                   summarize: bool = True, refresh: bool = False,
                                   include_source: bool = False,
                                   max_source_chars: int = 6000,
                                   compact: bool = True) -> str:
    """
    Get the full structure of a class with an optional AI-generated role summary.

    USE THIS TOOL WHEN:
    - User asks "what does class X do?"
    - User asks "show me the structure of X"
    - User is unfamiliar with a class and needs context before editing it
    - User asks "what methods / fields does X have?"
    - Before writing code that interacts with X

    Returns:
    - Fields, methods, in/out dependencies
    - Unity prefab / UE5 blueprint usages (engine asset back-references)
    - 3-line AI summary of the class role (when LLM is configured via gdep config llm)
    - Source code appended (when include_source=True)

    Args:
        project_path:     Absolute path to Scripts/Source folder.
        class_name:       Class to explore. E.g. "ManagerBattle", "AHSAttributeSet"
        summarize:        Generate AI 3-line summary if LLM is configured. Default True.
        refresh:          Ignore cache and regenerate summary. Default False.
        include_source:   Append actual source code after structure analysis. Default False.
                          Use when you need to understand implementation details immediately.
        max_source_chars: Max chars for appended source (default 6000).
        compact:          Limit items per section for AI-friendly output (default True).
                          Shows top 15 fields, 25 methods, 10 ext refs with counts.
                          Use compact=False only when you need the complete listing.
    """
    return await anyio.to_thread.run_sync(
        lambda: _semantics_run(project_path, class_name, summarize, refresh,
                               include_source, max_source_chars, compact)
    )


@mcp.tool()
async def find_class_hierarchy(project_path: str, class_name: str,
                                direction: str = "both",
                                max_depth: int = 10) -> str:
    """
    Get the full inheritance hierarchy of a class.

    Returns the ancestor chain (parents → engine base) and/or descendant
    tree (all classes deriving from the target). Works for C++, UE5,
    Unity (C#), and .NET projects.

    USE THIS TOOL WHEN:
    - User asks "what does this class inherit from?"
    - User asks "which classes extend / derive from X?"
    - User wants to see the full class taxonomy / lineage
    - Before refactoring a base class, to see all affected subclasses
    - User asks about interfaces implemented by a class

    Args:
        project_path: Absolute path to Scripts/Source folder.
        class_name:   Target class. E.g. "APlayerCharacter", "ManagerBattle"
        direction:    "up" = ancestors only, "down" = descendants only,
                      "both" = full hierarchy (default).
        max_depth:    Maximum traversal depth (default 10).
    """
    return await anyio.to_thread.run_sync(
        lambda: _hierarchy_run(project_path, class_name, direction, max_depth)
    )


@mcp.tool()
async def find_unused_assets(project_path: str, scan_dir: str | None = None,
                              max_results: int = 50) -> str:
    """
    Find potentially unused assets in the project (Unity/UE5 only).

    Scans the project's asset directory and identifies assets that are
    not referenced by any other asset. Useful for cleaning up projects
    and reducing build size.

    USE THIS TOOL WHEN:
    - User asks "which assets are unused / can I delete?"
    - User wants to reduce build size or clean up the project
    - User asks "are there orphan assets?"

    Limitations:
    - Assets loaded via code (Resources.Load, soft references) may be falsely
      reported. Always verify before deleting.

    Args:
        project_path: Absolute path to project root or Scripts/Source folder.
        scan_dir:     Optional subdirectory to limit the scan.
        max_results:  Maximum results to show (default 50). Pass 0 for unlimited.
    """
    return await anyio.to_thread.run_sync(
        lambda: _unused_assets_run(project_path, scan_dir, max_results)
    )


@mcp.tool()
async def query_project_api(project_path: str, query: str,
                             scope: str = "all",
                             max_results: int = 20) -> str:
    """
    Search the project's code as an API reference (class/method/property lookup).

    Searches all parsed class names, method names, property names, and parameter
    types. Returns ranked results with full signatures.

    USE THIS TOOL WHEN:
    - User asks "find all methods related to Health/Damage/Save"
    - User asks "what classes handle inventory?"
    - User wants to discover available APIs before writing integration code
    - User asks "show me methods that return X type"

    Note: Searches PROJECT code only (not engine source).

    Args:
        project_path: Absolute path to Scripts/Source folder.
        query:        Search term. E.g. "Health", "Attack", "Save"
        scope:        "all" (default), "classes", "methods", or "properties"
        max_results:  Maximum results (default 20). Pass 0 for unlimited.
    """
    return await anyio.to_thread.run_sync(
        lambda: _query_api_run(project_path, query, scope, max_results)
    )


@mcp.tool()
async def detect_patterns(project_path: str, max_results: int = 30) -> str:
    """
    Detect design patterns and architectural patterns used in the project.

    Identifies common game engine patterns (Singleton, Component Composition,
    GAS, Event/Observer, Replication, State Machine, Object Pooling, etc.)
    to help understand the codebase architecture.

    USE THIS TOOL WHEN:
    - User asks "what patterns does this project use?"
    - User wants an architecture overview before refactoring
    - User is onboarding to an unfamiliar codebase
    - User asks "how is this project structured?"

    Args:
        project_path: Absolute path to Scripts/Source folder.
        max_results:  Maximum patterns to show (default 30). Pass 0 for unlimited.
    """
    return await anyio.to_thread.run_sync(
        lambda: _detect_patterns_run(project_path, max_results)
    )


# ════════════════════════════════════════════════════════════════
# RAW CLI ACCESS TOOL
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def execute_gdep_cli(args: list[str]) -> str:
    """
    Execute any gdep CLI command directly. Use this to access features not covered
    by the high-level tools above.

    You MUST provide exact CLI arguments as a list of strings.

    Common examples:
      Detect project type:    ["detect", "D:/MyGame/Assets/Scripts"]
      Scan with dead code:    ["scan", "D:/MyGame/Assets/Scripts", "--dead-code", "--circular"]
      Describe a class:       ["describe", "D:/MyGame/Assets/Scripts", "BattleManager"]
      Flow trace (console):   ["flow", "D:/MyGame/Assets/Scripts", "--class", "BattleManager", "--method", "StartBattle"]
      Impact analysis:        ["impact", "D:/MyGame/Assets/Scripts", "BattleManager", "--depth", "5"]
      Lint check:             ["lint", "D:/MyGame/Assets/Scripts"]
      Graph export:           ["graph", "D:/MyGame/Assets/Scripts", "--format", "mermaid"]
      Diff vs HEAD~1:         ["diff", "D:/MyGame/Assets/Scripts", "--commit", "HEAD~1"]
      Generate hints:         ["hints", "generate", "D:/MyGame/Assets/Scripts"]
      Show LLM config:        ["config", "llm"]

    Args:
        args: CLI argument list (exclude 'gdep' itself).
              E.g. ["scan", "D:\\Project", "--dead-code"] runs: gdep scan D:\\Project --dead-code
    """
    def _run():
        try:
            command = [sys.executable, "-m", "gdep.cli"] + args

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                stdin=subprocess.DEVNULL,
                env=env,
                timeout=180,
                cwd=str(_GDEP_ROOT),
            )

            if result.returncode == 0:
                output = result.stdout or ""
                if result.stderr and result.stderr.strip():
                    output = (output.rstrip("\n") + "\n\n" if output.strip() else "") + result.stderr.strip()
                return output or "(No output)"
            return (
                f"CLI Error (exit {result.returncode}):\n"
                f"{result.stderr}\n"
                f"{result.stdout}"
            )

        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 180 seconds."
        except Exception as e:
            return f"Failed to execute CLI command: {e}"
    return await anyio.to_thread.run_sync(_run)


# ════════════════════════════════════════════════════════════════
# TEST SCOPE TOOL
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def suggest_test_scope(project_path: str, class_name: str, depth: int = 3) -> str:
    """
    Suggest which test files need to run when a specific class is modified.

    USE THIS TOOL WHEN:
    - User asks "what tests do I need to run after changing class X?"
    - User asks "which tests cover class X?"
    - PR review: determine the minimal test set for a change
    - CI automation: generate a targeted test-file list programmatically
    - User says "I'm about to modify X, what should I test?"

    Performs reverse-dependency analysis (like analyze_impact_and_risk) and then
    filters the affected class list to test files only, using engine-specific patterns:
      - Unity / .NET : *Test*.cs  *Tests.cs  *Spec.cs  or  Tests/ directory
      - UE5          : *Spec.cpp  *Test*.cpp            or  Tests/ Specs/ directory
      - C++          : *test*.cpp *spec*.cpp test_*.cpp or  tests/ directory

    Returns:
    - Number of directly affected classes
    - List of test files that cover the affected scope, with engine tag and matched class

    Args:
        project_path: Absolute path to Scripts (Unity) or Source (UE5) folder.
        class_name:   Class to analyze. E.g. "BattleManager", "APlayerCharacter"
        depth:        Reverse-dependency tracing depth (default 3).
    """
    return await anyio.to_thread.run_sync(
        lambda: _test_scope_run(project_path, class_name, depth)
    )


# ════════════════════════════════════════════════════════════════
# LINT FIX TOOL
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def suggest_lint_fixes(project_path: str, rule_ids: list[str] | None = None) -> str:
    """Run linter and return actionable code fix suggestions for detected anti-patterns.

    Goes beyond reporting — provides concrete code snippets for each fixable issue.
    Currently supports: UNI-PERF-001, UNI-PERF-002, UE5-BASE-001, UNI-ASYNC-001,
    AXM-PERF-001, AXM-MEM-001, AXM-EVENT-001.

    USE THIS TOOL WHEN:
    - User asks 'how do I fix these lint warnings?'
    - After analyze_impact_and_risk reveals anti-patterns
    - Pre-PR cleanup: user wants concrete steps, not just a list

    Args:
        project_path: Absolute path to project root or Scripts/Source directory.
        rule_ids: Optional list of rule IDs to filter (e.g. ['UNI-PERF-001']).
    """
    return await anyio.to_thread.run_sync(
        lambda: _lint_fixes_run(project_path, rule_ids=rule_ids)
    )


# ════════════════════════════════════════════════════════════════
# DIFF SUMMARY TOOL
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def summarize_project_diff(project_path: str,
                                  commit_ref: str | None = None) -> str:
    """
    Analyze git diff and summarize the architectural impact of changes.

    USE THIS TOOL WHEN:
    - User asks "what does this PR do to the codebase architecture?"
    - User asks "does this change introduce new circular dependencies?"
    - User asks "is this commit risky from an architecture standpoint?"
    - PR review: need to understand structural impact, not just file changes
    - After refactoring: verify circular references were resolved

    Returns:
    - Number of changed files
    - New vs resolved circular references (net change)
    - High-coupling classes involved in new cycles (blast-radius warning)
    - Actionable review recommendations

    Args:
        project_path: Absolute path to project root or Scripts/Source directory.
        commit_ref:   Git ref to diff against (e.g. "HEAD~1", "main", a commit SHA).
                      Defaults to "HEAD~1".

    Note: Currently supports Unity / C# projects. For UE5/C++ use inspect_architectural_health.
    """
    return await anyio.to_thread.run_sync(
        lambda: _diff_summary_run(project_path, commit_ref=commit_ref)
    )


# ════════════════════════════════════════════════════════════════
# AXMOL-SPECIFIC TOOLS
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def analyze_axmol_events(project_path: str,
                                class_name: str | None = None) -> str:
    """
    Scan an Axmol project for EventDispatcher and scheduler callback bindings.

    USE THIS TOOL WHEN:
    - User asks "which callbacks does this Axmol class register?"
    - User asks "where is this method wired as an event callback?"
    - Debugging event listener leaks or unexpected callback invocations
    - Reviewing which classes opt in to the scheduler (scheduleUpdate)

    Detects:
    - addEventListenerWithSceneGraphPriority / addEventListenerWithFixedPriority
    - CC_CALLBACK_0/1/2/3(ClassName::method, this) macro bindings
    - schedule / scheduleOnce with CC_SCHEDULE_SELECTOR(ClassName::method)
    - scheduleUpdate() registrations (implicit update() callback)

    Args:
        project_path: Absolute path to Axmol project root or Classes/ directory.
        class_name:   Optional class name to filter results.
                      If None, returns all bindings in the project.
    """
    return await anyio.to_thread.run_sync(
        lambda: _axmol_events_run(project_path, class_name)
    )


# ════════════════════════════════════════════════════════════════
# UNITY-SPECIFIC TOOLS (3단계 기능)
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def find_unity_event_bindings(project_path: str,
                                     method_name: str | None = None) -> str:
    """
    Find Unity Event (UnityEvent / Button.onClick) bindings in prefabs, scenes, and assets.

    Scans .prefab, .unity, and .asset files for persistent call bindings
    (m_PersistentCalls) and returns which methods are wired to which events.

    This reveals methods that are called from the Inspector (not visible in code search).

    Args:
        project_path: Absolute path to Unity Assets or Scripts folder.
        method_name:  Optional filter — only return bindings for this method name.
                      If None, returns all event bindings found.
    """
    def _run():
        if not _UNITY_EVENTS_AVAILABLE:
            return (
                "unity_event_refs module not available yet. "
                "Use execute_gdep_cli(['scan', project_path]) as a fallback."
            )
        try:
            from gdep.unity_event_refs import build_event_map, format_event_result
            event_map = build_event_map(project_path)
            return format_event_result(event_map, method_name) + confidence_footer(ConfidenceTier.HIGH, "Unity persistent-call YAML parsing")
        except Exception as e:
            return f"[find_unity_event_bindings] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def analyze_unity_animator(project_path: str,
                                  controller_name: str | None = None,
                                  detail_level: str = "summary") -> str:
    """
    Analyze Unity Animator Controller structure: layers, states, transitions, blend trees.

    Parses .controller files (Unity YAML) and returns a structured view of
    the animation state machine — layers, states, any-state transitions, blend trees,
    and which animation clips each state uses.

    Args:
        project_path:     Absolute path to Unity Assets or project root.
        controller_name:  Optional — analyze only the named .controller file.
                          If None, analyzes all .controller files found.
        detail_level:     "summary" (default) — controller names + layer/state counts.
                          "full" — complete analysis with parameters, blend trees, transitions.
    """
    def _run():
        if not _UNITY_ANIMATOR_AVAILABLE:
            return (
                "unity_animator module not available yet. "
                "Use execute_gdep_cli(['detect', project_path]) as a fallback."
            )
        try:
            from gdep.unity_animator import analyze_animator
            return analyze_animator(project_path, controller_name, detail_level=detail_level) + confidence_footer(ConfidenceTier.MEDIUM, "animator YAML parsing")
        except Exception as e:
            return f"[analyze_unity_animator] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


# ════════════════════════════════════════════════════════════════
# UE5-SPECIFIC TOOLS (5~7단계 기능)
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def analyze_ue5_gas(project_path: str,
                           class_name: str | None = None,
                           detail_level: str = "summary",
                           category: str | None = None,
                           query: str | None = None) -> str:
    """
    Analyze Gameplay Ability System (GAS) usage in a UE5 project.

    ⚠️ CRITICAL: Always call with detail_level="summary" first.
    Only use detail_level="full" if the user explicitly requests the full GAS report.
    Large projects may have 100+ tags — use category= or query= to narrow results before using "full".

    Scans C++ source and .uasset binaries to extract:
    - GameplayTags used (FGameplayTag, FGameplayTagContainer)
    - GameplayAbilities and their activation conditions
    - GameplayEffects and their targets
    - AttributeSets and their attributes
    - AbilitySystemComponent usage
    - ABP (AnimBlueprint) relationships to abilities

    Args:
        project_path: Absolute path to UE5 Source or project root.
        class_name:   Optional — filter results to a specific class.
                      If None, scans the entire project.
        detail_level: "summary" (default) — compact overview with tag distribution.
                      "full" — complete report (expensive; may return 100+ tags for large projects).
        category:     Tag prefix filter. e.g. "Event" → only Event.* tags and
                      abilities/effects that reference those tags.
        query:        Keyword search across class names, tag names, and asset names
                      (case-insensitive substring match).

    Usage examples:
        analyze_ue5_gas(path)                          # compact summary (always start here)
        analyze_ue5_gas(path, category="Event")        # Event.* tags only
        analyze_ue5_gas(path, query="Dash")            # everything related to Dash
        analyze_ue5_gas(path, detail_level="full")     # full report (only if user explicitly asked)
    """
    def _run():
        if not _UE5_GAS_AVAILABLE:
            return (
                "ue5_gas_analyzer module not available yet. "
                "Use execute_gdep_cli(['scan', project_path, '--deep']) as a fallback."
            )
        try:
            from gdep.ue5_gas_analyzer import analyze_gas
            return analyze_gas(project_path, class_name, detail_level, category, query)
        except Exception as e:
            return f"[analyze_ue5_gas] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def analyze_ue5_behavior_tree(project_path: str,
                                     asset_name: str | None = None) -> str:
    """
    Extract and describe UE5 Behavior Tree structure from .uasset files.

    Parses BehaviorTree assets to reveal:
    - Root → Composite → Task/Decorator/Service hierarchy
    - Referenced C++ Task/Decorator/Service class names
    - Blackboard asset and its keys
    - Connection between BT assets and the AI Controllers that use them

    Args:
        project_path: Absolute path to UE5 Content or project root.
        asset_name:   Optional .uasset filename (without extension) to analyze.
                      If None, scans all BehaviorTree assets found.
    """
    def _run():
        if not _UE5_AI_AVAILABLE:
            return (
                "ue5_ai_analyzer module not available yet. "
                "Use execute_gdep_cli(['describe', project_path, 'MyAIController']) as a fallback."
            )
        try:
            from gdep.ue5_ai_analyzer import analyze_behavior_tree
            return analyze_behavior_tree(project_path, asset_name) + confidence_footer(ConfidenceTier.MEDIUM, "binary .uasset pattern match")
        except Exception as e:
            return f"[analyze_ue5_behavior_tree] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def analyze_ue5_state_tree(project_path: str,
                                  asset_name: str | None = None) -> str:
    """
    Extract and describe UE5 StateTree structure from .uasset files.

    Parses StateTree assets (UE 5.2+) to reveal:
    - State hierarchy and transitions
    - Task/Evaluator/Condition C++ class references
    - Enter/Exit conditions per state
    - Linked schema and context data

    Args:
        project_path: Absolute path to UE5 Content or project root.
        asset_name:   Optional asset filename to analyze. If None, scans all StateTree assets.
    """
    def _run():
        if not _UE5_AI_AVAILABLE:
            return "ue5_ai_analyzer module not available yet."
        try:
            from gdep.ue5_ai_analyzer import analyze_state_tree
            return analyze_state_tree(project_path, asset_name) + confidence_footer(ConfidenceTier.MEDIUM, "binary .uasset pattern match")
        except Exception as e:
            return f"[analyze_ue5_state_tree] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def analyze_ue5_animation(project_path: str,
                                 asset_name: str | None = None,
                                 asset_type: str = "all",
                                 detail_level: str = "summary") -> str:
    """
    Analyze UE5 animation assets: AnimBlueprint (ABP) and Animation Montages.

    USE THIS TOOL WHEN:
    - User asks "what animation states does this character have?"
    - User asks "which montages are used for abilities?"
    - User asks "what GAS notifies are in the animation?"
    - User needs to understand the animation graph structure

    detail_level controls output verbosity:
    - "summary" (default): Only gameplay-relevant info — State names, Slot names,
                           GAS-related notifies, referenced anim assets.
                           Best for understanding the animation system.
    - "full": Everything above + all AnimNotify classes, all asset references.
              Best for detailed debugging or documentation.

    Extracts:
    - ABP: state machine states (Idle/Jump/Attack etc.), slots, GAS ability notifies
    - Montage: section names, slot names, GAS notify events, AnimSequence references

    Args:
        project_path: Absolute path to UE5 Content or project root.
        asset_name:   Optional asset name filter. If None, scans all animation assets.
        asset_type:   One of "abp", "montage", or "all" (default).
        detail_level: "summary" (default) or "full".
    """
    def _run():
        if not _UE5_ANIMATOR_AVAILABLE:
            return "ue5_animator module not available yet."
        try:
            from gdep.ue5_animator import analyze_abp, analyze_montage

            def _trim_for_summary(text: str) -> str:
                """summary 모드: 노이즈 섹션 제거."""
                out = []
                skip = False
                for line in text.splitlines():
                    # 섹션 헤더
                    if line.startswith("###"):
                        skip = not any(k in line for k in [
                            "States", "Animation Slots", "GAS-related",
                            "Sections", "Slots", "Referenced Anim"
                        ])
                    if not skip:
                        out.append(line)
                return "\n".join(out)

            if asset_type == "abp":
                result = analyze_abp(project_path, asset_name)
            elif asset_type == "montage":
                result = analyze_montage(project_path, asset_name)
            else:
                result = analyze_abp(project_path, asset_name) + \
                         "\n\n" + analyze_montage(project_path, asset_name)

            output = result if detail_level == "full" else _trim_for_summary(result)
            return output + confidence_footer(ConfidenceTier.MEDIUM, "binary .uasset pattern match")
        except Exception as e:
            return f"[analyze_ue5_animation] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def analyze_ue5_blueprint_mapping(project_path: str,
                                         cpp_class: str | None = None) -> str:
    """
    Blueprint <-> C++ detailed mapping for a UE5 project.

    USE THIS TOOL WHEN:
    - User asks "which Blueprints extend C++ class X?"
    - User asks "what does BP_Character implement?"
    - User asks "which events / K2 functions does this Blueprint override?"
    - User asks "what variables and assets are configured in this Blueprint?"
    - User wants to understand the bridge between C++ and Blueprint logic

    Scans all .uasset files and extracts for each Blueprint:
    - cpp_parent     The C++ parent class (NativeParentClass)
    - bp_class       The Blueprint-generated _C class name
    - event_nodes    Entry points in the event graph with call chains
    - k2_overrides   C++ virtual functions overridden in Blueprint (K2_ prefix)
    - variables      Blueprint-declared variables with type hints
    - asset_refs     /Game/ assets referenced (montages, GEs, other BPs)
    - gameplay_tags  GameplayTag values configured in this Blueprint
    - gas_params     GAS-specific settings (ActivationOwnedTags, etc.)
    - cpp_refs       Additional C++ types used beyond the direct parent

    Args:
        project_path: Absolute path to UE5 Source or project root.
        cpp_class:    Optional C++ class name to filter.
                      If provided, returns full detail: event_nodes, k2_overrides,
                      variables, asset_refs, gameplay_tags, gas_params for matching BPs.
                      If None (default), returns a project-level index showing
                      "C++ class -> BP1 (K2:N Ev:N), BP2 ..." for quick orientation.
                      Use cpp_class for deep inspection of a specific class.

    Examples:
        analyze_ue5_blueprint_mapping(path)
            -> Index: "UGameplayAbility -> GA_Jump (K2:2 Ev:1), GA_Attack (K2:3 Ev:0)"
        analyze_ue5_blueprint_mapping(path, "AHSCharacterBase")
            -> Full detail: events, K2 overrides, variables, tags for each child BP
        analyze_ue5_blueprint_mapping(path, "UGameplayAbility")
            -> Full detail for all GA Blueprints with K2_ActivateAbility chains + tags
    """
    def _run():
        if not _UE5_BP_MAPPING_AVAILABLE:
            return "ue5_blueprint_mapping module not available."
        try:
            from gdep.ue5_blueprint_mapping import build_bp_map, format_full_project_map
            bp_map = build_bp_map(project_path)
            if not bp_map.blueprints:
                return (
                    f"No Blueprint assets found for project at '{project_path}'.\n"
                    "This may happen if:\n"
                    "- The Content folder is empty or missing\n"
                    "- Assets are stored via Git LFS and not pulled yet\n"
                    "- The project path points to Source only (not project root)\n"
                    "Try passing the project root instead of the Source folder."
                )
            return format_full_project_map(bp_map, cpp_class)
        except Exception as e:
            return f"[analyze_ue5_blueprint_mapping] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def get_architecture_advice(project_path: str,
                                   focus_class: str | None = None) -> str:
    """
    Diagnose the architecture of a game project and suggest improvements.

    Combines scan (coupling/cycles/dead-code) + lint (anti-patterns) +
    impact analysis for the highest-risk class into a single advice report.

    If an LLM is configured (gdep config llm), the report is enriched with
    natural-language advice from the model. Results are cached in
    .gdep/cache/advice.md and reused until project metrics change.

    USE THIS TOOL WHEN:
    - User asks "what is the technical debt in this project?"
    - User asks "what should I refactor first?"
    - User asks "diagnose the architecture problems"
    - User asks "give me refactoring priorities"
    - User wants a high-level overview before starting a large change

    Args:
        project_path: Absolute path to the project root or source directory.
        focus_class:  Optional class name to center the advice around.
                      Impact analysis will pivot on this class.
                      If None, the highest-coupling class is used automatically.
    """
    def _run():
        try:
            from gdep.detector import detect
            from gdep import runner
            profile = detect(project_path)
            result = runner.advise(profile, focus_class=focus_class)
            if not result.ok:
                return f"[get_architecture_advice] Error: {result.error_message}"
            return result.stdout
        except Exception as e:
            return f"[get_architecture_advice] Error: {e}"
    return await anyio.to_thread.run_sync(_run)


@mcp.tool()
async def explain_method_logic(project_path: str, class_name: str, method_name: str,
                                include_source: bool = False,
                                max_source_chars: int = 4000) -> str:
    """
    Extract and summarize the internal control flow logic of a specific method.

    Unlike trace_gameplay_flow (which shows the call chain A→B→C),
    this tool focuses on WHY and WHEN calls happen inside a single method —
    returning guard conditions, branches, loops, and key calls in 5-10 lines.

    USE THIS TOOL WHEN:
    - User asks "what does method X actually do internally?"
    - User asks "what are the conditions inside PlayHand / ActivateAbility?"
    - User wants to understand business rules without reading the full source file
    - User asks "when does this method return early?"
    - User is debugging conditional logic or branching behavior

    Returns:
    - Numbered list of Guard / Branch / Loop / Always control flow items
    - Each item shows the condition and 1-2 key calls made in that branch
    - Source file reference for quick navigation
    - Method body source code (when include_source=True)

    Args:
        project_path:     Absolute path to the project root or source folder.
        class_name:       Class containing the method. E.g. "ManagerBattle"
        method_name:      Method to explain. E.g. "PlayHand", "ActivateAbility"
        include_source:   Also return the actual method body code. Default False.
                          Use when the control flow summary isn't enough context.
        max_source_chars: Max chars for the method body (default 4000).
    """
    return await anyio.to_thread.run_sync(
        lambda: _explain_logic_run(project_path, class_name, method_name,
                                   include_source, max_source_chars)
    )


@mcp.tool()
async def find_method_callers(project_path: str, class_name: str, method_name: str,
                               max_results: int = 30) -> str:
    """
    Find all methods that call a specific method (reverse call graph).

    USE THIS TOOL WHEN:
    - User asks "who calls this method?"
    - User asks "what will break if I change method X?"
    - User wants to understand the blast radius of a method change
    - User wants to find all entry points that lead to a specific method

    Returns:
    - List of CallerClass::CallerMethod with call conditions
    - Caller count and pagination info

    Args:
        project_path: Absolute path to Scripts/Source folder.
        class_name:   Class containing the method. E.g. "ManagerBattle"
        method_name:  Method to find callers of. E.g. "PlayHand"
        max_results:  Maximum callers to return (default 30). Pass 0 for unlimited.
    """
    return await anyio.to_thread.run_sync(
        lambda: _callers_run(project_path, class_name, method_name, max_results)
    )


@mcp.tool()
async def find_call_path(project_path: str, from_class: str, from_method: str,
                          to_class: str, to_method: str, depth: int = 10) -> str:
    """
    Find the shortest call path between two methods (A to B connection trace).
    **C#/Unity projects only** — C++ and UE5 projects are not supported yet.

    USE THIS TOOL WHEN:
    - User asks "how does A connect to B?"
    - User asks "does method X eventually call method Y?"
    - User wants to trace a UI event to a backend method
    - User wants to understand how an entry point reaches a specific logic

    Returns:
    - Step-by-step call path: A.m1 → B.m2 [condition] → C.m3
    - Or "No path found" if methods are not connected

    Args:
        project_path: Absolute path to Scripts/Source folder.
        from_class:   Source class. E.g. "UIBattle"
        from_method:  Source method. E.g. "OnClickPlayingCard"
        to_class:     Target class. E.g. "ManagerBattle"
        to_method:    Target method. E.g. "PlayHand"
        depth:        Max search depth (default 10).
    """
    return await anyio.to_thread.run_sync(
        lambda: _path_run(project_path, from_class, from_method, to_class, to_method, depth)
    )


# ════════════════════════════════════════════════════════════════
# SOURCE CODE ACCESS TOOL
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def read_class_source(project_path: str, class_name: str,
                             max_chars: int = 8000,
                             method_name: str | None = None) -> str:
    """
    Return the actual source code of a class or a specific method within it.

    USE THIS TOOL WHEN:
    - You need to read actual implementation after identifying a class with explore_class_semantics
    - You want to understand business logic, not just structure (fields/methods list)
    - You want to see field initializations, exception handling, async patterns, or state mutations
    - You want to understand WHY code is written a certain way (design intent, context)
    - method_name is provided: returns ONLY that method's body (token-efficient)

    This tool bridges the gap between gdep's structural analysis and actual code understanding.
    Use after: explore_class_semantics, find_method_callers, analyze_impact_and_risk

    Args:
        project_path: Absolute path to Scripts/Source folder (or project root).
        class_name:   Class to read. E.g. "BattleManager", "AHSCharacterBase"
        max_chars:    Maximum characters to return (default 8000, max recommended 15000).
        method_name:  Optional — if provided, returns ONLY this method's body.
                      Much more token-efficient. E.g. "PlayHand", "BeginPlay"

    Returns:
        Source code as text. With method_name: returns only that method in a code block.
    """
    return await anyio.to_thread.run_sync(
        lambda: _read_source_run(project_path, class_name, max_chars, method_name)
    )


# ════════════════════════════════════════════════════════════════
# WIKI TOOLS — 축적된 분석 결과 위키 조회
# ════════════════════════════════════════════════════════════════

@mcp.tool()
async def wiki_search(project_path: str, query: str,
                      node_type: str | list[str] | None = None,
                      related: bool | str = False,
                      limit: int = 20,
                      mode: str = "or") -> str:
    """
    Search the project wiki for previously analyzed classes, assets, and systems.

    Uses FTS5 full-text search with BM25 ranking — finds nodes even when you
    don't know the exact class name.

    USE THIS TOOL FIRST before running fresh analysis tools.
    The wiki accumulates analysis results across sessions — if a class or asset
    has already been analyzed, you can get the result instantly without re-analysis.

    USE THIS TOOL WHEN:
    - You want to check if a class/asset has already been analyzed
    - You want to find all analyzed entities related to a concept (e.g. "damage", "ability", "zombie AI")
    - You want to see what the team has already explored in previous sessions
    - You want to find classes related to a known class (use related=True)
    - You need to narrow down broad results with mode='and'

    Returns matching wiki nodes with BM25 relevance scores and content snippets.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        query:        Search keyword or phrase.
                      Examples: "damage", "PlayerCharacter", "GAS ability", "zombie AI"
        node_type:    Optional filter. String or list of strings:
                        'class', 'asset', 'system', 'pattern', 'conversation'
                      Example: ['class', 'asset'] — search both types.
                      None = search all types.
        related:      If True, also includes nodes connected via dependency edges
                      (depends_on, referenced_by, inherits, uses_asset).
                      Nodes not yet in wiki appear as stubs with "(not yet analyzed)"
                      to hint at unexplored relationships.
        limit:        Maximum results to return (default 20).
        mode:         Query matching mode (default 'or'):
                        'or'     — any word matches (broad, good for exploration)
                        'and'    — all words must match (precise, avoids noise)
                        'phrase' — exact phrase in sequence (strictest)
                      Use 'and' when OR returns too many unrelated results.
                      Use 'phrase' for exact method names or class names with spaces.
    """
    # MCP 클라이언트가 "true"/"false" 문자열로 전송하는 경우 대비
    if isinstance(related, str):
        related = related.lower() in ("true", "1", "yes")
    return await anyio.to_thread.run_sync(
        lambda: _wiki_search_run(project_path, query, node_type, related, limit, mode)
    )


@mcp.tool()
async def wiki_list(project_path: str,
                    node_type: str | list[str] | None = None,
                    limit: int = 50) -> str:
    """
    List all wiki nodes for this project — previously analyzed classes, assets, and systems.

    USE THIS TOOL WHEN:
    - You want to see all analyzed entities before starting work on a project
    - You want to check if any nodes are stale (source has changed since last analysis)
    - You want an overview of what knowledge has accumulated in the wiki

    Stale nodes (⚠) need re-analysis — call the relevant analysis tool to refresh them.

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        node_type:    Optional filter. String or list of strings:
                        'class', 'asset', 'system', 'pattern', 'conversation'
                      Example: ['class', 'asset'] — list both class and asset nodes.
                      None = list all types.
        limit:        Maximum nodes to show (default 50).
    """
    return await anyio.to_thread.run_sync(
        lambda: _wiki_list_run(project_path, node_type, limit)
    )


@mcp.tool()
async def wiki_get(project_path: str, node_id: str) -> str:
    """
    Read the full content of a wiki node by its ID.

    Wiki nodes contain previously analyzed class structures, asset mappings,
    engine system overviews, and pattern documentation accumulated across sessions.

    USE THIS TOOL WHEN:
    - wiki_search or wiki_list found a node you want to read in detail
    - You want to review a cached analysis without triggering re-analysis

    Node ID format: 'type:Name'
    Examples: 'class:PlayerCharacter', 'asset:BP_GA_BasicAttack',
              'system:gas', 'pattern:Singleton', 'class:DamageManager'

    Args:
        project_path: Absolute path to the project Scripts/Source directory.
        node_id:      The wiki node ID (from wiki_list or wiki_search results).
    """
    return await anyio.to_thread.run_sync(
        lambda: _wiki_get_run(project_path, node_id)
    )


@mcp.tool()
async def wiki_save_conversation(
    project_path: str,
    title: str,
    content: str,
    referenced_classes: list[str] | None = None,
    tags: list[str] | None = None,
    tools_used: list[str] | None = None,
) -> str:
    """
    Save an agent conversation summary to the project wiki.

    Call this at the end of a session (or at any meaningful checkpoint)
    to persist what was discussed, decided, and discovered.
    Conversations are the most valuable asset of agent sessions — they capture
    context, decisions, and discoveries that raw code analysis cannot.

    USE THIS TOOL WHEN:
    - Session ends and meaningful analysis/decisions were made
    - You want to record architectural decisions for future sessions
    - You explored multiple classes and want to save the context map
    - The user explicitly asks to save the conversation
    - You want future sessions to know what was already investigated

    The saved node is:
    - Searchable via wiki_search (FTS5 full-text, filter node_type='conversation')
    - Browsable via wiki_list (appears under 'Conversations' section)
    - Linked to classes via 'discussed_in' edges (discoverable with related=True)
    - Re-saveable: calling again with same title updates the node (upsert)

    Args:
        project_path:       Absolute path to the project Scripts/Source directory.
        title:              Session title — brief and descriptive.
                            Example: "Zombie AI GAS ability analysis"
        content:            Conversation summary in markdown. Recommended structure:
                            ## Summary — 1-3 bullet overview
                            ## Key Findings — discoveries, dependencies, issues
                            ## Decisions — architectural choices + rationale
                            ## Open Questions — unresolved items
                            ## Next Steps — what to investigate next
        referenced_classes: Optional list of class names discussed in this session.
                            Creates 'discussed_in' edges for graph traversal.
                            Example: ["ULyraAbilitySystemComponent", "ZombieCharacter"]
        tags:               Optional keyword tags for search.
                            Example: ["gas", "ability", "zombie-ai"]
        tools_used:         Optional list of gdep tools used during this session.
                            Example: ["explore_class_semantics", "analyze_ue5_gas"]
    """
    return await anyio.to_thread.run_sync(
        lambda: _wiki_save_conv_run(
            project_path, title, content,
            referenced_classes, tags, tools_used,
        )
    )


# ════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
