import { useState, useEffect } from 'react'
import { useState as useLocalState } from 'react'
import { Search, Zap, ChevronRight, ChevronDown, ShieldAlert, Play } from 'lucide-react'
import { useApp, type EngineProfile } from '../store'
import type { TranslationKey } from '../i18n'
import {
  classesApi, flowApi, unityApi, projectApi, analysisNewApi,
  type ClassInfo, type ClassMethod, type ClassField, type PrefabRef,
  type LintIssue, ue5Api, type BlueprintRef,
  type ExplainMethodResult, type DescribeResult,
} from '../api/client'


// ── BP 매핑 상세 카드 컴포넌트 ────────────────────────────────
function BpMappingDetail({ text }: { text: string }) {
  // "### `BP_Name` (BP_Name_C)" 로 시작하는 블록으로 분리
  const blocks: { title: string; lines: string[] }[] = []
  let current: { title: string; lines: string[] } | null = null

  for (const line of text.split('\n')) {
    if (line.startsWith('### ')) {
      if (current) blocks.push(current)
      current = { title: line.replace(/^###\s*/, '').replace(/`/g, ''), lines: [] }
    } else if (current) {
      current.lines.push(line)
    }
  }
  if (current) blocks.push(current)

  if (blocks.length === 0) {
    // 블록이 없으면 단순 텍스트 렌더링
    return (
      <div className="border-t border-gray-800 pt-2 mt-1 space-y-0.5 max-h-52 overflow-y-auto">
        {text.split('\n').map((line, i) => {
          if (line.startsWith('##')) return <p key={i} className="text-xs font-semibold text-blue-300 mt-2">{line.replace(/^#+\s*/,'')}</p>
          if (line.startsWith('-'))  return <p key={i} className="text-xs text-gray-400 pl-2">• {line.slice(1).trim()}</p>
          if (!line.trim())          return <div key={i} className="h-1" />
          return <p key={i} className="text-xs text-gray-500">{line}</p>
        })}
      </div>
    )
  }

  return (
    <div className="border-t border-gray-800 pt-2 mt-1 space-y-1">
      {blocks.map((block, idx) => (
        <BpCard key={idx} title={block.title} lines={block.lines} defaultOpen={blocks.length === 1} />
      ))}
    </div>
  )
}

function BpCard({ title, lines, defaultOpen }: { title: string; lines: string[]; defaultOpen: boolean }) {
  const [open, setOpen] = useLocalState(defaultOpen)
  const sections: { heading: string; items: string[] }[] = []
  let cur: { heading: string; items: string[] } | null = null
  for (const line of lines) {
    if (line.startsWith('  K2 overrides:') || line.startsWith('  Variables:') ||
        line.startsWith('  Tags:') || line.startsWith('  Path:') ||
        line.startsWith('  Event ')) {
      if (cur) sections.push(cur)
      const colon = line.indexOf(':')
      cur = { heading: line.slice(0, colon).trim(), items: [line.slice(colon + 1).trim()] }
    } else if (line.trim() && cur) {
      cur.items.push(line.trim())
    }
  }
  if (cur) sections.push(cur)

  return (
    <div className="rounded border border-gray-700 bg-gray-900/60 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-gray-800/50 transition-colors"
      >
        <span className="text-xs font-semibold text-blue-300 text-left truncate flex-1">{title}</span>
        <span className="text-gray-500 text-xs ml-2 shrink-0">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-1 border-t border-gray-800">
          {sections.map((sec, i) => (
            <div key={i} className="mt-1.5">
              <p className="text-xs text-gray-500 font-medium">{sec.heading}</p>
              {sec.items.filter(Boolean).map((item, j) => (
                <p key={j} className="text-xs text-gray-300 pl-2 truncate" title={item}>• {item}</p>
              ))}
            </div>
          ))}
          {sections.length === 0 && (
            <p className="text-xs text-gray-600 mt-1">—</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── 엔진 정의 ─────────────────────────────────────────────────
const ENGINE_BASES: Record<EngineProfile, string[]> = {
  auto:     [],
  unity:    ['MonoBehaviour','ScriptableObject','Editor','EditorWindow',
             'StateMachineBehaviour','NetworkBehaviour','PlayableBehaviour'],
  cocos2dx: ['CCNode','CCLayer','CCScene','CCSprite','CCMenu','CCObject',
             'Node','Layer','Scene','Sprite','Ref'],
  unreal: [
    'UObject','AActor','APawn','ACharacter','AController',
    'APlayerController','AAIController','AGameMode','AGameModeBase',
    'AGameState','APlayerState','AHUD',
    'UActorComponent','USceneComponent','UPrimitiveComponent',
    'UMeshComponent','USkeletalMeshComponent','UStaticMeshComponent',
    'UCapsuleComponent','USphereComponent','UBoxComponent',
    'UGameInstance','ULocalPlayer',
    'UGameplayAbility','UAttributeSet','UAbilitySystemComponent',
    'UGameplayEffect','UGameplayTask',
    'UUserWidget','UWidget',
    'IAbilitySystemInterface','IInterface',
  ],
  dotnet:   ['Object','Component'],
  cpp:      [],
  axmol: [
    'Node','Scene','Layer','Sprite','Ref','Application',
    'Director','Action','Event','EventListener',
    'DrawNode','ClippingNode','MotionStreak',
    'Label','LabelTTF','Menu','MenuItem','MenuItemLabel',
    'ScrollView','ListView','PageView','TableView',
    'AudioEngine','SimpleAudioEngine',
  ],
}

// ★ private 포함 — Unity lifecycle은 private으로 선언하는 게 일반적
const LIFECYCLE: Record<EngineProfile, string[]> = {
  auto:     [],
  unity:    ['Awake','Start','Update','FixedUpdate','LateUpdate','OnEnable','OnDisable',
             'OnDestroy','OnTriggerEnter','OnTriggerExit','OnCollisionEnter','OnCollisionExit',
             'OnApplicationPause','OnApplicationFocus','Reset','OnValidate',
             'OnBecameVisible','OnBecameInvisible','OnDrawGizmos'],
  cocos2dx: ['init','onEnter','onExit','update','draw',
             'onEnterTransitionDidFinish','onExitTransitionDidStart','cleanup'],
  unreal: [
    'BeginPlay','EndPlay','Tick','PostInitializeComponents',
    'BeginDestroy','PostLoad','OnConstruction','Destroyed',
    'InitializeComponent','UninitializeComponent','OnRegister','OnUnregister',
    'ActivateAbility','EndAbility','CancelAbility','CommitAbility','CanActivateAbility',
    'PostGameplayEffectExecute','PreAttributeChange','PostAttributeChange',
    'SetupPlayerInputComponent','PossessedBy','UnPossessed','OnRep_PlayerState',
    'NativeConstruct','NativeDestruct','NativeTick','NativeOnInitialized',
  ],
  dotnet:   ['Main','Dispose','OnStart','OnStop','Initialize','Finalize'],
  cpp:      ['main','init','update','draw','cleanup'],
  axmol: ['init','onEnter','onExit','update','draw',
          'onEnterTransitionDidFinish','onExitTransitionDidStart','cleanup',
          'onTouchBegan','onTouchMoved','onTouchEnded','onTouchCancelled'],
}

type ClassType = 'engine_base' | 'engine_derived' | 'project'

function classifyClass(name: string, bases: string[], profile: EngineProfile, custom: string[]): ClassType {
  const eb = [...(ENGINE_BASES[profile] ?? []), ...custom]
  if (eb.includes(name)) return 'engine_base'
  if (bases.some(b => eb.includes(b))) return 'engine_derived'
  return 'project'
}

// Labels are resolved at render time via t()
const TYPE_BADGE_KEYS = {
  engine_base:    { icon: '🔴', color: 'text-red-400',     labelKey: 'engine_base_label'    as TranslationKey },
  engine_derived: { icon: '🟡', color: 'text-yellow-400',  labelKey: 'engine_derived_label' as TranslationKey },
  project:        { icon: '🟢', color: 'text-emerald-400', labelKey: 'project_label'        as TranslationKey },
}

// ── 시그니처 포맷 ─────────────────────────────────────────────
function sig(m: ClassMethod): string {
  const params = m.params.length === 0 ? ''
    : m.params.slice(0, 4).join(', ') + (m.params.length > 4 ? ', …' : '')
  const ret = m.ret && m.ret !== 'void' ? ` → ${m.ret}` : ' → void'
  return `(${params})${ret}`
}

// ── 접근제한자 토글 ───────────────────────────────────────────
function AccessToggle({ label, icon, count, children }: {
  label: string; icon: string; count: number; children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  if (count === 0) return null
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 py-1">
        {open ? <ChevronDown size={12}/> : <ChevronRight size={12}/>}
        <span className="shrink-0">{icon}</span> {label} ({count})
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  )
}

// ── 테이블 (가로 폭 풀 활용, 스크롤 가능) ────────────────────
function FieldTable({ fields, dim = false }: { fields: ClassField[]; dim?: boolean }) {
  if (fields.length === 0) return null
  return (
    <table className="w-full text-sm border-collapse">
      <tbody>
        {fields.map(f => (
          <tr key={f.name + f.access}
            className={`border-b border-gray-800 hover:bg-gray-800/50 ${dim ? 'opacity-60' : ''}`}>
            <td className="py-1 px-2 text-emerald-400 whitespace-nowrap w-2/5">{f.name}</td>
            <td className="py-1 px-2 text-gray-400 break-all">{f.type}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function MethodTable({ methods, lifecycleMethods, dim = false }: {
  methods: ClassMethod[]; lifecycleMethods: string[]; dim?: boolean
}) {
  if (methods.length === 0) return null
  return (
    <table className="w-full text-sm border-collapse">
      <tbody>
        {methods.map(m => (
          <tr key={m.name + m.access}
            className={`border-b border-gray-800 hover:bg-gray-800/50 ${dim ? 'opacity-60' : ''}`}>
            <td className="py-1 px-2 whitespace-nowrap w-2/5">
              <span className={dim ? 'text-gray-500' : 'text-blue-400'}>
                {m.isAsync && <span className="text-yellow-500 mr-1 text-xs">⏱</span>}
                {lifecycleMethods.includes(m.name) && <span className="text-yellow-400 mr-1 text-xs">⚡</span>}
                {m.name}
              </span>
            </td>
            <td className="py-1 px-2 font-mono text-xs text-gray-500 break-all">{sig(m)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ── Method Logic 패널 (확장 카드 내부) ────────────────────────
const LOGIC_TYPE_COLOR: Record<string, string> = {
  guard: 'text-red-400', branch: 'text-yellow-400',
  loop: 'text-blue-400', switch: 'text-cyan-400',
  exception: 'text-orange-400', always: 'text-green-400',
}

function MethodLogicPanel({ methodName, methodLogic, methodLogicLoading,
  methodSource, methodSourceName, methodSourceLoading,
  methodCallersResult, methodCallersName, methodCallersLoading,
  onViewSource, onRunFlow, onMethodCallers, analyzing, t,
}: {
  methodName: string
  methodLogic: ExplainMethodResult | null; methodLogicLoading: boolean
  methodSource: string | null; methodSourceName: string | null; methodSourceLoading: boolean
  methodCallersResult: string | null; methodCallersName: string | null; methodCallersLoading: boolean
  onViewSource: () => void; onRunFlow: () => void; onMethodCallers: () => void
  analyzing: boolean; t: (k: any) => string
}) {
  return (
    <div className="mt-1 rounded-b border border-t-0 border-violet-800 bg-violet-950/30 p-3 space-y-1">
      {methodLogicLoading ? (
        <p className="text-xs text-gray-500 animate-pulse">analyzing {methodName}…</p>
      ) : methodLogic ? (
        <>
          {methodLogic.items.length === 0 ? (
            <p className="text-xs text-gray-500">Linear sequence — no branching logic detected.</p>
          ) : methodLogic.items.map((item, i) => (
            <div key={i} className="flex gap-2 text-xs">
              <span className={`shrink-0 w-16 font-mono uppercase ${LOGIC_TYPE_COLOR[item.type] ?? 'text-gray-400'}`}>{item.type}</span>
              <span className="text-gray-300 truncate" title={item.text}>{item.text}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-violet-800/50">
            {methodLogic.source_file && (
              <p className="text-xs text-gray-600 flex-1 truncate">{methodLogic.source_file}</p>
            )}
            <button onClick={onViewSource} disabled={methodSourceLoading}
              className={`text-xs px-2 py-0.5 rounded border transition-colors shrink-0
                ${methodSourceName === methodName && methodSource
                  ? 'border-emerald-600 bg-emerald-950 text-emerald-300'
                  : 'border-gray-700 text-gray-400 hover:border-emerald-700 hover:text-emerald-400'}
                disabled:opacity-50`}>
              {methodSourceLoading ? '...' : t('method_view_source')}
            </button>
            <button onClick={onMethodCallers} disabled={methodCallersLoading}
              title={t('tooltip_method_callers' as TranslationKey)}
              className={`text-xs px-2 py-0.5 rounded border transition-colors shrink-0
                ${methodCallersName === methodName && methodCallersResult
                  ? 'border-blue-600 bg-blue-950 text-blue-300'
                  : 'border-gray-700 text-gray-400 hover:border-blue-700 hover:text-blue-400'}
                disabled:opacity-50`}>
              {methodCallersLoading ? '...' : t('method_callers_btn' as TranslationKey)}
            </button>
            <button onClick={onRunFlow} disabled={analyzing}
              className="text-xs px-2 py-0.5 rounded border border-emerald-700 bg-emerald-950
                         text-emerald-300 hover:bg-emerald-900 transition-colors shrink-0
                         disabled:opacity-50 flex items-center gap-1">
              <Play size={10}/> {t('method_run_flow' as TranslationKey)}
            </button>
          </div>
          {methodSourceName === methodName && methodSource && (
            <div className="mt-2 rounded bg-gray-900 border border-gray-700 p-2 max-h-60 overflow-y-auto">
              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">{methodSource}</pre>
            </div>
          )}
          {methodCallersName === methodName && methodCallersResult && (
            <div className="mt-2 rounded bg-gray-900 border border-blue-900 p-2 max-h-60 overflow-y-auto">
              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">{methodCallersResult}</pre>
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-gray-500">No result</p>
      )}
    </div>
  )
}

// ── 메서드 카드 그리드 (확장 가능) ─────────────────────────────
function MethodCardGrid({ methods, variant, expandedMethod, setExpandedMethod,
  selectedClass, scriptsPath, analyzing,
  methodLogic, methodLogicLoading, methodSource, methodSourceName, methodSourceLoading,
  methodCallersResult, methodCallersName, methodCallersLoading,
  setLogicMethod, setMethodLogic, setMethodLogicLoading,
  setMethodSource, setMethodSourceName, setMethodSourceLoading,
  setMethodCallersResult, setMethodCallersName, setMethodCallersLoading,
  runFlow, t,
}: {
  methods: ClassMethod[]; variant: 'public' | 'protected' | 'private'
  expandedMethod: string | null; setExpandedMethod: (v: string | null) => void
  selectedClass: string; scriptsPath: string
  analyzing: boolean
  methodLogic: ExplainMethodResult | null; methodLogicLoading: boolean
  methodSource: string | null; methodSourceName: string | null; methodSourceLoading: boolean
  methodCallersResult: string | null; methodCallersName: string | null; methodCallersLoading: boolean
  setLogicMethod: (v: string | null) => void
  setMethodLogic: (v: ExplainMethodResult | null) => void
  setMethodLogicLoading: (v: boolean) => void
  setMethodSource: (v: string | null) => void
  setMethodSourceName: (v: string | null) => void
  setMethodSourceLoading: (v: boolean) => void
  setMethodCallersResult: (v: string | null) => void
  setMethodCallersName: (v: string | null) => void
  setMethodCallersLoading: (v: boolean) => void
  runFlow: (cls: string, method: string) => void
  t: (k: any) => string
}) {
  const styles = {
    public:    { bg: 'bg-gray-700 hover:bg-gray-600', border: 'border-gray-600 hover:border-emerald-700',
                 activeBorder: 'border-2 border-emerald-500 bg-gray-600', text: 'text-gray-100', icon: '' },
    protected: { bg: 'bg-gray-800 hover:bg-gray-700', border: 'border-amber-800',
                 activeBorder: 'border-2 border-amber-500 bg-gray-700', text: 'text-gray-400', icon: '🛡' },
    private:   { bg: 'bg-gray-800 hover:bg-gray-700', border: 'border-gray-700',
                 activeBorder: 'border-2 border-gray-500 bg-gray-700', text: 'text-gray-400', icon: '🔒' },
  }
  const s = styles[variant]

  return (
    <div className="grid grid-cols-2 gap-1.5 max-h-96 overflow-y-auto pr-1">
      {methods.slice(0, 60).map(m => {
        const key = `${variant}_${m.name}`
        const isExpanded = expandedMethod === key
        return (
          <div key={m.name} className={isExpanded ? 'col-span-2' : ''}>
            <button
              onClick={() => {
                if (isExpanded) { setExpandedMethod(null); return }
                setExpandedMethod(key)
                setLogicMethod(m.name); setMethodLogic(null); setMethodLogicLoading(true)
                setMethodSource(null); setMethodSourceName(null)
                setMethodCallersResult(null); setMethodCallersName(null)
                projectApi.explainMethodLogic(scriptsPath, selectedClass, m.name)
                  .then(r => setMethodLogic(r)).catch(() => setMethodLogic(null))
                  .finally(() => setMethodLogicLoading(false))
              }}
              title={`${m.name}${sig(m)}`}
              className={`w-full text-left flex flex-col gap-0.5 px-3 py-2 rounded transition-colors
                         ${isExpanded ? s.activeBorder : `${s.bg} border ${s.border}`}`}>
              <span className={`flex items-center gap-1 text-sm truncate w-full ${s.text}`}>
                {s.icon && <span className="shrink-0">{s.icon}</span>}
                {m.isAsync && <span className="text-yellow-500 shrink-0">⏱</span>}
                <span className="truncate font-medium">{m.name}</span>
              </span>
              <span className="font-mono text-xs text-gray-500 truncate w-full">{sig(m)}</span>
            </button>
            {isExpanded && (
              <MethodLogicPanel
                methodName={m.name}
                methodLogic={methodLogic} methodLogicLoading={methodLogicLoading}
                methodSource={methodSource} methodSourceName={methodSourceName}
                methodSourceLoading={methodSourceLoading}
                methodCallersResult={methodCallersResult} methodCallersName={methodCallersName}
                methodCallersLoading={methodCallersLoading}
                onViewSource={async () => {
                  if (methodSourceName === m.name && methodSource) {
                    setMethodSource(null); setMethodSourceName(null); return
                  }
                  setMethodSourceLoading(true)
                  try {
                    const res = await projectApi.readSource(scriptsPath, selectedClass, 4000, m.name)
                    setMethodSource(res.content); setMethodSourceName(m.name)
                  } catch { setMethodSource(null) }
                  finally { setMethodSourceLoading(false) }
                }}
                onMethodCallers={async () => {
                  if (methodCallersName === m.name && methodCallersResult) {
                    setMethodCallersResult(null); setMethodCallersName(null); return
                  }
                  setMethodCallersLoading(true)
                  try {
                    const res = await analysisNewApi.methodCallers(scriptsPath, selectedClass, m.name)
                    setMethodCallersResult(res); setMethodCallersName(m.name)
                  } catch { setMethodCallersResult(null) }
                  finally { setMethodCallersLoading(false) }
                }}
                onRunFlow={() => runFlow(selectedClass, m.name)}
                analyzing={analyzing} t={t}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

interface Props { onFlowReady: () => void }

export default function ClassBrowser({ onFlowReady }: Props) {
  const {
    scriptsPath, projectInfo, selectedClass, setSelectedClass,
    setFlowData, setBreadcrumb, depth, focusClasses, setSelectedNode,
    getCache, setCache, engineProfile, customBaseClasses, t,
  } = useApp()

  const [classes,     setClasses]    = useState<Record<string, ClassInfo>>({})
  const [query,       setQuery]      = useState('')
  const [methodQuery, setMethodQuery] = useState('')
  const [loading,     setLoading]    = useState(false)
  const [analyzing,   setAnalyzing]  = useState(false)
  const [prefabRef,   setPrefabRef]  = useState<(PrefabRef & { class_name: string }) | null>(null)
  const [loadingRef,  setLoadingRef] = useState(false)
  const [bpRef,        setBpRef]        = useState<(BlueprintRef & { class_name: string }) | null>(null)
  const [bpLoading,    setBpLoading]    = useState(false)
  const [bpMapping,    setBpMapping]    = useState<string>('')
  const [bpMapLoading, setBpMapLoading] = useState(false)
  // Lint
  const [lintIssues,  setLintIssues]  = useState<LintIssue[]>([])
  const [lintLoading, setLintLoading] = useState(false)
  const [lintOpen,    setLintOpen]    = useState(false)
  // Describe / inheritance chain (Phase 2-4)
  const [describeResult,    setDescribeResult]    = useState<DescribeResult | null>(null)
  // Method Logic (Phase 2-3)
  const [methodLogic,       setMethodLogic]       = useState<ExplainMethodResult | null>(null)
  const [methodLogicLoading,setMethodLogicLoading]= useState(false)
  const [logicMethod,       setLogicMethod]       = useState<string | null>(null)
  // API Search mode
  const [apiSearchMode,    setApiSearchMode]    = useState(false)
  const [apiScope,         setApiScope]         = useState<'all'|'classes'|'methods'|'properties'>('all')
  const [apiSearchResult,  setApiSearchResult]  = useState('')
  const [apiSearchLoading, setApiSearchLoading] = useState(false)
  // Method source viewer
  const [methodSource,        setMethodSource]        = useState<string | null>(null)
  const [methodSourceLoading, setMethodSourceLoading] = useState(false)
  const [methodSourceName,    setMethodSourceName]    = useState<string | null>(null)
  // AI Semantics
  const [semanticsResult,  setSemanticsResult]  = useState<string | null>(null)
  const [semanticsLoading, setSemanticsLoading] = useState(false)
  const [semanticsOpen,    setSemanticsOpen]    = useState(false)
  const [semanticsCompact, setSemanticsCompact] = useState(true)
  const [semanticsSource,  setSemanticsSource]  = useState(false)
  // Method callers
  const [methodCallersResult,  setMethodCallersResult]  = useState<string | null>(null)
  const [methodCallersLoading, setMethodCallersLoading] = useState(false)
  const [methodCallersName,    setMethodCallersName]    = useState<string | null>(null)
  // Expandable method card
  const [expandedMethod,   setExpandedMethod]   = useState<string | null>(null)

  useEffect(() => {
    if (!selectedClass || !scriptsPath || projectInfo?.kind !== 'UNREAL') {
      setBpRef(null); setBpLoading(false)
      setBpMapping(''); setBpMapLoading(false)
      return
    }
    setBpRef(null); setBpLoading(true)
    ue5Api.getClassBlueprintRefs(scriptsPath, selectedClass)
      .then(setBpRef)
      .catch(() => setBpRef(null))
      .finally(() => setBpLoading(false))

    // BP 매핑 상세 (K2 오버라이드, 변수, 태그)
    setBpMapping(''); setBpMapLoading(true)
    ue5Api.getBlueprintMapping(scriptsPath, selectedClass)
      .then(r => setBpMapping(r.result))
      .catch(() => setBpMapping(''))
      .finally(() => setBpMapLoading(false))
  }, [selectedClass, scriptsPath, projectInfo])

  // describe 결과 (inheritance_chain 포함) — selectedClass 변경 시 갱신
  useEffect(() => {
    if (!selectedClass || !scriptsPath) { setDescribeResult(null); return }
    projectApi.describe(scriptsPath, selectedClass)
      .then(setDescribeResult)
      .catch(() => setDescribeResult(null))
    setMethodLogic(null); setLogicMethod(null)
    setMethodSource(null); setMethodSourceName(null)
    setSemanticsResult(null); setSemanticsOpen(false)
    setMethodCallersResult(null); setMethodCallersName(null)
    setExpandedMethod(null)
  }, [selectedClass, scriptsPath])

  // 클래스 목록 캐시
  useEffect(() => {
    if (!scriptsPath) return
    const cached = getCache(scriptsPath).classMap
    if (cached) { setClasses(cached); return }
    setLoading(true)
    classesApi.list(scriptsPath)
      .then(d => { setClasses(d.classes); setCache(scriptsPath, { classMap: d.classes }) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [scriptsPath])

  // 프리팹 역참조 캐시
  useEffect(() => {
    if (!selectedClass || !scriptsPath || projectInfo?.kind !== 'UNITY') { setPrefabRef(null); return }
    const cached = getCache(scriptsPath).prefabRefs?.[selectedClass]
    if (cached) { setPrefabRef({ ...cached, class_name: selectedClass }); return }
    setLoadingRef(true)
    unityApi.getClassRefs(scriptsPath, selectedClass)
      .then(ref => {
        setPrefabRef(ref)
        const ex = getCache(scriptsPath).prefabRefs ?? {}
        setCache(scriptsPath, { prefabRefs: { ...ex, [selectedClass]: ref } })
      })
      .catch(() => setPrefabRef(null))
      .finally(() => setLoadingRef(false))
  }, [selectedClass, scriptsPath, projectInfo])

  async function runFlow(cls: string, method: string) {
    setAnalyzing(true)
    try {
      const data = await flowApi.analyze(scriptsPath, cls, method, depth, focusClasses)
      setFlowData(data); setBreadcrumb([{ cls, method }]); setSelectedNode(null)
      onFlowReady()
    } catch (e) { console.error(e) }
    finally { setAnalyzing(false) }
  }

  async function runLint() {
    setLintLoading(true); setLintOpen(true)
    try {
      const res = await projectApi.lint(scriptsPath)
      setLintIssues(res.issues)
    } catch (e) { console.error(e) }
    finally { setLintLoading(false) }
  }

  const profile    = engineProfile
  const lcMethods  = LIFECYCLE[profile] ?? []
  const classNames = Object.keys(classes).sort()
  const filtered   = query
    ? classNames.filter(c => c.toLowerCase().includes(query.toLowerCase()))
    : classNames

  const cls     = selectedClass ? classes[selectedClass] : null
  const methods = cls?.methods ?? []
  const fields  = cls?.fields  ?? []

  const lifecycle   = methods.filter(m => lcMethods.includes(m.name))
  const lcNames     = new Set(lifecycle.map(m => m.name))

  const pubFields   = fields.filter(f => f.access === 'public')
  const protFields  = fields.filter(f => f.access === 'protected')
  const privFields  = fields.filter(f => f.access !== 'public' && f.access !== 'protected')

  const mqFilter = (m: ClassMethod) => !methodQuery || m.name.toLowerCase().includes(methodQuery.toLowerCase())
  const pubOther    = methods.filter(m => m.access === 'public'    && !lcNames.has(m.name) && mqFilter(m))
  const protOther   = methods.filter(m => m.access === 'protected' && !lcNames.has(m.name) && mqFilter(m))
  const privOther   = methods.filter(m => m.access !== 'public' && m.access !== 'protected' && !lcNames.has(m.name) && mqFilter(m))

  // resolved TYPE_BADGE with translated labels
  const TYPE_BADGE = Object.fromEntries(
    Object.entries(TYPE_BADGE_KEYS).map(([k, v]) => [k, { ...v, label: t(v.labelKey) }])
  ) as Record<string, { icon: string; color: string; label: string }>

  if (!scriptsPath) return (
    <div className="flex items-center justify-center h-full text-gray-500 text-base">
      {t('class_no_path')}
    </div>
  )

  return (
    <div className="flex h-full overflow-hidden">

      {/* 클래스 목록 (고정 너비) */}
      <div className="w-64 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="p-3 border-b border-gray-800">
          {/* 검색 모드 토글 */}
          <div className="flex gap-1 mb-1.5">
            <button onClick={() => { setApiSearchMode(false); setApiSearchResult('') }}
              className={`text-xs px-2 py-0.5 rounded ${!apiSearchMode ? 'bg-emerald-800 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>
              📂
            </button>
            <button onClick={() => setApiSearchMode(true)}
              title={t('tooltip_api_search' as TranslationKey)}
              className={`text-xs px-2 py-0.5 rounded ${apiSearchMode ? 'bg-indigo-700 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>
              {t('api_search_mode')}
            </button>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-gray-500"/>
            <input className="input pl-8 text-sm"
              placeholder={apiSearchMode ? t('api_search_ph') : t('class_search_placeholder')}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && apiSearchMode && query.trim()) {
                  setApiSearchLoading(true); setApiSearchResult('')
                  analysisNewApi.queryApi(scriptsPath, query.trim(), apiScope)
                    .then(setApiSearchResult)
                    .catch((err: any) => setApiSearchResult(`Error: ${err?.message ?? err}`))
                    .finally(() => setApiSearchLoading(false))
                }
              }}
            />
          </div>
          {apiSearchMode && (
            <div className="flex gap-1 mt-1">
              {(['all', 'classes', 'methods', 'properties'] as const).map(s => (
                <button key={s} onClick={() => setApiScope(s)}
                  className={`text-xs px-1.5 py-0.5 rounded ${apiScope === s ? 'bg-indigo-700 text-white' : 'bg-gray-800 text-gray-400'}`}>
                  {t(`api_scope_${s}` as any)}
                </button>
              ))}
            </div>
          )}
        <div className="flex items-center justify-between mt-1">
            <p className="text-xs text-gray-500">
              {filtered.length}/{classNames.length}개
              {loading && <span className="ml-1 animate-pulse">{t('parsing')}</span>}
            </p>
            <div className="flex items-center gap-1.5">
              <button onClick={runLint} disabled={lintLoading}
                title={t('tooltip_lint' as TranslationKey)}
                className="flex items-center gap-1 text-xs px-2 py-0.5 rounded
                           bg-orange-900 hover:bg-orange-800 border border-orange-700
                           text-orange-200 disabled:opacity-50 transition-colors">
                <ShieldAlert size={11}/>
                {lintLoading ? t('lint_scanning') : 'Lint'}
              </button>
              <div className="flex gap-1.5 text-xs">
                <span title={t('badge_project_tip' as TranslationKey)}>🟢</span>
                <span title={t('badge_engine_derived_tip' as TranslationKey)}>🟡</span>
                <span title={t('badge_engine_base_tip' as TranslationKey)}>🔴</span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filtered.slice(0, 200).map(name => {            const bases = classes[name]?.bases ?? []
            const ct    = classifyClass(name, bases, profile, customBaseClasses)
            const bx    = TYPE_BADGE[ct]
            return (
              <button key={name}
                onClick={() => { setSelectedClass(name); setMethodQuery('') }}
                className={`w-full text-left text-sm px-2 py-1 rounded flex items-center gap-1.5 transition-colors
                  ${selectedClass === name
                    ? 'bg-emerald-900 text-emerald-300 border border-emerald-700'
                    : 'text-gray-300 hover:bg-gray-800'}`}>
                <span className="shrink-0 text-xs" title={bx.label}>{bx.icon}</span>
                <span className="truncate">{name}</span>
              </button>
            )
          })}
          {filtered.length > 200 && (
            <p className="text-xs text-gray-500 text-center py-2">{t('search_narrow')} ({filtered.length})</p>
          )}
        </div>

        {/* ── API 검색 결과 ── */}
        {apiSearchMode && (apiSearchResult || apiSearchLoading) && (
          <div className="border-t border-gray-800 shrink-0 max-h-64 overflow-y-auto p-2 bg-indigo-950/20">
            {apiSearchLoading ? (
              <p className="text-xs text-gray-500 animate-pulse text-center py-2">{t('analyzing')}</p>
            ) : (
              <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">{apiSearchResult}</pre>
            )}
          </div>
        )}

        {/* ── Lint 결과 패널 ── */}
        {lintOpen && (
          <div className="border-t border-gray-800 shrink-0 flex flex-col" style={{ maxHeight: 300 }}>
            <div className="flex items-center justify-between px-3 py-2 bg-orange-950/40
                            border-b border-orange-900 shrink-0">
              <span className="text-xs font-semibold text-orange-300 flex items-center gap-1.5">
                <ShieldAlert size={12}/> {t('lint_results')}
                {!lintLoading && (
                  <span className="ml-1 text-gray-400">
                    {lintIssues.length === 0 ? t('lint_none') : `${lintIssues.length}`}
                  </span>
                )}
              </span>
              <button onClick={() => setLintOpen(false)}
                className="text-xs text-gray-500 hover:text-gray-300">✕</button>
            </div>
            <div className="overflow-y-auto flex-1">
              {lintLoading && (
                <p className="text-xs text-gray-500 px-3 py-2 animate-pulse">{t('lint_scanning')}</p>
              )}
              {!lintLoading && lintIssues.length === 0 && (
                <p className="text-xs text-emerald-400 px-3 py-2">{t('lint_no_issues')}</p>
              )}
              {!lintLoading && lintIssues.map((issue, i) => {
                const sevCls = issue.severity === 'Error'
                  ? 'bg-red-900/60 border-red-800 text-red-300'
                  : issue.severity === 'Warning'
                    ? 'bg-yellow-900/40 border-yellow-800 text-yellow-300'
                    : 'bg-blue-900/30 border-blue-800 text-blue-300'
                const sevIcon = issue.severity === 'Error' ? '✕'
                  : issue.severity === 'Warning' ? '⚠' : 'ℹ'
                const ruleColor = issue.rule_id.startsWith('UE5-GAS') ? 'text-purple-400'
                  : issue.rule_id.startsWith('UE5-NET') ? 'text-cyan-400'
                  : issue.rule_id.startsWith('UE5') ? 'text-orange-400'
                  : issue.rule_id.startsWith('UNI') ? 'text-emerald-400'
                  : 'text-gray-500'
                return (
                  <div key={i}
                    onClick={() => setSelectedClass(issue.class_name)}
                    className={`px-3 py-2 border-b border-gray-800 hover:bg-gray-800/60
                               cursor-pointer transition-colors`}>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={`inline-flex items-center justify-center
                                        w-4 h-4 rounded text-xs font-bold shrink-0
                                        ${sevCls}`}>
                        {sevIcon}
                      </span>
                      <span className="text-xs text-gray-300 font-medium truncate flex-1">
                        {issue.class_name}
                        {issue.method_name && (
                          <span className="text-gray-500">.{issue.method_name}</span>
                        )}
                      </span>
                      <span className={`text-xs font-mono shrink-0 ${ruleColor}`}>
                        {issue.rule_id}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5 ml-5 leading-relaxed">
                      {issue.message}
                    </p>
                    {issue.suggestion && (
                      <p className="text-xs text-blue-400/70 mt-0.5 ml-5">
                        💡 {issue.suggestion}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* 상세 패널 — 가로 폭 풀 활용 */}
      <div className="flex-1 overflow-y-auto p-5">
        {!selectedClass ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-base">
            {t('class_select')}
          </div>
        ) : cls ? (() => {
          const ct  = classifyClass(selectedClass, cls.bases, profile, customBaseClasses)
          const bx  = TYPE_BADGE[ct]
          return (
            <div className="space-y-6">

              {/* 헤더 */}
              <div className="flex items-start gap-3">
                <span className={`text-2xl mt-0.5 shrink-0 ${bx.color}`} title={bx.label}>
                  {bx.icon}
                </span>
                <div>
                  <h2 className="text-xl font-bold text-white flex flex-wrap items-center gap-2">
                    {selectedClass}
                    <span className="text-sm text-gray-500 font-normal">{cls.kind}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700 ${bx.color}`}>
                      {bx.label}
                    </span>
                  </h2>
                  {/* 상속 체인 breadcrumb (describe 결과 기반) */}
                  {describeResult && describeResult.inheritance_chain.length > 1 ? (
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      {describeResult.inheritance_chain.map((cls2, i) => (
                        <span key={cls2} className="flex items-center gap-1">
                          {i > 0 && <ChevronRight size={12} className="text-gray-600 shrink-0" />}
                          <button
                            onClick={() => setSelectedClass(cls2)}
                            className="text-sm text-purple-400 hover:text-purple-300 hover:underline transition-colors">
                            {cls2}
                          </button>
                        </span>
                      ))}
                      {describeResult.also_implements.length > 0 && (
                        <span className="text-xs text-gray-500 ml-1">
                          +{describeResult.also_implements.join(', ')}
                        </span>
                      )}
                    </div>
                  ) : cls.bases.length > 0 ? (
                    <p className="text-sm text-gray-400 mt-0.5">
                      {t('inheritance')}: {cls.bases.map(b => (
                        <button key={b}
                          onClick={() => setSelectedClass(b)}
                          className="text-purple-400 hover:text-purple-300 hover:underline mr-2 transition-colors">
                          {b}
                        </button>
                      ))}
                    </p>
                  ) : null}
                  {/* AI 요약 버튼 */}
                  <button
                    onClick={async () => {
                      if (semanticsOpen) { setSemanticsOpen(false); return }
                      setSemanticsOpen(true)
                      setSemanticsLoading(true); setSemanticsResult(null)
                      try {
                        const res = await analysisNewApi.exploreSemantics(
                          scriptsPath, selectedClass, semanticsCompact, semanticsSource)
                        setSemanticsResult(res)
                      } catch { setSemanticsResult(null) }
                      finally { setSemanticsLoading(false) }
                    }}
                    title={t('tooltip_ai_summary' as TranslationKey)}
                    className={`mt-1.5 text-xs px-2.5 py-1 rounded border transition-colors inline-flex items-center gap-1
                      ${semanticsOpen
                        ? 'border-cyan-600 bg-cyan-950 text-cyan-300'
                        : 'border-gray-700 text-gray-400 hover:border-cyan-700 hover:text-cyan-400'}`}>
                    {t('semantics_btn')}
                  </button>
                </div>
              </div>

              {/* AI 요약 패널 */}
              {semanticsOpen && (
                <div className="card p-3 border-cyan-800">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-sm font-semibold text-cyan-300">{t('semantics_btn')}</h3>
                    <label className="flex items-center gap-1 text-xs text-gray-400"
                      title={t('tooltip_compact' as TranslationKey)}>
                      <input type="checkbox" checked={semanticsCompact}
                        onChange={e => setSemanticsCompact(e.target.checked)}
                        className="rounded" />
                      {t('semantics_compact')}
                    </label>
                    <label className="flex items-center gap-1 text-xs text-gray-400">
                      <input type="checkbox" checked={semanticsSource}
                        onChange={e => setSemanticsSource(e.target.checked)}
                        className="rounded" />
                      {t('semantics_source')}
                    </label>
                    <button
                      onClick={async () => {
                        setSemanticsLoading(true); setSemanticsResult(null)
                        try {
                          const res = await analysisNewApi.exploreSemantics(
                            scriptsPath, selectedClass, semanticsCompact, semanticsSource)
                          setSemanticsResult(res)
                        } catch { setSemanticsResult(null) }
                        finally { setSemanticsLoading(false) }
                      }}
                      className="text-xs px-2 py-0.5 rounded bg-cyan-900 hover:bg-cyan-800 text-cyan-300 border border-cyan-700">
                      Refresh
                    </button>
                    <button onClick={() => setSemanticsOpen(false)}
                      className="ml-auto text-xs text-gray-500 hover:text-gray-300">✕</button>
                  </div>
                  {semanticsLoading ? (
                    <p className="text-xs text-gray-500 animate-pulse">{t('analyzing')}</p>
                  ) : semanticsResult ? (
                    <div className="max-h-80 overflow-y-auto">
                      <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">{semanticsResult}</pre>
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500">No result</p>
                  )}
                </div>
              )}

              {/* 프리팹 역참조 */}
              {projectInfo?.kind === 'UNITY' && (
                <div className="card p-3">
                  <h3 className="text-sm font-semibold text-gray-300 mb-2">{t('prefab_usage')}</h3>
                  {loadingRef
                    ? <p className="text-sm text-gray-500 animate-pulse">{t('loading')}</p>
                    : prefabRef && prefabRef.total > 0 ? (
                      <div className="space-y-0.5">
                        {prefabRef.prefabs.map(p => (
                          <p key={p} className="text-sm text-blue-400" title={p}>
                            📦 <span className="font-medium">{p.split(/[\\/]/).pop()}</span>
                            <span className="text-gray-600 ml-2 text-xs">{p}</span>
                          </p>
                        ))}
                        {prefabRef.scenes.map(s => (
                          <p key={s} className="text-sm text-yellow-400" title={s}>
                            🎬 <span className="font-medium">{s.split(/[\\/]/).pop()}</span>
                            <span className="text-gray-600 ml-2 text-xs">{s}</span>
                          </p>
                        ))}
                      </div>
                    ) : <p className="text-sm text-gray-500">{t('no_prefab')}</p>
                  }
                </div>
              )}

              {projectInfo?.kind === 'UNREAL' && (
              <div className="card p-3">
                <h3 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                  {t('bp_impl')}
                  {bpRef && bpRef.total > 0 && (
                    <span className="text-xs bg-blue-900 text-blue-300 px-1.5 py-0.5 rounded-full">
                      {bpRef.total}개
                    </span>
                  )}
                </h3>
                {/* 파일 목록 (빠른 참조) */}
                {bpLoading ? (
                  <p className="text-sm text-gray-500 animate-pulse">{t('loading')}</p>
                ) : bpRef && bpRef.total > 0 ? (
                  <div className="space-y-0.5 mb-3">
                    {bpRef.blueprints.map(p => (
                      <p key={p} className="text-sm text-blue-400" title={p}>
                        📋 <span className="font-medium">{p.split(/[\\/]/).pop()}</span>
                        <span className="text-gray-600 ml-2 text-xs">{p}</span>
                      </p>
                    ))}
                    {bpRef.maps.map(m => (
                      <p key={m} className="text-sm text-yellow-400" title={m}>
                        🗺️ <span className="font-medium">{m.split(/[\\/]/).pop()}</span>
                        <span className="text-gray-600 ml-2 text-xs">{m}</span>
                      </p>
                    ))}
                  </div>
                ) : !bpLoading && (
                  <p className="text-sm text-gray-500 mb-2">{t('no_bp')}</p>
                )}
                {/* BP 매핑 상세 (K2 오버라이드, 변수, GameplayTag) */}
                {bpMapLoading && (
                  <p className="text-xs text-gray-500 animate-pulse">{t('bp_mapping_loading')}</p>
                )}
                {!bpMapLoading && bpMapping && !bpMapping.startsWith('Error') && (
                  <BpMappingDetail text={bpMapping} />
                )}
              </div>
            )}

              {/* 필드 + 메서드 — 세로 배치로 가로 폭 최대 활용 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

                {/* 필드 */}
                <div className="card overflow-hidden">
                  <div className="px-3 py-2 border-b border-gray-700 bg-gray-800/50">
                    <h3 className="text-sm font-semibold text-gray-200">
                      {t('fields')}
                      <span className="text-gray-500 font-normal ml-1.5">({fields.length})</span>
                    </h3>
                  </div>
                  <div className="overflow-y-auto" style={{ maxHeight: 360 }}>
                    <FieldTable fields={pubFields} />
                    <AccessToggle label="protected" icon="🛡" count={protFields.length}>
                      <FieldTable fields={protFields} dim />
                    </AccessToggle>
                    <AccessToggle label="private" icon="🔒" count={privFields.length}>
                      <FieldTable fields={privFields} dim />
                    </AccessToggle>
                  </div>
                </div>

                {/* 메서드 */}
                <div className="card overflow-hidden">
                  <div className="px-3 py-2 border-b border-gray-700 bg-gray-800/50">
                    <h3 className="text-sm font-semibold text-gray-200">
                      {t('methods')}
                      <span className="text-gray-500 font-normal ml-1.5">({methods.length})</span>
                    </h3>
                  </div>
                  <div className="overflow-y-auto" style={{ maxHeight: 360 }}>
                    <MethodTable methods={methods.filter(m => m.access === 'public')} lifecycleMethods={lcMethods} />
                    <AccessToggle label="protected" icon="🛡" count={methods.filter(m => m.access === 'protected').length}>
                      <MethodTable methods={methods.filter(m => m.access === 'protected')} lifecycleMethods={lcMethods} dim />
                    </AccessToggle>
                    <AccessToggle label="private" icon="🔒" count={methods.filter(m => m.access !== 'public' && m.access !== 'protected').length}>
                      <MethodTable methods={methods.filter(m => m.access !== 'public' && m.access !== 'protected')} lifecycleMethods={lcMethods} dim />
                    </AccessToggle>
                  </div>
                </div>

              </div>

              {/* 메서드 상세 분석 */}
              <div className="card p-4">
                <div className="flex items-center gap-3 mb-4">
                  <h3 className="text-base font-semibold text-gray-100">
                    {t('flow_analysis')}
                    {analyzing && <span className="text-sm text-emerald-400 ml-2 animate-pulse">{t('analyzing')}</span>}
                  </h3>
                </div>

                {/* 라이프사이클 진입점 */}
                {lifecycle.length > 0 && (
                  <div className="mb-5">
                    <p className="text-sm text-yellow-400 font-medium mb-2.5 flex items-center gap-1.5">
                      <Zap size={14}/> {t('lifecycle_entry')}
                    </p>
                    <div className="grid grid-cols-2 gap-1.5">
                      {lifecycle.map(m => {
                        const isExpanded = expandedMethod === `lc_${m.name}`
                        return (
                          <div key={m.name} className={isExpanded ? 'col-span-2' : ''}>
                            <button
                              onClick={() => {
                                const key = `lc_${m.name}`
                                if (expandedMethod === key) { setExpandedMethod(null); return }
                                setExpandedMethod(key)
                                setLogicMethod(m.name); setMethodLogic(null); setMethodLogicLoading(true)
                                setMethodSource(null); setMethodSourceName(null)
                                setMethodCallersResult(null); setMethodCallersName(null)
                                projectApi.explainMethodLogic(scriptsPath, selectedClass, m.name)
                                  .then(setMethodLogic).catch(() => setMethodLogic(null))
                                  .finally(() => setMethodLogicLoading(false))
                              }}
                              title={sig(m)}
                              className={`w-full text-left flex items-center gap-1.5 px-3 py-1.5 rounded
                                         text-sm font-medium transition-colors
                                         ${isExpanded
                                           ? 'bg-yellow-800 border-2 border-yellow-500 text-yellow-100'
                                           : 'bg-yellow-900 hover:bg-yellow-800 border border-yellow-700 text-yellow-200'}`}>
                              <Zap size={12} className="text-yellow-400 shrink-0"/>
                              <span className="truncate">{m.name}</span>
                              <span className="font-mono text-xs text-yellow-400/70 truncate">{sig(m)}</span>
                            </button>
                            {isExpanded && (
                              <MethodLogicPanel
                                methodName={m.name}
                                methodLogic={methodLogic} methodLogicLoading={methodLogicLoading}
                                methodSource={methodSource} methodSourceName={methodSourceName}
                                methodSourceLoading={methodSourceLoading}
                                methodCallersResult={methodCallersResult} methodCallersName={methodCallersName}
                                methodCallersLoading={methodCallersLoading}
                                onViewSource={async () => {
                                  if (methodSourceName === m.name && methodSource) {
                                    setMethodSource(null); setMethodSourceName(null); return
                                  }
                                  setMethodSourceLoading(true)
                                  try {
                                    const res = await projectApi.readSource(scriptsPath, selectedClass, 4000, m.name)
                                    setMethodSource(res.content); setMethodSourceName(m.name)
                                  } catch { setMethodSource(null) }
                                  finally { setMethodSourceLoading(false) }
                                }}
                                onMethodCallers={async () => {
                                  if (methodCallersName === m.name && methodCallersResult) {
                                    setMethodCallersResult(null); setMethodCallersName(null); return
                                  }
                                  setMethodCallersLoading(true)
                                  try {
                                    const res = await analysisNewApi.methodCallers(scriptsPath, selectedClass, m.name)
                                    setMethodCallersResult(res); setMethodCallersName(m.name)
                                  } catch { setMethodCallersResult(null) }
                                  finally { setMethodCallersLoading(false) }
                                }}
                                onRunFlow={() => runFlow(selectedClass, m.name)}
                                analyzing={analyzing} t={t}
                              />
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* 메서드 검색 */}
                <div>
                  <div className="relative mb-3">
                    <Search size={14} className="absolute left-2.5 top-2.5 text-gray-500"/>
                    <input className="input pl-8 text-sm" placeholder={t('method_search_placeholder')}
                      value={methodQuery} onChange={e => setMethodQuery(e.target.value)}/>
                  </div>

                  {/* public 메서드 그리드 */}
                  {pubOther.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">public</p>
                      <MethodCardGrid
                        methods={pubOther} variant="public"
                        expandedMethod={expandedMethod} setExpandedMethod={setExpandedMethod}
                        selectedClass={selectedClass} scriptsPath={scriptsPath}
                        analyzing={analyzing}
                        methodLogic={methodLogic} methodLogicLoading={methodLogicLoading}
                        methodSource={methodSource} methodSourceName={methodSourceName}
                        methodSourceLoading={methodSourceLoading}
                        methodCallersResult={methodCallersResult} methodCallersName={methodCallersName}
                        methodCallersLoading={methodCallersLoading}
                        setLogicMethod={setLogicMethod} setMethodLogic={setMethodLogic}
                        setMethodLogicLoading={setMethodLogicLoading}
                        setMethodSource={setMethodSource} setMethodSourceName={setMethodSourceName}
                        setMethodSourceLoading={setMethodSourceLoading}
                        setMethodCallersResult={setMethodCallersResult}
                        setMethodCallersName={setMethodCallersName}
                        setMethodCallersLoading={setMethodCallersLoading}
                        runFlow={runFlow} t={t}
                      />
                    </div>
                  )}

                  {/* protected 메서드 */}
                  {protOther.length > 0 && (
                    <AccessToggle label="protected" icon="🛡" count={protOther.length}>
                      <MethodCardGrid
                        methods={protOther} variant="protected"
                        expandedMethod={expandedMethod} setExpandedMethod={setExpandedMethod}
                        selectedClass={selectedClass} scriptsPath={scriptsPath}
                        analyzing={analyzing}
                        methodLogic={methodLogic} methodLogicLoading={methodLogicLoading}
                        methodSource={methodSource} methodSourceName={methodSourceName}
                        methodSourceLoading={methodSourceLoading}
                        methodCallersResult={methodCallersResult} methodCallersName={methodCallersName}
                        methodCallersLoading={methodCallersLoading}
                        setLogicMethod={setLogicMethod} setMethodLogic={setMethodLogic}
                        setMethodLogicLoading={setMethodLogicLoading}
                        setMethodSource={setMethodSource} setMethodSourceName={setMethodSourceName}
                        setMethodSourceLoading={setMethodSourceLoading}
                        setMethodCallersResult={setMethodCallersResult}
                        setMethodCallersName={setMethodCallersName}
                        setMethodCallersLoading={setMethodCallersLoading}
                        runFlow={runFlow} t={t}
                      />
                    </AccessToggle>
                  )}

                  {/* private 메서드 */}
                  {privOther.length > 0 && (
                    <AccessToggle label="private" icon="🔒" count={privOther.length}>
                      <MethodCardGrid
                        methods={privOther} variant="private"
                        expandedMethod={expandedMethod} setExpandedMethod={setExpandedMethod}
                        selectedClass={selectedClass} scriptsPath={scriptsPath}
                        analyzing={analyzing}
                        methodLogic={methodLogic} methodLogicLoading={methodLogicLoading}
                        methodSource={methodSource} methodSourceName={methodSourceName}
                        methodSourceLoading={methodSourceLoading}
                        methodCallersResult={methodCallersResult} methodCallersName={methodCallersName}
                        methodCallersLoading={methodCallersLoading}
                        setLogicMethod={setLogicMethod} setMethodLogic={setMethodLogic}
                        setMethodLogicLoading={setMethodLogicLoading}
                        setMethodSource={setMethodSource} setMethodSourceName={setMethodSourceName}
                        setMethodSourceLoading={setMethodSourceLoading}
                        setMethodCallersResult={setMethodCallersResult}
                        setMethodCallersName={setMethodCallersName}
                        setMethodCallersLoading={setMethodCallersLoading}
                        runFlow={runFlow} t={t}
                      />
                    </AccessToggle>
                  )}
                </div>
              </div>

            </div>
          )
        })() : null}
      </div>
    </div>
  )
}
