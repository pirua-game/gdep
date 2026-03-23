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

_HERE      = Path(__file__).parent
_GDEP_ROOT = _HERE.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from mcp.server.fastmcp import FastMCP
from gdep_mcp.tools.analyze_impact_and_risk import run as _impact_run
from gdep_mcp.tools.explore_class_semantics import run as _semantics_run
from gdep_mcp.tools.inspect_architectural_health import run as _health_run
from gdep_mcp.tools.trace_gameplay_flow import run as _flow_run
from gdep_mcp.tools.suggest_test_scope import run as _test_scope_run
from gdep_mcp.tools.suggest_lint_fixes import run as _lint_fixes_run
from gdep_mcp.tools.summarize_project_diff import run as _diff_summary_run
from gdep_mcp.tools.analyze_axmol_events import run as _axmol_events_run

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
    from gdep.ue5_blueprint_mapping import build_bp_map, format_full_project_map, format_mapping
    _UE5_BP_MAPPING_AVAILABLE = True
except ImportError:
    _UE5_BP_MAPPING_AVAILABLE = False

mcp = FastMCP("gdep")


@mcp.tool()
def get_project_context(project_path: str) -> str:
    """Get a complete AI-ready overview of the game project. CALL THIS FIRST.

    Returns project type, source path, class count, high-coupling classes,
    GAS summary (UE5), Animator controllers (Unity), and a decision guide
    for which gdep tool to use for each type of question.

    If .gdep/AGENTS.md exists in the project root (created by 'gdep init'),
    returns its content. Otherwise generates context on the fly.

    Args:
        project_path: Any path within the game project (root, Source, or Assets).
    """
    try:
        from gdep.init_context import build_context_output
        return build_context_output(project_path)
    except Exception as e:
        return f"[get_project_context] Error: {e}"


@mcp.tool()
def analyze_impact_and_risk(project_path: str, class_name: str) -> str:
    """Analyze the blast radius and risks before modifying a class.

    USE THIS TOOL WHEN:
    - User says "I want to refactor / modify / rename / delete class X"
    - User asks "what will break if I change X?"
    - Before any non-trivial code change to understand side effects

    Args:
        project_path: Absolute path to Scripts (Unity) or Source (UE5) folder.
        class_name:   Class to analyze. E.g. "BattleManager", "APlayerCharacter"
    """
    return _impact_run(project_path, class_name)


@mcp.tool()
def trace_gameplay_flow(project_path: str, class_name: str, method_name: str,
                        depth: int = 4, include_source: bool = True) -> str:
    """Trace a method's full call chain and show relevant source code.

    USE THIS TOOL WHEN:
    - User asks "how does feature X work?" or "trace the flow of method Y"
    - User is debugging and wants to see the execution path

    Args:
        project_path:   Absolute path to Scripts/Source folder.
        class_name:     Entry-point class. E.g. "ManagerBattle", "AHSCharacterBase"
        method_name:    Entry-point method. E.g. "PlayHand", "ActivateAbility"
        depth:          Tracing depth (default 4, max recommended 6).
        include_source: Append source code of entry class (default True).
    """
    return _flow_run(project_path, class_name, method_name, depth, include_source)


@mcp.tool()
def inspect_architectural_health(project_path: str, include_dead_code: bool = True,
                                  include_refs: bool = True, top: int = 15) -> str:
    """Full architectural health check: coupling, cycles, dead code, and anti-patterns.

    USE THIS TOOL WHEN:
    - User asks "is the codebase in good shape?" or "what's the technical debt?"
    - User asks "are there circular dependencies?" or "what code is dead?"

    Args:
        project_path:      Absolute path to Scripts/Source folder.
        include_dead_code: Detect unreferenced classes (default True).
        include_refs:      Factor in engine asset refs for dead-code filtering (default True).
        top:               Number of high-coupling classes to show (default 15).
    """
    return _health_run(project_path, include_dead_code, include_refs, top)


@mcp.tool()
def explore_class_semantics(project_path: str, class_name: str,
                             summarize: bool = True, refresh: bool = False) -> str:
    """Get the full structure of a class with an optional AI-generated role summary.

    USE THIS TOOL WHEN:
    - User asks "what does class X do?" or "show me the structure of X"
    - Before writing code that interacts with X

    Args:
        project_path: Absolute path to Scripts/Source folder.
        class_name:   Class to explore. E.g. "ManagerBattle", "AHSAttributeSet"
        summarize:    Prepend AI 3-line summary (requires gdep config llm). Default True.
        refresh:      Ignore cache and regenerate summary. Default False.
    """
    return _semantics_run(project_path, class_name, summarize, refresh)


@mcp.tool()
def execute_gdep_cli(args: list[str]) -> str:
    """Execute any gdep CLI command directly.

    Common examples:
      ["detect", "D:/MyGame/Assets/Scripts"]
      ["scan", "D:/MyGame/Assets/Scripts", "--dead-code", "--circular"]
      ["describe", "D:/MyGame/Assets/Scripts", "BattleManager"]
      ["flow", "D:/MyGame/Assets/Scripts", "--class", "BattleManager", "--method", "StartBattle"]
      ["impact", "D:/MyGame/Assets/Scripts", "BattleManager", "--depth", "5"]
      ["lint", "D:/MyGame/Assets/Scripts"]
      ["diff", "D:/MyGame/Assets/Scripts", "--commit", "HEAD~1"]

    Args:
        args: CLI argument list (exclude 'gdep'). E.g. ["scan", "D:\\Project", "--dead-code"]
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "gdep.cli"] + args,
            capture_output=True, text=True, encoding="utf-8",
            stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=180, cwd=str(_GDEP_ROOT),
        )
        if result.returncode == 0:
            return result.stdout or "(No output)"
        return f"CLI Error (exit {result.returncode}):\n{result.stderr}\n{result.stdout}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 180 seconds."
    except Exception as e:
        return f"Failed to execute CLI command: {e}"


@mcp.tool()
def suggest_test_scope(project_path: str, class_name: str, depth: int = 3) -> str:
    """Suggest which test files need to run when a specific class is modified.

    USE THIS TOOL WHEN:
    - User asks "what tests do I need to run after changing class X?"
    - PR review: determine the minimal test set for a change
    - CI automation: generate a targeted test-file list

    Args:
        project_path: Absolute path to Scripts (Unity) or Source (UE5) folder.
        class_name:   Class to analyze. E.g. "BattleManager", "APlayerCharacter"
        depth:        Reverse-dependency tracing depth (default 3).
    """
    return _test_scope_run(project_path, class_name, depth)


@mcp.tool()
def suggest_lint_fixes(project_path: str, rule_ids: list[str] | None = None) -> str:
    """Run linter and return actionable code fix suggestions for detected anti-patterns.

    USE THIS TOOL WHEN:
    - User asks "how do I fix these lint warnings?"
    - Pre-PR cleanup: user wants concrete steps, not just a list

    Args:
        project_path: Absolute path to project root or Scripts/Source directory.
        rule_ids: Optional list of rule IDs to filter (e.g. ['UNI-PERF-001']).
    """
    return _lint_fixes_run(project_path, rule_ids=rule_ids)


@mcp.tool()
def summarize_project_diff(project_path: str, commit_ref: str | None = None) -> str:
    """Analyze git diff and summarize the architectural impact of changes.

    USE THIS TOOL WHEN:
    - User asks "what does this PR do to the codebase architecture?"
    - User asks "does this change introduce new circular dependencies?"

    Args:
        project_path: Absolute path to project root or Scripts/Source directory.
        commit_ref:   Git ref to diff against (e.g. "HEAD~1", "main"). Defaults to "HEAD~1".
    """
    return _diff_summary_run(project_path, commit_ref=commit_ref)


@mcp.tool()
def analyze_axmol_events(project_path: str, class_name: str | None = None) -> str:
    """Scan an Axmol project for EventDispatcher and scheduler callback bindings.

    USE THIS TOOL WHEN:
    - User asks "which callbacks does this Axmol class register?"
    - Debugging event listener leaks or unexpected callback invocations

    Detects addEventListenerWithSceneGraphPriority, CC_CALLBACK_* macros,
    schedule/scheduleOnce with CC_SCHEDULE_SELECTOR, scheduleUpdate().

    Args:
        project_path: Absolute path to Axmol project root or Classes/ directory.
        class_name:   Optional class name to filter results.
    """
    return _axmol_events_run(project_path, class_name)


@mcp.tool()
def find_unity_event_bindings(project_path: str, method_name: str | None = None) -> str:
    """Find Unity Event bindings in prefabs, scenes, and assets.

    Reveals methods called from the Inspector (not visible in code search).

    Args:
        project_path: Absolute path to Unity Assets or Scripts folder.
        method_name:  Optional filter. If None, returns all event bindings.
    """
    if not _UNITY_EVENTS_AVAILABLE:
        return "unity_event_refs module not available."
    try:
        from gdep.unity_event_refs import build_event_map, format_event_result
        return format_event_result(build_event_map(project_path), method_name)
    except Exception as e:
        return f"[find_unity_event_bindings] Error: {e}"


@mcp.tool()
def analyze_unity_animator(project_path: str, controller_name: str | None = None) -> str:
    """Analyze Unity Animator Controller: layers, states, transitions, blend trees.

    Args:
        project_path:     Absolute path to Unity Assets or project root.
        controller_name:  Optional .controller filename. If None, analyzes all.
    """
    if not _UNITY_ANIMATOR_AVAILABLE:
        return "unity_animator module not available."
    try:
        from gdep.unity_animator import analyze_animator
        return analyze_animator(project_path, controller_name)
    except Exception as e:
        return f"[analyze_unity_animator] Error: {e}"


@mcp.tool()
def analyze_ue5_gas(project_path: str, class_name: str | None = None) -> str:
    """Analyze Gameplay Ability System (GAS) usage in a UE5 project.

    Extracts GameplayTags, Abilities, Effects, AttributeSets, ASC usage.

    Args:
        project_path: Absolute path to UE5 Source or project root.
        class_name:   Optional filter. If None, scans the entire project.
    """
    if not _UE5_GAS_AVAILABLE:
        return "ue5_gas_analyzer module not available."
    try:
        from gdep.ue5_gas_analyzer import analyze_gas
        return analyze_gas(project_path, class_name)
    except Exception as e:
        return f"[analyze_ue5_gas] Error: {e}"


@mcp.tool()
def analyze_ue5_behavior_tree(project_path: str, asset_name: str | None = None) -> str:
    """Extract UE5 Behavior Tree structure from .uasset files.

    Args:
        project_path: Absolute path to UE5 Content or project root.
        asset_name:   Optional asset name. If None, scans all BehaviorTree assets.
    """
    if not _UE5_AI_AVAILABLE:
        return "ue5_ai_analyzer module not available."
    try:
        from gdep.ue5_ai_analyzer import analyze_behavior_tree
        return analyze_behavior_tree(project_path, asset_name)
    except Exception as e:
        return f"[analyze_ue5_behavior_tree] Error: {e}"


@mcp.tool()
def analyze_ue5_state_tree(project_path: str, asset_name: str | None = None) -> str:
    """Extract UE5 StateTree structure from .uasset files.

    Args:
        project_path: Absolute path to UE5 Content or project root.
        asset_name:   Optional asset name. If None, scans all StateTree assets.
    """
    if not _UE5_AI_AVAILABLE:
        return "ue5_ai_analyzer module not available."
    try:
        from gdep.ue5_ai_analyzer import analyze_state_tree
        return analyze_state_tree(project_path, asset_name)
    except Exception as e:
        return f"[analyze_ue5_state_tree] Error: {e}"


@mcp.tool()
def analyze_ue5_animation(project_path: str, asset_name: str | None = None,
                           asset_type: str = "all", detail_level: str = "summary") -> str:
    """Analyze UE5 animation assets: AnimBlueprint (ABP) and Animation Montages.

    USE THIS TOOL WHEN:
    - User asks "what animation states does this character have?"
    - User asks "which montages are used for abilities?"

    Args:
        project_path: Absolute path to UE5 Content or project root.
        asset_name:   Optional asset name filter. If None, scans all animation assets.
        asset_type:   One of "abp", "montage", or "all" (default).
        detail_level: "summary" (default) or "full".
    """
    if not _UE5_ANIMATOR_AVAILABLE:
        return "ue5_animator module not available."
    try:
        from gdep.ue5_animator import analyze_abp, analyze_montage
        if asset_type == "abp":
            result = analyze_abp(project_path, asset_name)
        elif asset_type == "montage":
            result = analyze_montage(project_path, asset_name)
        else:
            result = analyze_abp(project_path, asset_name) + "\n\n" + analyze_montage(project_path, asset_name)
        return result
    except Exception as e:
        return f"[analyze_ue5_animation] Error: {e}"


@mcp.tool()
def analyze_ue5_blueprint_mapping(project_path: str, cpp_class: str | None = None) -> str:
    """Blueprint <-> C++ detailed mapping for a UE5 project.

    USE THIS TOOL WHEN:
    - User asks "which Blueprints extend C++ class X?"
    - User asks "which events / K2 functions does this Blueprint override?"

    Args:
        project_path: Absolute path to UE5 Source or project root.
        cpp_class:    Optional C++ class name to filter. If None, returns full project map.
    """
    if not _UE5_BP_MAPPING_AVAILABLE:
        return "ue5_blueprint_mapping module not available."
    try:
        from gdep.ue5_blueprint_mapping import build_bp_map, format_full_project_map
        bp_map = build_bp_map(project_path)
        if not bp_map.blueprints:
            return (
                f"No Blueprint assets found for project at '{project_path}'.\n"
                "Check that the Content folder exists and LFS assets are pulled."
            )
        return format_full_project_map(bp_map, cpp_class)
    except Exception as e:
        return f"[analyze_ue5_blueprint_mapping] Error: {e}"


@mcp.tool()
def get_architecture_advice(project_path: str, focus_class: str | None = None) -> str:
    """Diagnose the architecture of a game project and suggest improvements.

    Combines scan + lint + impact analysis into a single prioritized advice report.
    Results cached in .gdep/cache/advice.md.

    USE THIS TOOL WHEN:
    - User asks "what is the technical debt in this project?"
    - User asks "what should I refactor first?" or "give me refactoring priorities"

    Args:
        project_path: Absolute path to the project root or source directory.
        focus_class:  Optional class to center advice around. If None, uses highest-coupling class.
    """
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


if __name__ == "__main__":
    mcp.run()
