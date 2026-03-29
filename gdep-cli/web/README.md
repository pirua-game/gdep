# gdep Web UI

A browser-based interface for [gdep](../../README.md) — interactive visualization and AI-powered analysis for game codebases (Unity · UE5 · Axmol · C++).

---

## Overview

The gdep Web UI wraps the gdep CLI into a local web application, replacing terminal output with:

- Interactive dependency graphs and call-flow diagrams
- Real-time file-watch panel that auto-analyzes on every save
- AI chat agent with tool-calling against your actual codebase
- Engine-specific explorers (UE5 GAS, Blueprint mapping, Animator, BehaviorTree …)
- Pattern detection, unused asset scanning, and API-level code search

**Stack:** React 19 + TypeScript + Vite + TailwindCSS (frontend) · FastAPI + Python (backend)

---

## Quick Start

### One-Click (Recommended)

**Step 1 — Install** (run once from project root)

```
# Windows
install.bat

# macOS / Linux
chmod +x install.sh && ./install.sh
```

**Step 2 — Launch**

```
# Windows — opens backend + frontend in two separate terminals automatically
run.bat

# macOS / Linux — run in two separate terminals
./run.sh          # Terminal 1: backend  (port 8000)
./run_front.sh    # Terminal 2: frontend (port 5173)
```

Open `http://localhost:5173` in your browser and point the sidebar to your project's scripts folder.

| URL | Service |
|-----|---------|
| `http://localhost:5173` | Frontend (Web UI) |
| `http://localhost:8000` | Backend API |

> **Note:** This is a non-commercial tool under active development — some features may not be perfect.
> UI language support: **English and Korean only**.
> Local LLM: **Ollama** is supported — start `ollama serve` and select it in the sidebar LLM settings.

---

### Manual Setup (Development)

```bash
# 1. Install backend dependencies
cd backend
pip install -r requirements.txt

# 2. Start backend (port 8000)
uvicorn main:app --reload

# 3. In a second terminal — install and start frontend (port 5173)
cd ../frontend
npm install
npm run dev
```

---

## Features

The UI is organized into **6 main tabs**.

### 1. Class Browser

Explore every class in your project without opening an IDE.

- **Class type indicators** — 🟢 project / 🟡 engine-derived / 🔴 engine-base badges on every class item (hover for description)
- **Inheritance chain breadcrumb** — clickable `A → B → C → D` chain; click any ancestor to navigate to it
- **Access modifier groups** — fields and methods are separated into 🔓 public / 🛡 protected / 🔒 private expandable sections
- **Expandable Method Analysis cards** — click any method card to expand it in-place and see:
  - Internal control flow: Guard / Branch / Loop / Switch / Exception items with color-coded labels
  - `{ } 소스 보기` — view the method's source code inline
  - `📡 호출 추적` — find every call site of this method across the project
  - `▶ 흐름 그래프` — jump directly to the Flow Graph tab for this method
- **AI Summary** (`🔍 AI 요약`) — AI-powered class overview: role, structure, design patterns, relationships; Compact / Full modes
- **API Search mode** — toggle to keyword-search across all classes, methods, and properties by relevance score; scope filter: All / Classes / Methods / Properties
- Coupling metrics and dead-code flags
- Unity Prefab / UE5 Blueprint back-references
- UE5 Blueprint↔C++ mapping details

### 2. Flow Graph

Visualize method call chains as an interactive node graph.

- Animated execution paths from any entry point
- Color-coded nodes: entry · async · dispatch · blueprint · leaf
- Drill-down into any node to expand its call tree
- LLM explanation panel — ask "what does this flow do?"
- Supports C++→Blueprint boundary crossings (UE5)
- **Reverse Callers panel** — select any node and click "Who calls this?" to see every caller across the project
- **Find Path panel** — specify From (class.method) and To (class.method), then find the call chain connecting them (C#/Unity)

### 3. Analysis

Architectural health dashboard for the whole project.

- Circular dependency detection with highlighted cycle paths
- High-coupling class ranking
- Dead code list
- **Inheritance hierarchy** — full hierarchy tree with direction toggle (Up / Down / Both) to trace ancestors or descendants; ReactFlow graph alongside text results
- One-click impact and test-scope for any class
- LLM architecture advice
- Lint issue scan with fix suggestions
- Git diff summary — architecture delta between two commits
- **Patterns** — detect architectural anti-patterns (God Object, Singleton abuse, tight coupling chains, etc.)
- **Unused Assets** (Unity + UE5) — scan for assets referenced nowhere in code; configurable scan directory and result limit
- Method callers — find all callers of a given method
- Call path — shortest call chain between two methods (C#/Unity)

### 4. Engine

Engine-specific explorers, each with its own sub-tab.

| Engine | Sub-tab | What you get |
|--------|---------|-------------|
| Unity | **UnityEvent** | Inspector-wired persistent calls invisible in code search |
| Unity | **Animator** | States, transitions, blend trees from AnimatorController |
| Unity | **Unused Assets** | Assets with no code references in the project |
| UE5 | **GAS** | Abilities, Effects, Attributes, Tags, ASC owners — `detail_level`, `category` (tag prefix), and `query` (keyword) filters |
| UE5 | **Blueprint** | C++ class → BP implementations, K2 overrides, events, variables |
| UE5 | **Animation** | ABP states, Montage slots, GAS Notifies |
| UE5 | **BehaviorTree** | BT asset structure with task/decorator/service nodes |
| UE5 | **StateTree** | StateTree (UE 5.2+) state + transition map |
| UE5 | **Unused Assets** | Assets with no code references in the project |
| Axmol | **Events** | EventDispatcher and Scheduler binding map |

All engine analysis results display a **Confidence badge** (🟢 HIGH / 🟡 MEDIUM / 🔴 LOW) indicating the reliability of the analysis based on the data source (source code vs. binary asset scanning).

### 5. Watch Panel

Live feedback as you code — no terminal needed.

- WebSocket connection to a local file watcher
- On every save: impact count · test files affected · lint warnings
- Collapsible result cards with severity indicators (ok / warning / error)
- Configurable debounce and analysis depth
- Optional target-class filter to reduce noise

### 6. Agent Chat

Conversational AI that reads your actual code.

- Server-Sent Events streaming for real-time responses
- Tool-calling execution steps shown inline
- Preset queries: onboarding · circular refs · God Object · GAS analysis · animation · AI behavior
- LLM provider selector: Ollama · OpenAI · Claude · Gemini
- Session-based conversation history with reset

---

## Configuration (Sidebar)

| Setting | Description |
|---------|-------------|
| **Scripts path** | Absolute path to your project's source folder — type directly or use the 📁 folder picker |
| **Folder picker** | Server-side directory browser — navigate and select any folder without typing paths |
| **Context button** | View the project's AI context (AGENTS.md) and run `gdep init` to generate it |
| **Engine profile** | auto · Unity · UE5 · Axmol · .NET · C++ |
| **Analysis depth** | 1–8 levels for flow and impact tracing |
| **Focus classes** | Comma-separated list to narrow results |
| **LLM provider** | Ollama / OpenAI / Claude / Gemini + model + API key |
| **Theme** | Dark / Light |
| **Language** | English / 한국어 |

### Project Context (AGENTS.md)

Click the **Context** button next to the cache refresh button to:

1. View the auto-generated project context (or AGENTS.md if it exists)
2. Click **Init AGENTS.md** to generate `.gdep/AGENTS.md` — a structured project overview consumed by AI tools (Claude Code, Cursor, etc.)
3. Click **Regen AGENTS.md** to regenerate if the project has changed

---

## API Reference

The backend exposes a REST + WebSocket API consumed by the frontend. All routes are prefixed with `/api`.

| Router | Path | Purpose |
|--------|------|---------|
| project | `POST /project/scan` | Coupling, cycles, dead code |
| project | `POST /project/impact` | Blast-radius for a class |
| project | `POST /project/describe` | Class structure with inheritance chain |
| project | `POST /project/lint` | Lint issue scan |
| project | `POST /project/advise` | LLM architecture advice |
| project | `POST /project/test-scope` | Test files for a changed class |
| project | `POST /project/diff-summary` | Architecture delta for a git diff |
| project | `POST /project/explain-method-logic` | Internal control flow of a method (Guard/Branch/Loop) |
| project | `POST /project/read_source` | Class or method source code (supports `method_name`) |
| project | `GET  /project/context` | Project AI context / AGENTS.md content |
| project | `POST /project/init` | Generate `.gdep/AGENTS.md` |
| project | `GET  /project/browse` | Server-side directory listing (drives → subdirs) |
| classes | `GET /classes/list` | All classes with fields + methods |
| flow | `POST /flow/analyze` | Method call graph |
| engine | `POST /engine/unity/events` | UnityEvent bindings |
| engine | `POST /engine/unity/animator` | Animator structure |
| engine | `POST /engine/ue5/gas` | GAS analysis (detail_level / category / query) |
| engine | `POST /engine/ue5/gas/graph` | GAS ReactFlow graph |
| engine | `POST /engine/ue5/animation` | ABP + Montage analysis |
| engine | `POST /engine/ue5/behavior_tree` | BehaviorTree structure |
| engine | `POST /engine/ue5/state_tree` | StateTree structure |
| engine | `POST /engine/axmol/events` | Axmol event bindings |
| unity | `GET /unity/refs` | All prefab/scene references |
| ue5 | `GET /ue5/blueprint_refs` | All blueprint references |
| ue5 | `GET /ue5/blueprint_mapping` | C++↔BP detailed mapping |
| analysis | `POST /analysis/hierarchy` | Full class inheritance tree (up/down/both) |
| analysis | `POST /analysis/unused-assets` | Unused asset scan |
| analysis | `POST /analysis/query-api` | API-level keyword search across classes/methods/properties |
| analysis | `POST /analysis/detect-patterns` | Architectural anti-pattern detection |
| analysis | `POST /analysis/method-callers` | Find all callers of a method |
| analysis | `POST /analysis/call-path` | Call chain path between two methods (C#/Unity) |
| analysis | `POST /analysis/explore-semantics` | AI-powered class semantics summary (compact / full) |
| agent | `POST /agent/run` | SSE-streamed AI agent |
| agent | `POST /agent/reset` | Clear agent session |
| llm | `POST /llm/analyze` | LLM flow explanation |
| llm | `GET /llm/ollama/models` | Discover local Ollama models |
| watch | `WS /watch` | Real-time file change events |

---

## Directory Structure

```
web/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, router registration
│   ├── requirements.txt
│   └── routers/
│       ├── project.py           # scan / impact / describe / lint / advise / diff
│       │                        # explain-method-logic / read_source / context / init / browse
│       ├── classes.py           # class list parser (C# / C++ / UE5)
│       ├── flow.py              # call graph tracer
│       ├── engine.py            # engine-specific analyzers (GAS w/ filters)
│       ├── unity.py             # Unity ref queries
│       ├── ue5.py               # UE5 blueprint queries
│       ├── analysis.py          # hierarchy / unused-assets / query-api / detect-patterns
│       │                        # method-callers / call-path / explore-semantics
│       ├── agent.py             # SSE agent with tool-calling
│       ├── llm.py               # LLM provider bridge
│       └── watch.py             # WebSocket file watcher
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx              # 6-tab layout
        ├── store.tsx            # Global state + caching
        ├── i18n.ts              # EN / KR translations
        ├── api/
        │   └── client.ts        # Typed API functions
        └── components/
            ├── Sidebar.tsx      # Project config panel + folder picker + Context modal
            ├── ClassBrowser.tsx # Class explorer: expandable method cards, AI summary,
            │                    # public/protected/private groups, API search mode
            ├── AnalysisView.tsx # Analysis tab: coupling / inheritance / dead code /
            │                    # impact / test-scope / advise / lint / diff /
            │                    # patterns / unused assets / method-callers / call-path
            ├── EngineView.tsx   # Engine tab: Unity / UE5 / Axmol sub-tabs
            ├── FlowGraph.tsx    # Call graph + Reverse Callers + Find Path
            ├── WatchPanel.tsx   # Real-time file watcher
            ├── ConfidenceBadge.tsx  # HIGH/MEDIUM/LOW confidence pill badge
            ├── MdResult.tsx     # Shared markdown/text result renderer
            └── tabs/
                └── AgentChat.tsx    # SSE-streaming AI agent chat
```

---

*Part of the [gdep](../../README.md) project — Game Codebase Analysis Tool*
