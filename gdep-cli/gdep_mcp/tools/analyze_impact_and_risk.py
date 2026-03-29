"""
gdep-mcp/tools/analyze_impact_and_risk.py

High-level tool: 특정 클래스 수정 전 파급 효과 + 안티패턴 통합 진단.
runner.impact + runner.lint 결합.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# gdep 패키지 경로를 sys.path에 추가 (gdep-mcp는 gdep-cli 하위에 위치)
_GDEP_ROOT = Path(__file__).parent.parent.parent
if str(_GDEP_ROOT) not in sys.path:
    sys.path.insert(0, str(_GDEP_ROOT))

from gdep import runner
from gdep.confidence import ConfidenceTier, confidence_footer
from gdep.detector import detect


def run(project_path: str, class_name: str,
        method_name: str | None = None,
        detail_level: str = "full",
        query: str | None = None,
        max_results: int = 0) -> str:
    """
    Analyze the impact and risks of modifying a specific class (or method) before making changes.

    Combines reverse-dependency tracing (who calls this class, what assets use it)
    with engine-specific anti-pattern scanning (lint rules).

    Use this tool BEFORE modifying or refactoring a class to understand:
    - Which classes and assets will be affected (blast radius)
    - Whether the target class already has known anti-patterns
    - (Optional) Which specific methods call the target method

    Args:
        project_path: Absolute path to the project root or Scripts/Source directory.
                      Examples: "D:/MyGame/Assets/Scripts" (Unity),
                                "F:/MyGame/Source/MyGame" (UE5)
        class_name:   The C++ or C# class name to analyze.
                      Examples: "BattleManager", "APlayerCharacter"
        method_name:  Optional. If provided, also traces method-level callers
                      of class_name::method_name across the project.
                      Examples: "checkCollision", "Update"
        detail_level: "summary" — affected class count + top-5 risk items (fast, low token).
                      "full"    — full impact tree + all lint issues (default).
        query:        Optional class/pattern filter. Only results containing this string
                      are included. Useful for narrowing large codebases.
        max_results:  Maximum number of lint issues to show (default 0 = auto:
                      5 for summary, 20 for full). Useful for controlling output size.

    Returns:
        A report containing:
        - Impact tree (or summary): which classes/prefabs/blueprints depend on this class
        - Method-level callers (if method_name is provided)
        - Lint results: anti-patterns found in or around this class
    """
    if not class_name or not class_name.strip():
        return "[analyze_impact_and_risk] Error: class_name must not be empty."

    try:
        profile = detect(project_path)
        sections: list[str] = []
        is_summary = detail_level.lower() == "summary"

        # ── Impact Analysis ──────────────────────────────────────────
        impact_result = runner.impact(profile, class_name, depth=4)
        sections.append("## Impact Analysis")
        if impact_result.ok:
            impact_text = impact_result.stdout
            if query:
                impact_lines = [l for l in impact_text.splitlines()
                                if query.lower() in l.lower() or not l.strip()]
                impact_text = "\n".join(impact_lines)
            if is_summary:
                impact_text = _summarize_impact(impact_text)
            sections.append(impact_text)
        else:
            sections.append(f"Impact analysis failed: {impact_result.error_message}")

        # ── Method-Level Impact (optional) ─────────────────────────
        if method_name:
            try:
                method_result = runner.method_impact(profile, class_name,
                                                     method_name, depth=4)
                sections.append("\n## Method-Level Impact")
                if method_result.ok:
                    sections.append(method_result.stdout)
                else:
                    sections.append(f"Method impact failed: {method_result.error_message}")
            except Exception as me:
                sections.append(f"\n## Method-Level Impact\nError: {me}")

        # ── Asset Cross-Reference (Source ↔ Asset) ──────────────────
        _append_asset_crossref(sections, profile, class_name, is_summary)

        # ── Lint Analysis ────────────────────────────────────────────
        lint_result = runner.lint(profile, fmt="json")
        sections.append("\n## Lint / Anti-pattern Scan")
        if lint_result.ok:
            try:
                issues = json.loads(lint_result.stdout) if lint_result.stdout else []
                # Filter to issues related to the target class (if possible)
                related = [i for i in issues
                           if i.get("class_name", "").lower() == class_name.lower()]
                all_issues = related if related else issues

                # Apply query filter
                if query:
                    q = query.lower()
                    all_issues = [i for i in all_issues
                                  if q in i.get("class_name", "").lower()
                                  or q in i.get("message", "").lower()
                                  or q in i.get("rule_id", "").lower()]

                limit = max_results if max_results > 0 else (5 if is_summary else 20)
                if not all_issues:
                    sections.append("✓ No anti-patterns detected.")
                else:
                    if is_summary:
                        # severity breakdown + top items
                        by_sev: dict[str, int] = {}
                        for i in all_issues:
                            sev = i.get("severity", "unknown")
                            by_sev[sev] = by_sev.get(sev, 0) + 1
                        sev_str = ", ".join(f"{v} {k}" for k, v in sorted(by_sev.items()))
                        sections.append(f"Total: {len(all_issues)} issues ({sev_str})")
                        sections.append("Top issues:")
                    for issue in all_issues[:limit]:
                        loc = f"{issue.get('class_name','?')}.{issue.get('method_name','')}"
                        sections.append(
                            f"- [{issue.get('severity','?')}] {loc}: "
                            f"{issue.get('message','')} "
                            f"(Rule: {issue.get('rule_id','')})"
                        )
                    if len(all_issues) > limit:
                        sections.append(f"... and {len(all_issues)-limit} more issues"
                                        + (" (use detail_level='full' to see all)" if is_summary else ""))
            except (json.JSONDecodeError, TypeError):
                sections.append(lint_result.stdout or "No lint output")
        else:
            sections.append(f"Lint failed: {lint_result.error_message}")

        return "\n".join(sections) + confidence_footer(ConfidenceTier.HIGH, "reverse dependency graph")

    except Exception as e:
        return f"[analyze_impact_and_risk] Error: {e}"


def _summarize_impact(impact_text: str) -> str:
    """Condense impact output to class count + first 5 affected class names."""
    lines = impact_text.splitlines()
    class_lines = [l for l in lines if l.strip() and not l.startswith("#")]
    total = len(class_lines)
    preview = "\n".join(class_lines[:5])
    suffix = f"\n... and {total - 5} more affected classes (use detail_level='full' to see all)" if total > 5 else ""
    header = f"Affected classes: {total}\n"
    return header + preview + suffix


def _append_asset_crossref(sections: list[str], profile, class_name: str,
                            is_summary: bool) -> None:
    """Add Source ↔ Asset cross-reference section if applicable."""
    from gdep.detector import ProjectKind

    try:
        if profile.kind == ProjectKind.UNREAL:
            try:
                from gdep.ue5_blueprint_mapping import build_bp_map
                src = str(profile.source_dirs[0]) if profile.source_dirs else str(profile.root)
                bp_map = build_bp_map(src)
                if not bp_map:
                    return

                # Find Blueprints that reference this C++ class
                matching_bps: list[str] = []
                for bp_path, bp_info in bp_map.blueprints.items():
                    cpp_parent = getattr(bp_info, 'cpp_parent', '')
                    if not cpp_parent:
                        continue
                    # Match with or without UE prefix (U/A/F/I)
                    def _strip_ue_prefix(n: str) -> str:
                        return n[1:] if len(n) > 1 and n[0] in 'UAFI' else n
                    if (cpp_parent == class_name or
                        _strip_ue_prefix(cpp_parent) == _strip_ue_prefix(class_name)):
                        matching_bps.append(bp_path)

                if matching_bps:
                    sections.append("\n## Blueprint Assets Referencing This Class")
                    if is_summary:
                        sections.append(f"Found **{len(matching_bps)}** Blueprint(s) "
                                       f"using {class_name} as parent class.")
                    else:
                        for bp in matching_bps[:20]:
                            bp_name = bp.split('/')[-1] if '/' in bp else bp
                            sections.append(f"  └── {bp_name}  ({bp})")
                        if len(matching_bps) > 20:
                            sections.append(f"  ... {len(matching_bps) - 20} more")
            except ImportError:
                pass

        elif profile.kind == ProjectKind.UNITY:
            try:
                from gdep import unity_refs
                src = str(profile.source_dirs[0]) if profile.source_dirs else str(profile.root)
                ref_map = unity_refs.build_ref_map(src)
                if not ref_map:
                    return

                ref = ref_map.get(class_name)
                if ref and ref.usages:
                    sections.append("\n## Unity Assets Referencing This Class")
                    if is_summary:
                        sections.append(f"Found **{len(ref.usages)}** asset reference(s) "
                                       f"to {class_name}.")
                    else:
                        for usage in sorted(ref.usages)[:20]:
                            sections.append(f"  └── {usage}")
                        if len(ref.usages) > 20:
                            sections.append(f"  ... {len(ref.usages) - 20} more")
            except ImportError:
                pass

    except Exception:
        pass  # Non-critical — silently skip
