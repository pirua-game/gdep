"""
gdep.agent  —  v2  (27단계 업데이트)
Multi-provider LLM Agent with full tool coverage.

변경 사항:
- TOOLS: GAS / ABP / BT / StateTree / BP매핑 / blueprint_refs 도구 추가 (총 16개)
- 시스템 프롬프트: 엔진별 전략 가이드 강화
- tool_call 파싱: content/tool_calls 양쪽 robust하게 처리
- ToolExecutor: 신규 도구 실행 연결 + 결과 요약 개선
"""
from __future__ import annotations

import json
import re as _re
from collections.abc import Generator

from . import runner
from .detector import detect
from .llm_provider import LLMConfig
from .llm_provider import chat as llm_chat
from .source_reader import find_class_files, format_for_llm

# ── Parse tool calls from content ─────────────────────────────

def _parse_tool_calls_from_text(text: str) -> list[dict]:
    if not text or not text.strip():
        return []
    # JSON 블록 우선 탐색
    for block in _re.findall(r"```(?:json)?\s*([\s\S]*?)```", text):
        block = block.strip()
        try:
            data = json.loads(block)
            items = data if isinstance(data, list) else [data]
            calls = _extract_calls(items)
            if calls:
                return calls
        except Exception:
            pass
    # 블록 없으면 raw JSON 탐색
    for m in _re.finditer(r'(\{[\s\S]*?\})', text):
        try:
            data = json.loads(m.group(1))
            calls = _extract_calls([data])
            if calls:
                return calls
        except Exception:
            pass
    return []


def _extract_calls(items: list) -> list[dict]:
    result = []
    for item in items:
        name = item.get("name") or item.get("function", {}).get("name") or item.get("tool")
        args = (item.get("arguments") or item.get("parameters")
                or item.get("args") or item.get("input") or {})
        if name:
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            result.append({"function": {"name": name, "arguments": args}})
    return result

# ── Tool Definitions (16개) ────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "scan",
            "description": "Analyze project dependencies. Returns top coupled classes, circular refs, dead code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "circular":     {"type": "boolean", "description": "Include circular references (default: true)"},
                    "dead_code":    {"type": "boolean", "description": "Detect unreferenced classes (default: false)"},
                    "deep":         {"type": "boolean", "description": "Deep analysis including method bodies (default: false)"},
                    "include_refs": {"type": "boolean", "description": "Include engine asset back-references (default: false)"},
                    "top":          {"type": "integer", "description": "Top N classes to output (default: 20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe",
            "description": "Returns fields, methods, and dependencies of a class. Call this before read_source.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Class name"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_source",
            "description": "Returns actual source code of a class. Supports C# partial classes and C++ .h/.cpp pairs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string"},
                    "max_chars":  {"type": "integer", "description": "Max characters (default: 8000, max: 15000)"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flow",
            "description": "Traces method call chains. Includes lock/async/dynamic dispatch boundaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name":    {"type": "string"},
                    "method_name":   {"type": "string"},
                    "depth":         {"type": "integer", "description": "Trace depth (default: 2, max: 3)"},
                    "focus_classes": {"type": "string", "description": "Classes to focus on (comma-separated)"},
                },
                "required": ["class_name", "method_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "impact",
            "description": "Reverse-traces the blast radius of a class change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_class": {"type": "string"},
                    "depth":        {"type": "integer", "description": "Analysis depth (default: 3)"},
                },
                "required": ["target_class"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lint",
            "description": "Scans for game-engine-specific anti-patterns. Includes UNI-PERF, UE5-GAS, UE5-NET rules.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "graph",
            "description": "Returns the dependency graph in Mermaid format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cycles_only": {"type": "boolean", "description": "Show only circular references (default: true)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diff",
            "description": "Compares dependency changes between git commits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commit": {"type": "string", "description": "git commit hash or branch name"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_prefab_refs",
            "description": "[Unity only] Finds which Prefab/Scene a MonoBehaviour class is attached to.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_blueprint_refs",
            "description": "[UE5 only] Finds Blueprint/Map .uasset files that inherit or reference a C++ class.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string"},
                },
                "required": ["class_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_gas",
            "description": "[UE5 only] Analyzes full GAS structure: GameplayAbility / GameplayEffect / AttributeSet / GameplayTag.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_name": {"type": "string", "description": "Filter by specific class (omit for all)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_animation",
            "description": "[UE5 only] Analyzes AnimBlueprint (ABP) state machines and AnimMontage structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_type":   {"type": "string", "enum": ["all", "abp", "montage"], "description": "Asset type to analyze (default: all)"},
                    "asset_name":   {"type": "string", "description": "Filter by specific asset name"},
                    "detail_level": {"type": "string", "enum": ["summary", "full"], "description": "Detail level (default: summary)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_behavior_tree",
            "description": "[UE5 only] Analyzes BehaviorTree (BT_*) asset: Task/Decorator/Service/Blackboard structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_name": {"type": "string", "description": "Filter by specific BT asset name"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_state_tree",
            "description": "[UE5 only] Analyzes StateTree (ST_*) assets and AIController connection structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_name": {"type": "string", "description": "Filter by specific ST asset name"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "blueprint_mapping",
            "description": "[UE5 only] Maps C++ classes to Blueprint implementations. Includes K2 overrides, variables, GameplayTags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cpp_class": {"type": "string", "description": "C++ class name (omit for whole project)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unity_events",
            "description": "[Unity only] Detects Inspector event binding methods in Prefab/Scene/Asset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method_name": {"type": "string", "description": "Filter by method name (omit for all)"},
                },
                "required": [],
            },
        },
    },
]


# ── ToolExecutor ───────────────────────────────────────────────

class ToolExecutor:
    def __init__(self, scripts_path: str):
        self.scripts_path = scripts_path
        self.profile      = detect(scripts_path)
        self._cache:      dict[str, str] = {}

    def _cache_key(self, name: str, args: dict) -> str:
        return f"{name}:{json.dumps(args, sort_keys=True)}"

    def execute(self, tool_name: str, args: dict) -> str:
        key = self._cache_key(tool_name, args)
        if key in self._cache:
            return f"[cached] Previous result:\n{self._cache[key]}"

        out = self._run(tool_name, args)
        self._cache[key] = out
        return out

    def _run(self, tool_name: str, args: dict) -> str:  # noqa: C901
        p = self.profile

        if tool_name == "scan":
            r = runner.scan(p, circular=args.get("circular", True),
                            dead_code=args.get("dead_code", False),
                            deep=args.get("deep", False),
                            include_refs=args.get("include_refs", False),
                            top=args.get("top", 20))
            out = r.stdout if r.ok else f"Error: {r.error_message}"
            return out[:2500] + "\n[truncated...]" if len(out) > 2500 else out

        elif tool_name == "describe":
            r = runner.describe(p, class_name=args["class_name"])
            return _summarize_describe(r.stdout) if r.ok else f"Error: {r.error_message}"

        elif tool_name == "read_source":
            max_chars = min(args.get("max_chars", 8000), 15000)
            r = runner.read_source(p, args["class_name"], max_chars=max_chars)
            if r.ok:
                return r.stdout
            sr = find_class_files(self.scripts_path, args["class_name"])
            if sr.chunks:
                out = format_for_llm(sr, max_chars=max_chars)
                prefix = f"partial class ({sr.total_parts} files)\n\n" if sr.is_partial else ""
                return prefix + out
            return f"Source file not found: `{args['class_name']}`"

        elif tool_name == "flow":
            focus = [f.strip() for f in args["focus_classes"].split(",")
                     ] if args.get("focus_classes") else None
            r = runner.flow(p, class_name=args["class_name"],
                            method_name=args["method_name"],
                            depth=min(args.get("depth", 2), 3),
                            focus_classes=focus, fmt="json")
            return _summarize_flow(r.stdout) if r.ok else f"Error: {r.error_message}"

        elif tool_name == "impact":
            r = runner.impact(p, target_class=args["target_class"],
                              depth=args.get("depth", 3))
            out = r.stdout if r.ok else f"Error: {r.error_message}"
            return out[:2500] + "\n[truncated...]" if len(out) > 2500 else out

        elif tool_name == "lint":
            r = runner.lint(p)
            out = r.stdout if r.ok else f"Error: {r.error_message}"
            return out[:2500] + "\n[truncated...]" if len(out) > 2500 else out

        elif tool_name == "graph":
            r = runner.graph(p, fmt="mermaid",
                             cycles_only=args.get("cycles_only", True))
            out = r.stdout if r.ok else f"Error: {r.error_message}"
            return out[:1500] + "\n[truncated...]" if len(out) > 1500 else out

        elif tool_name == "diff":
            r = runner.diff(p, commit=args.get("commit"))
            out = r.stdout if r.ok else f"Error: {r.error_message}"
            return out[:2000] + "\n[truncated...]" if len(out) > 2000 else out

        elif tool_name == "find_prefab_refs":
            from .unity_refs import build_ref_map, format_ref_result
            ref_map = build_ref_map(self.scripts_path)
            if ref_map is None:
                return "Not a Unity project or Assets folder not found."
            ref = ref_map.get(args["class_name"])
            return format_ref_result(ref, args["class_name"])

        elif tool_name == "find_blueprint_refs":
            from .ue5_blueprint_refs import build_ref_map, format_ref_result
            ref_map = build_ref_map(self.scripts_path)
            if ref_map is None:
                return "Not a UE5 project or Content folder not found."
            ref = ref_map.get(args["class_name"])
            return format_ref_result(ref, args["class_name"])

        elif tool_name == "analyze_gas":
            from .ue5_gas_analyzer import analyze_gas
            return analyze_gas(self.scripts_path, args.get("class_name"))

        elif tool_name == "analyze_animation":
            from .ue5_animator import analyze_abp, analyze_montage
            t = args.get("asset_type", "all")
            n = args.get("asset_name")
            d = args.get("detail_level", "summary")
            if t == "abp":
                return analyze_abp(self.scripts_path, n)
            elif t == "montage":
                return analyze_montage(self.scripts_path, n)
            return analyze_abp(self.scripts_path, n) + "\n\n" + analyze_montage(self.scripts_path, n)

        elif tool_name == "analyze_behavior_tree":
            from .ue5_ai_analyzer import analyze_behavior_tree
            return analyze_behavior_tree(self.scripts_path, args.get("asset_name"))

        elif tool_name == "analyze_state_tree":
            from .ue5_ai_analyzer import analyze_state_tree
            return analyze_state_tree(self.scripts_path, args.get("asset_name"))

        elif tool_name == "blueprint_mapping":
            from .ue5_blueprint_mapping import (
                build_bp_map,
                format_cpp_to_bps,
                format_full_project_map,
            )
            bp_map = build_bp_map(self.scripts_path)
            cpp_class = args.get("cpp_class")
            if cpp_class:
                bps: list = []
                seen: set = set()
                for c in _cpp_variants(cpp_class):
                    for m in bp_map.cpp_to_bps.get(c, []):
                        if m.bp_class not in seen:
                            seen.add(m.bp_class)
                            bps.append(m)
                return format_cpp_to_bps(cpp_class, bps)
            return format_full_project_map(bp_map)

        elif tool_name == "unity_events":
            from .unity_event_refs import build_event_map, format_event_result
            event_map = build_event_map(self.scripts_path)
            return format_event_result(event_map, args.get("method_name"))

        return f"Unknown tool: {tool_name}"


def _cpp_variants(name: str) -> list[str]:
    variants = [name]
    for prefix in ('A', 'U', 'F', 'I', 'E'):
        if name.startswith(prefix):
            variants.append(name[1:])
        else:
            variants.append(prefix + name)
    return variants


# ── Summary Utilities ──────────────────────────────────────────

def _summarize_flow(stdout: str) -> str:
    j = stdout.find("{")
    if j == -1:
        return stdout[:1200]
    try:
        data = json.loads(stdout[j:stdout.rfind("}")+1])
    except Exception:
        return stdout[:1200]
    nodes      = data.get("nodes", [])
    edges      = data.get("edges", [])
    dispatches = data.get("dispatches", [])
    bp_bridge  = data.get("bpBridge", False)

    lines = [
        f"## Flow: {data.get('entry', '?')}",
        f"Nodes {len(nodes)} / Edges {len(edges)} / Dispatches {len(dispatches)}"
        + (" / BP bridge" if bp_bridge else ""),
        "", "### Key call relationships",
    ]
    seen: set[str] = set()
    for e in edges[:40]:
        ctx = e.get("context") or ("dispatch" if e.get("isDynamic") else "")
        bp  = " [BP]" if e.get("isBlueprintNode") or ctx == "blueprint" else ""
        k   = f"{e['from']}→{e['to']}"
        if k in seen:
            continue
        seen.add(k)
        lines.append(f"- {e['from'].split('.')[-1]} → {e['to'].split('.')[-1]}"
                     + (f" [{ctx}]" if ctx else "") + bp)
    if dispatches:
        lines += ["", "### Dynamic dispatches"]
        for d in dispatches[:8]:
            lines.append(f"- {d['from']}: {d['handler']}")
    return "\n".join(lines)


def _summarize_describe(stdout: str) -> str:
    lines  = stdout.splitlines()
    result = []
    count  = 0
    for line in lines:
        s = line.strip()
        if "──" in s:
            result.append(s); count = 0; continue
        if s and count < 15:
            result.append(line); count += 1
        elif count == 15:
            result.append("  ... (truncated)"); count += 1
    out = "\n".join(result)
    return out[:2500] if len(out) > 2500 else out


def ensure_hints(scripts_path: str) -> str | None:
    from pathlib import Path
    profile    = detect(scripts_path)
    hints_path = Path(profile.root) / ".gdep" / ".gdep-hints.json"
    if hints_path.exists():
        return None
    result = runner.hints_generate(profile)
    return str(hints_path) if (result.ok and hints_path.exists()) else None


# ── gdepAgent ─────────────────────────────────────────────────

class gdepAgent:
    def __init__(
        self,
        scripts_path: str,
        model:        str = "qwen2.5-coder:14b",
        ollama_url:   str = "http://localhost:11434",
        llm_config:   LLMConfig | None = None,
    ):
        self.scripts_path = scripts_path
        self.executor     = ToolExecutor(scripts_path)
        self._history:    list[dict] = []
        self._default_cfg = llm_config or LLMConfig(
            provider="ollama", model=model, base_url=ollama_url
        )

    def reset_history(self) -> None:
        self._history = []

    @property
    def history(self) -> list[dict]:
        return self._history

    def _build_system_prompt(self, max_calls: int) -> str:
        profile = self.executor.profile
        src     = str(profile.source_dirs[0]) if profile.source_dirs else str(profile.root)
        engine  = profile.display

        # 엔진별 전략 힌트
        if "Unity" in engine:
            engine_guide = """
## Unity Analysis Strategy
1. Use describe -> read_source -> flow in order
2. Check Inspector event bindings with unity_events
3. Find which Prefab a component is attached to with find_prefab_refs
4. Detect Update/Tick anti-patterns with lint"""
        elif "Unreal" in engine or "UE5" in engine:
            engine_guide = """
## UE5 Analysis Strategy
1. Use describe -> read_source -> flow in order
2. Call analyze_gas first for a full picture of the GAS system
3. Check Blueprint implementations of C++ classes with blueprint_mapping
4. Analyze ABP/Montage structure with analyze_animation
5. Check AI behavior trees with analyze_behavior_tree
6. Find C++ classes referenced by Blueprints with find_blueprint_refs"""
        else:
            engine_guide = ""

        return f"""You are an expert game client codebase analyst.
Project: {profile.name} ({engine})
Analysis path: {src}
{engine_guide}

## Available tools (16)
**Common**: scan, describe, read_source, flow, impact, lint, graph, diff
**Unity only**: find_prefab_refs, unity_events
**UE5 only**: find_blueprint_refs, analyze_gas, analyze_animation, analyze_behavior_tree, analyze_state_tree, blueprint_mapping

## Rules
- Do not call the same tool with the same arguments more than once
- Provide your final answer in English after gathering sufficient information
- Maximum {max_calls} tool calls allowed
- Remember prior conversation context and respond consistently
- When analyzing code, always confirm with read_source before drawing conclusions"""

    def run(
        self,
        user_question: str,
        max_tool_calls: int = 6,
        llm_config: LLMConfig | None = None,
    ) -> Generator[dict, None, None]:
        cfg     = llm_config or self._default_cfg
        system  = self._build_system_prompt(max_tool_calls)
        use_native_tools = cfg.provider in ("ollama", "openai", "anthropic")

        self._history.append({"role": "user", "content": user_question})
        messages = [{"role": "system", "content": system}] + self._history
        call_count = 0

        while call_count < max_tool_calls:
            try:
                response = llm_chat(cfg, messages,
                                    tools=TOOLS if use_native_tools else None)
            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return

            message    = response.get("message", {})
            tool_calls = message.get("tool_calls") or []

            # Fallback: text 안에 JSON tool call이 있는 경우
            if not tool_calls:
                tool_calls = _parse_tool_calls_from_text(message.get("content", ""))

            # 도구 호출 없으면 최종 답변
            if not tool_calls:
                content = message.get("content", "")
                self._history.append({"role": "assistant", "content": content})
                yield {"type": "answer", "content": content}
                return

            messages.append({
                "role":       "assistant",
                "content":    message.get("content", ""),
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                func      = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        args = json.loads(args)
                except Exception:
                    args = {}

                yield {
                    "type":     "tool_call",
                    "tool":     tool_name,
                    "args":     args,
                    "call_num": call_count + 1,
                }

                result  = self.executor.execute(tool_name, args)
                preview = result
                if tool_name == "read_source" and len(result) > 400:
                    lines   = result.splitlines()
                    preview = "\n".join(lines[:10]) + f"\n... ({len(lines)} lines total)"

                yield {"type": "tool_result", "tool": tool_name, "result": preview}
                messages.append({"role": "tool", "content": result})
                call_count += 1

        # 최대 호출 도달 → 마지막으로 답변 요청
        messages.append({
            "role":    "user",
            "content": "Based on the information gathered so far, provide your final analysis in English.",
        })
        try:
            response = llm_chat(cfg, messages, tools=None)
            content  = response.get("message", {}).get("content", "")
            self._history.append({"role": "assistant", "content": content})
            yield {"type": "answer", "content": content}
        except Exception as e:
            yield {"type": "error", "message": str(e)}
