"""
gdep.analyzer.pattern_detector
Game engine design pattern detection.

Identifies common architectural patterns used in the project code.
Unlike the linter (which finds anti-patterns), this module detects
*positive* patterns to help understand the codebase architecture.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatternMatch:
    """A detected design pattern in the codebase."""
    pattern_name: str
    category: str       # "architecture", "lifecycle", "communication", "data"
    class_name: str
    file_path: str = ""
    details: str = ""   # Additional context about how the pattern is used
    confidence: str = "high"  # "high", "medium", "low"


# ── UE5 Patterns ─────────────────────────────────────────────

def detect_ue5_patterns(project: Any) -> list[PatternMatch]:
    """Detect common UE5 architectural patterns in parsed project."""
    results: list[PatternMatch] = []
    all_items = {**project.classes, **project.structs}

    for cls_name, cls in all_items.items():
        bases = getattr(cls, 'bases', [])
        functions = getattr(cls, 'functions', [])
        properties = getattr(cls, 'properties', [])
        specifiers = getattr(cls, 'specifiers', [])
        file_path = getattr(cls, 'source_file', '')
        func_names = {f.name for f in functions}

        # ── Subsystem Pattern ──
        if any('Subsystem' in b for b in bases):
            results.append(PatternMatch(
                pattern_name="Subsystem Pattern",
                category="architecture",
                class_name=cls_name,
                file_path=file_path,
                details=f"Inherits from {', '.join(b for b in bases if 'Subsystem' in b)}. "
                        f"Engine-managed singleton-like service.",
            ))

        # ── Component Composition ──
        comp_props = [p for p in properties
                      if 'Component' in getattr(p, 'type_', '')]
        if comp_props:
            results.append(PatternMatch(
                pattern_name="Component Composition",
                category="architecture",
                class_name=cls_name,
                file_path=file_path,
                details=f"{len(comp_props)} component(s): "
                        f"{', '.join(p.name + ':' + p.type_ for p in comp_props[:5])}",
            ))

        # ── GAS Ability Pattern ──
        if any('GameplayAbility' in b for b in bases):
            results.append(PatternMatch(
                pattern_name="GAS Ability",
                category="architecture",
                class_name=cls_name,
                file_path=file_path,
                details="Gameplay Ability System ability class.",
            ))

        # ── GAS Attribute Set ──
        if any('AttributeSet' in b for b in bases):
            attr_props = [p for p in properties
                          if 'FGameplayAttributeData' in getattr(p, 'type_', '')]
            results.append(PatternMatch(
                pattern_name="GAS Attribute Set",
                category="data",
                class_name=cls_name,
                file_path=file_path,
                details=f"{len(attr_props)} gameplay attribute(s).",
            ))

        # ── Event Delegate Pattern ──
        delegate_props = [p for p in properties
                          if any(kw in getattr(p, 'type_', '')
                                 for kw in ('Delegate', 'FOn', 'Event', 'Multicast'))]
        if delegate_props:
            results.append(PatternMatch(
                pattern_name="Event Delegate",
                category="communication",
                class_name=cls_name,
                file_path=file_path,
                details=f"{len(delegate_props)} delegate(s): "
                        f"{', '.join(p.name for p in delegate_props[:5])}",
            ))

        # ── Replication Pattern ──
        replicated = [p for p in properties if getattr(p, 'is_replicated', False)]
        if replicated:
            has_rep_callback = any('OnRep_' in f.name for f in functions)
            results.append(PatternMatch(
                pattern_name="Network Replication",
                category="communication",
                class_name=cls_name,
                file_path=file_path,
                details=f"{len(replicated)} replicated prop(s), "
                        f"{'with' if has_rep_callback else 'without'} OnRep callbacks.",
            ))

        # ── Interface Implementation ──
        interfaces = [b for b in bases if b.startswith('I') and len(b) > 1
                      and b[1].isupper()]
        if interfaces:
            results.append(PatternMatch(
                pattern_name="Interface Implementation",
                category="architecture",
                class_name=cls_name,
                file_path=file_path,
                details=f"Implements: {', '.join(interfaces)}",
            ))

        # ── Behavior Tree Task/Service/Decorator ──
        bt_bases = [b for b in bases
                    if any(kw in b for kw in ('BTTask', 'BTService', 'BTDecorator'))]
        if bt_bases:
            results.append(PatternMatch(
                pattern_name="Behavior Tree Node",
                category="architecture",
                class_name=cls_name,
                file_path=file_path,
                details=f"AI BT node type: {', '.join(bt_bases)}",
            ))

    return results


# ── Unity Patterns ────────────────────────────────────────────

def detect_unity_patterns(source_path: str) -> list[PatternMatch]:
    """Detect common Unity C# patterns by scanning source files."""
    from pathlib import Path
    results: list[PatternMatch] = []
    src_root = Path(source_path)

    _re_class = re.compile(r'class\s+(\w+)\s*(?::\s*(.+?))?(?:\{|$)', re.MULTILINE)
    _re_singleton = re.compile(r'static\s+\w+\s+(?:Instance|instance|_instance)\b')
    _re_event = re.compile(r'\bUnityEvent|event\s+\w+|Action<')
    _re_coroutine = re.compile(r'IEnumerator\s+\w+')
    _re_pool = re.compile(r'Queue<|Stack<|pool|Pool', re.IGNORECASE)
    _re_observer = re.compile(r'OnNotify|Subscribe|AddListener|observer', re.IGNORECASE)
    _re_state_machine = re.compile(r'enum\s+\w*State|currentState|_state\s*=', re.IGNORECASE)
    _re_scriptable = re.compile(r':\s*ScriptableObject\b')

    _IGNORE_DIRS = {"packages", "library", "temp", "obj", ".git"}

    for cs_file in src_root.rglob("*.cs"):
        if any(p.lower() in _IGNORE_DIRS for p in cs_file.parts):
            continue
        try:
            content = cs_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Find class definitions
        for cm in _re_class.finditer(content):
            cls_name = cm.group(1)
            bases_str = cm.group(2) or ""

            # MonoBehaviour lifecycle
            if 'MonoBehaviour' in bases_str:
                # Singleton Pattern
                if _re_singleton.search(content):
                    results.append(PatternMatch(
                        pattern_name="Singleton Pattern",
                        category="architecture",
                        class_name=cls_name,
                        file_path=str(cs_file),
                        details="Static Instance field detected in MonoBehaviour.",
                    ))

                # Coroutine State Machine
                coroutines = _re_coroutine.findall(content)
                if len(coroutines) >= 2:
                    results.append(PatternMatch(
                        pattern_name="Coroutine Workflow",
                        category="lifecycle",
                        class_name=cls_name,
                        file_path=str(cs_file),
                        details=f"{len(coroutines)} coroutine(s) detected.",
                    ))

            # ScriptableObject Data Pattern
            if _re_scriptable.search(bases_str):
                results.append(PatternMatch(
                    pattern_name="ScriptableObject Data",
                    category="data",
                    class_name=cls_name,
                    file_path=str(cs_file),
                    details="Data container using ScriptableObject pattern.",
                ))

            # Event/Observer Pattern
            if _re_event.search(content) or _re_observer.search(content):
                results.append(PatternMatch(
                    pattern_name="Event/Observer",
                    category="communication",
                    class_name=cls_name,
                    file_path=str(cs_file),
                    details="Uses UnityEvent, C# events, or observer pattern.",
                    confidence="medium",
                ))

            # Object Pooling
            if _re_pool.search(content):
                results.append(PatternMatch(
                    pattern_name="Object Pooling",
                    category="architecture",
                    class_name=cls_name,
                    file_path=str(cs_file),
                    details="Pool-related data structures detected.",
                    confidence="medium",
                ))

            # State Machine
            if _re_state_machine.search(content):
                results.append(PatternMatch(
                    pattern_name="State Machine",
                    category="architecture",
                    class_name=cls_name,
                    file_path=str(cs_file),
                    details="State enum or state variable detected.",
                    confidence="medium",
                ))

    return results


# ── Formatting ────────────────────────────────────────────────

def format_patterns(patterns: list[PatternMatch], max_results: int = 30) -> str:
    """Format detected patterns as console text."""
    if not patterns:
        return "No design patterns detected in the project."

    # Group by category
    by_category: dict[str, list[PatternMatch]] = {}
    for p in patterns:
        by_category.setdefault(p.category, []).append(p)

    # Summary
    by_name: dict[str, int] = {}
    for p in patterns:
        by_name[p.pattern_name] = by_name.get(p.pattern_name, 0) + 1

    lines = [
        f"┌─ Design Pattern Analysis {'─' * 38}┐",
        f"│ Total patterns detected: {len(patterns)}",
        f"│ Unique pattern types:    {len(by_name)}",
        f"└{'─' * 60}┘",
        "",
        "── Pattern Summary ──",
    ]
    for name, count in sorted(by_name.items(), key=lambda x: -x[1]):
        lines.append(f"  {name:<35} {count:>3} occurrence(s)")

    lines.append("")
    shown = 0
    for category in ("architecture", "communication", "lifecycle", "data"):
        items = by_category.get(category, [])
        if not items:
            continue
        lines.append(f"── {category.title()} Patterns ──")
        for p in items:
            if max_results > 0 and shown >= max_results:
                break
            file_name = Path(p.file_path).name if p.file_path else ""
            lines.append(f"  • {p.pattern_name}: {p.class_name}  ({file_name})")
            if p.details:
                lines.append(f"    {p.details}")
            shown += 1
        lines.append("")

    remaining = len(patterns) - shown
    if remaining > 0:
        lines.append(f"... {remaining} more pattern(s) omitted"
                     f" (use max_results=0 to see all)")

    return "\n".join(lines)


# Need Path for format_patterns
from pathlib import Path
