# gdep Web UI — Frontend

React 19 + TypeScript + Vite frontend for the [gdep Web UI](../README.md).

---

## Tech Stack

| Library | Purpose |
|---------|---------|
| React 19 | UI framework |
| TypeScript | Type safety |
| Vite 8 | Build tool + HMR |
| TailwindCSS | Utility-first styling |
| React Flow (`@xyflow/react`) | Interactive graph visualizations |
| Axios | HTTP client |
| Lucide React | Icon library |

---

## Development

```bash
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build (tsc + vite)
npm run preview  # preview production build
```

Requires the backend to be running at `http://localhost:8000`. See [../README.md](../README.md).

---

## Project Structure

```
src/
├── App.tsx                  # Root component — 6-tab layout
│                            # Browser · Flow · Analysis · Engine · Watch · Agent
├── store.tsx                # Global state (Zustand-like context)
│                            # scriptsPath, projectInfo, llmConfig,
│                            # selectedClass, depth, cache, theme, lang
├── i18n.ts                  # EN / KR translations
├── api/
│   └── client.ts            # Typed Axios wrappers for all backend routes
└── components/
    ├── Sidebar.tsx          # Left panel: path input + 📁 folder picker,
    │                        # engine profile, LLM config,
    │                        # cache refresh + 📖 Context modal
    ├── ClassBrowser.tsx     # Class list + detail panel
    │                        # - 🟢🟡🔴 class type badges (project / engine-derived / engine-base)
    │                        # - inheritance chain breadcrumb (clickable)
    │                        # - public / 🛡 protected / 🔒 private access groups
    │                        # - expandable method analysis cards (accordion)
    │                        #   ├─ Guard/Branch/Loop/Switch/Exception control flow
    │                        #   ├─ { } source viewer (inline)
    │                        #   ├─ 📡 호출 추적 (method callers)
    │                        #   └─ ▶ 흐름 그래프 (jump to Flow tab)
    │                        # - 🔍 AI Summary (explore-semantics, compact/full)
    │                        # - API Search mode (classes / methods / properties)
    ├── AnalysisView.tsx     # Analysis tab — sub-tabs:
    │                        # coupling · inheritance · dead code · impact ·
    │                        # test-scope · advise · lint · diff · patterns ·
    │                        # unused assets · method callers · call path
    ├── EngineView.tsx       # Engine tab — horizontal sub-tab bar per engine:
    │                        # Unity: UnityEvent / Animator / Unused Assets
    │                        # UE5: GAS / Blueprint / Animation / BehaviorTree /
    │                        #      StateTree / Unused Assets
    │                        # Axmol: Events
    ├── FlowGraph.tsx        # Call graph + Reverse Callers panel + Find Path panel
    ├── WatchPanel.tsx       # WebSocket real-time file-change monitor
    ├── ConfidenceBadge.tsx  # Reusable HIGH/MEDIUM/LOW confidence pill badge
    │                        # + extractConfidence(text) helper
    ├── MdResult.tsx         # Shared markdown/text result renderer
    └── tabs/
        └── AgentChat.tsx    # SSE-streaming AI agent chat
```

---

## Key Components

### ClassBrowser

Shows every class in the project with full detail.

- **Class type badges** — 🟢 project / 🟡 engine-derived / 🔴 engine-base on each list item; hover for label tooltip. The legend near the Lint button has individual hover descriptions.
- **Inheritance chain**: fetches `/project/describe` on class selection and renders a clickable `A → B → C` breadcrumb. Clicking any ancestor navigates to that class.
- **Access modifier groups**: fields and methods are split into public (always visible) / 🛡 protected / 🔒 private collapsible sections.
- **Expandable Method Analysis cards** (`ExpandableMethodCard` pattern):
  - Click any method card → accordion expands to full width (`col-span-2`)
  - Calls `POST /project/explain-method-logic` and renders Guard/Branch/Loop/Switch/Exception items
  - `{ } 소스 보기` — calls `POST /project/read_source` with `method_name` and shows source inline
  - `📡 호출 추적` — calls `POST /analysis/method-callers` and shows all call sites
  - `▶ 흐름 그래프` — triggers `POST /flow/analyze` and switches to the Flow tab
  - Works for lifecycle, public, protected, and private methods
- **AI Summary** button: calls `POST /analysis/explore-semantics` with `compact` toggle; result rendered inline as scrollable pre block.
- **API Search mode**: calls `POST /analysis/query-api`; scope filter All / Classes / Methods / Properties.

### AnalysisView

Architectural health dashboard split into sub-tabs. Replaces the old `DependencyView` analysis side.

Key sub-tabs:
- **Coupling** — high-coupling class ranking + circular dependency detection
- **Inheritance** — ReactFlow hierarchy graph with Up / Down / Both direction toggle
- **Impact / Test Scope** — blast-radius and test file suggestions for any class
- **Patterns** — architectural anti-pattern detection (God Object, Singleton abuse, etc.)
- **Unused Assets** — configurable directory scan with result limit

### EngineView

Engine-specific explorers with a horizontal sub-tab bar. Engine is auto-detected from the project profile; tabs for irrelevant engines are hidden.

#### UE5 GAS tab — extra filter inputs

```
detail_level: summary (default) | full
category:     tag prefix filter (e.g. Event, Ability)
query:        keyword search across class names and tag names
```

### ConfidenceBadge

```tsx
import { ConfidenceBadge, ConfidenceFromText, extractConfidence } from './ConfidenceBadge'

// Manual usage
<ConfidenceBadge tier="HIGH" note="source-level control flow" />

// Auto-parse from analysis result text
<ConfidenceFromText text={result} />

// Parse programmatically
const conf = extractConfidence(result)  // { tier: "MEDIUM", note: "..." } | null
```

The CLI appends `[Confidence: HIGH | reason]` to analysis outputs. `ConfidenceFromText` parses this pattern and renders the badge automatically.

### Sidebar — Folder Picker + Project Context modal

```
Scripts path: [ /path/to/project ] [📁] [↻ 캐시] [📖 Context]
                                    ↓ click
                          ┌─────────────────────────┐
                          │ 폴더 선택                 │
                          │ ⬆ 상위 폴더              │
                          │ 📁 SubDir1               │
                          │ 📁 SubDir2               │
                          │ [선택]  [취소]            │
                          └─────────────────────────┘

[ 📖 Context ] → opens Project Context modal
                 [Init AGENTS.md]  [Regen AGENTS.md]  [✕]
                 <AGENTS.md content or generated context>
```

Folder picker calls `GET /project/browse` (server-side directory listing). Supports Windows drive enumeration at the root level.

Context modal calls `GET /project/context` on open. "Init AGENTS.md" calls `POST /project/init`.

---

## API Client (`src/api/client.ts`)

All backend calls go through typed functions organized into API groups:

```ts
// ── projectApi ──────────────────────────────────────────
projectApi.describe(path, className)               // → DescribeResult (with inheritance_chain)
projectApi.explainMethodLogic(path, cls, method)   // → ExplainMethodResult
projectApi.readSource(path, cls, maxChars, methodName?)  // → { content, truncated }
projectApi.getContext(path)                        // → ProjectContextResult
projectApi.init(path, force?)                      // → InitResult
projectApi.browse(path?)                           // → BrowseResult { parent, dirs, is_root }

// ── analysisNewApi ──────────────────────────────────────
analysisNewApi.exploreSemantics(path, cls, compact?, includeSource?)  // → string
analysisNewApi.methodCallers(path, cls, method, maxResults?)          // → string
analysisNewApi.callPath(path, fromCls, fromMethod, toCls, toMethod)   // → string
analysisNewApi.hierarchy(path, cls, direction?)                       // → HierarchyResult
analysisNewApi.unusedAssets(path, scanDir?, maxResults?)              // → string
analysisNewApi.detectPatterns(path, maxResults?)                      // → string
analysisNewApi.queryApi(path, query, scope?)                          // → string

// ── engineApi ───────────────────────────────────────────
engineApi.ue5Gas(path, cls?, detail_level?, category?, query?)
```

---

## 프론트엔드 구조 (한국어)

```
src/
├── App.tsx                  # 루트 컴포넌트 — 6탭 레이아웃
│                            # Browser · Flow · Analysis · Engine · Watch · Agent
├── store.tsx                # 전역 상태 (scriptsPath, projectInfo, 캐시 등)
├── i18n.ts                  # 영어 / 한국어 번역
├── api/
│   └── client.ts            # 백엔드 전체 라우트 타입 래퍼
└── components/
    ├── Sidebar.tsx          # 경로 입력 + 📁 폴더 선택기 · 엔진 · LLM 설정 + Context 모달
    ├── ClassBrowser.tsx     # 클래스 목록 + 상세
    │                        # · 🟢🟡🔴 클래스 타입 뱃지 (hover 툴팁)
    │                        # · 상속 체인 breadcrumb (클릭 이동)
    │                        # · public / 🛡 protected / 🔒 private 3그룹 분리
    │                        # · 확장형 메서드 분석 카드 (아코디언)
    │                        #   ├─ 제어 흐름 분석 (Guard/Branch/Loop 등)
    │                        #   ├─ { } 소스 보기 (메서드 소스 인라인)
    │                        #   ├─ 📡 호출 추적 (method-callers)
    │                        #   └─ ▶ 흐름 그래프 (Flow 탭 이동)
    │                        # · 🔍 AI 요약 (explore-semantics, Compact/Full)
    │                        # · API 검색 모드 (클래스/메서드/프로퍼티)
    ├── AnalysisView.tsx     # Analysis 탭 — 서브탭:
    │                        # 커플링 · 상속 계층 · 데드코드 · 영향 범위 ·
    │                        # 테스트 스코프 · 아키텍처 조언 · Lint · Diff ·
    │                        # 패턴 감지 · 미사용 에셋 · 역호출 · 호출 경로
    ├── EngineView.tsx       # Engine 탭 — 엔진별 수평 서브탭:
    │                        # Unity: UnityEvent / Animator / 미사용 에셋
    │                        # UE5: GAS / Blueprint / Animation /
    │                        #      BehaviorTree / StateTree / 미사용 에셋
    │                        # Axmol: Events
    ├── FlowGraph.tsx        # 호출 그래프 + 역호출 추적 + 경로 탐색
    ├── WatchPanel.tsx       # WebSocket 실시간 파일 감시
    ├── ConfidenceBadge.tsx  # HIGH/MEDIUM/LOW 신뢰도 pill 뱃지
    ├── MdResult.tsx         # 공통 마크다운/텍스트 결과 렌더러
    └── tabs/
        └── AgentChat.tsx    # SSE 스트리밍 AI 채팅
```

### ClassBrowser — 메서드 분석 카드 동작

```
메서드 카드 클릭
    ↓
카드 확장 (col-span-2)
    ├─ 제어 흐름 항목 (Guard/Branch/Loop/Switch/Exception)
    ├─ [{ } 소스 보기]  → 메서드 소스 코드 인라인 표시
    ├─ [📡 호출 추적]   → 해당 메서드의 모든 호출 위치 표시
    └─ [▶ 흐름 그래프] → Flow 탭으로 이동 + 호출 그래프 렌더링
```

라이프사이클 진입점(노란색) · public · protected · private 모든 메서드에서 동일하게 동작.

---

*Part of [gdep Web UI](../README.md)*
