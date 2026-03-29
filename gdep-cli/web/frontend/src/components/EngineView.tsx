import { useState, useEffect } from 'react'
import dagre from '@dagrejs/dagre'
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState,
  type Node, type Edge, MarkerType, Position,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Search } from 'lucide-react'
import { useApp } from '../store'
import {
  unityApi, ue5Api, engineApi, engineAnalysisApi, analysisNewApi,
  type PrefabRef, type BlueprintRef,
} from '../api/client'
import { ConfidenceFromText } from './ConfidenceBadge'
import MdResult from './MdResult'


// ── 프리팹 역참조 탭 (Unity) ─────────────────────────────────
function PrefabRefsTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [refs,     setRefs]    = useState<Record<string, PrefabRef>>({})
  const [loading,  setLoading] = useState(false)
  const [query,    setQuery]   = useState('')
  const [selected, setSelected] = useState('')
  const [totalCls, setTotalCls] = useState(0)

  useEffect(() => {
    setLoading(true)
    unityApi.getRefs(scriptsPath)
      .then(d => { setRefs(d.refs); setTotalCls(d.total_classes) })
      .catch(() => setRefs({}))
      .finally(() => setLoading(false))
  }, [scriptsPath])

  const used     = Object.entries(refs).sort((a, b) => b[1].total - a[1].total)
  const filtered = query ? used.filter(([n]) => n.toLowerCase().includes(query.toLowerCase())) : used
  const selRef   = selected ? refs[selected] : null

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-64 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="p-3 border-b border-gray-800">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-2.5 text-gray-500"/>
            <input className="input pl-8 text-xs" placeholder={t('dep_class_ph')}
              value={query} onChange={e => setQuery(e.target.value)} />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {loading ? t('analyzing') : `${used.length}${t('count_unit')} ${t('dep_of_total')} ${totalCls}${t('count_unit')}`}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filtered.slice(0, 100).map(([name, ref]) => (
            <button key={name} onClick={() => setSelected(name)}
              className={`w-full text-left text-xs px-2 py-1 rounded flex items-center gap-1
                ${selected === name
                  ? 'bg-blue-900 text-blue-200 border border-blue-700'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
              <span className="truncate flex-1">{name}</span>
              <span className="text-gray-600 shrink-0">{ref.total}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            {t('inh_select')}
          </div>
        ) : selRef ? (
          <div className="max-w-lg space-y-4">
            <div>
              <h2 className="text-lg font-bold text-white">{selected}</h2>
              <p className="text-xs text-gray-500">GUID: {selRef.guid}</p>
            </div>
            {selRef.prefabs.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-2">
                  {t('dep_prefabs_label')} ({selRef.prefabs.length}{t('count_unit')})
                </h3>
                {selRef.prefabs.map(p => (
                  <div key={p} className="text-xs py-1 border-b border-gray-800">
                    <span className="text-blue-400 font-medium">{p.split(/[\\/]/).pop()}</span>
                    <span className="text-gray-600 ml-2">{p}</span>
                  </div>
                ))}
              </div>
            )}
            {selRef.scenes.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-2">
                  {t('dep_scenes_label')} ({selRef.scenes.length}{t('count_unit')})
                </h3>
                {selRef.scenes.map(s => (
                  <div key={s} className="text-xs py-1 border-b border-gray-800">
                    <span className="text-yellow-400 font-medium">{s.split(/[\\/]/).pop()}</span>
                    <span className="text-gray-600 ml-2">{s}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}


// ── 블루프린트 역참조 탭 (UE5) ───────────────────────────────
function BlueprintRefsTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [refs,     setRefs]    = useState<Record<string, BlueprintRef>>({})
  const [loading,  setLoading] = useState(false)
  const [query,    setQuery]   = useState('')
  const [selected, setSelected] = useState('')
  const [totalCls, setTotalCls] = useState(0)

  useEffect(() => {
    setLoading(true)
    ue5Api.getBlueprintRefs(scriptsPath)
      .then(d => { setRefs(d.refs); setTotalCls(d.total_classes) })
      .catch(() => setRefs({}))
      .finally(() => setLoading(false))
  }, [scriptsPath])

  const used     = Object.entries(refs).sort((a, b) => b[1].total - a[1].total)
  const filtered = query ? used.filter(([n]) => n.toLowerCase().includes(query.toLowerCase())) : used
  const selRef   = selected ? refs[selected] : null

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-64 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="p-3 border-b border-gray-800">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-2.5 text-gray-500"/>
            <input className="input pl-8 text-xs" placeholder={t('dep_class_ph')}
              value={query} onChange={e => setQuery(e.target.value)} />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {loading ? t('analyzing') : `${used.length}${t('count_unit')} ${t('dep_of_total')} ${totalCls}${t('count_unit')}`}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filtered.slice(0, 100).map(([name, ref]) => (
            <button key={name} onClick={() => setSelected(name)}
              className={`w-full text-left text-xs px-2 py-1 rounded flex items-center gap-1
                ${selected === name
                  ? 'bg-blue-900 text-blue-200 border border-blue-700'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
              <span className="truncate flex-1">{name}</span>
              <span className="text-gray-600 shrink-0">{ref.total}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            {t('inh_select')}
          </div>
        ) : selRef ? (
          <div className="max-w-lg space-y-4">
            <h2 className="text-lg font-bold text-white">{selected}</h2>
            {selRef.blueprints.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-2">
                  {t('dep_bp_label')} ({selRef.blueprints.length}{t('count_unit')})
                </h3>
                {selRef.blueprints.map(p => (
                  <div key={p} className="text-xs py-1 border-b border-gray-800">
                    <span className="text-blue-400 font-medium">{p.split(/[\\/]/).pop()}</span>
                    <span className="text-gray-600 ml-2">{p}</span>
                  </div>
                ))}
              </div>
            )}
            {selRef.maps.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-300 mb-2">
                  {t('dep_maps_label')} ({selRef.maps.length}{t('count_unit')})
                </h3>
                {selRef.maps.map(m => (
                  <div key={m} className="text-xs py-1 border-b border-gray-800">
                    <span className="text-yellow-400 font-medium">{m.split(/[\\/]/).pop()}</span>
                    <span className="text-gray-600 ml-2">{m}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}


// ── Unity Event 바인딩 탭 ─────────────────────────────────────
function UnityEventsTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [result,  setResult]  = useState('')
  const [loading, setLoading] = useState(false)
  const [filter,  setFilter]  = useState('')

  async function run() {
    setLoading(true)
    try {
      const res = await engineApi.unityEvents(scriptsPath, filter || undefined)
      setResult(res)
    } catch (e: any) {
      setResult(`Error: ${e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input className="input text-sm w-56" placeholder={t('unity_ev_filter_ph')}
          value={filter} onChange={e => setFilter(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()} />
        <button onClick={run} disabled={loading} className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('unity_ev_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('unity_ev_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}

// ── Unity Animator 탭 ─────────────────────────────────────────
function UnityAnimatorTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [result,  setResult]  = useState('')
  const [loading, setLoading] = useState(false)
  const [ctrlName, setCtrlName] = useState('')

  async function run() {
    setLoading(true)
    try {
      const res = await engineApi.unityAnimator(scriptsPath, ctrlName || undefined)
      setResult(res)
    } catch (e: any) {
      setResult(`Error: ${e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input className="input text-sm w-56" placeholder={t('unity_anim_filter_ph')}
          value={ctrlName} onChange={e => setCtrlName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()} />
        <button onClick={run} disabled={loading} className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('unity_anim_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('unity_anim_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}

// ── UE5 GAS 탭 ───────────────────────────────────────────────
const GAS_NODE_COLORS: Record<string, string> = {
  ability:       '#1D6E4E',
  effect:        '#6B3A8A',
  attribute_set: '#1A4A8A',
  tag:           '#7A4500',
  bp_ability:    '#0E4A30',
  bp_effect:     '#3D1F60',
  bp_attr_set:   '#0A2A5A',
}
const GAS_NODE_LABELS: Record<string, string> = {
  ability:    'GA',     effect:      'GE',  attribute_set: 'AS',   tag: 'Tag',
  bp_ability: 'BP·GA',  bp_effect:  'BP·GE',  bp_attr_set: 'BP·AS',
}
const GAS_NODE_BORDERS: Record<string, string> = {
  bp_ability:  '2px dashed #34D399',
  bp_effect:   '2px dashed #A78BFA',
  bp_attr_set: '2px dashed #60A5FA',
}

function GasGraph({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [gasNodes, setGasNodes, onGasNodesChange] = useNodesState<Node>([])
  const [gasEdges, setGasEdges, onGasEdgesChange] = useEdgesState<Edge>([])
  const [summary,  setSummary]  = useState<Record<string, number> | null>(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  async function load() {
    setLoading(true); setError('')
    try {
      const data = await engineApi.ue5GasGraph(scriptsPath)
      if (data.error) { setError(data.error); return }

      const GAS_CHAR_W = 7, GAS_PAD = 32, GAS_NODE_MIN = 110, GAS_NODE_MAX = 280
      const calcGasNodeW = (lbl: string) =>
        Math.min(GAS_NODE_MAX, Math.max(GAS_NODE_MIN, Math.ceil(lbl.length * GAS_CHAR_W) + GAS_PAD))

      const rfNodes: Node[] = data.nodes.map((n) => {
        const label = `[${GAS_NODE_LABELS[n.type] ?? n.type}] ${n.label}`
        const nodeW = calcGasNodeW(label)
        return {
          id:   n.id,
          data: { label, nodeWidth: nodeW },
          position: { x: 0, y: 0 },
          style: {
            background:   GAS_NODE_COLORS[n.type] ?? '#374151',
            color:        '#fff',
            border:       GAS_NODE_BORDERS[n.type] ?? '1px solid rgba(255,255,255,0.15)',
            borderRadius: 8,
            fontSize:     12,
            padding:      '5px 12px',
            width:        nodeW,
            opacity:      n.type.startsWith('bp_') ? 0.88 : 1,
          },
          sourcePosition: Position.Bottom,
          targetPosition: Position.Top,
        }
      })

      const GAS_EDGE_COLORS: Record<string, string> = {
        applies:   '#A78BFA',
        owns:      '#60A5FA',
        uses_tag:  '#FCD34D',
        bp_impl:   '#34D399',
        uses_attr: '#60A5FA',
      }
      const rfEdges: Edge[] = data.edges.map(e => {
        const color = GAS_EDGE_COLORS[e.relation] ?? '#6B7280'
        const isBpImpl = e.relation === 'bp_impl'
        return {
          id:       `${e.from}→${e.to}`,
          source:   e.from,
          target:   e.to,
          label:    e.relation,
          animated: isBpImpl,
          style:    { stroke: color, strokeDasharray: isBpImpl ? '6 3' : undefined },
          markerEnd:    { type: MarkerType.ArrowClosed, color },
          labelStyle:   { fontSize: 10, fill: color },
          labelBgStyle: { fill: '#1F2937' },
        }
      })

      const GAS_NODE_H = 42
      const g = new dagre.graphlib.Graph()
      g.setDefaultEdgeLabel(() => ({}))
      g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 90, marginx: 40, marginy: 40 })
      rfNodes.forEach(n => {
        const w = (n.data as any)?.nodeWidth ?? GAS_NODE_MIN
        g.setNode(n.id, { width: w, height: GAS_NODE_H })
      })
      rfEdges.forEach(e => { if (e.source !== e.target) g.setEdge(e.source, e.target) })
      dagre.layout(g)
      const laidOut = rfNodes.map(n => {
        const pos = g.node(n.id)
        const w = (n.data as any)?.nodeWidth ?? GAS_NODE_MIN
        return pos ? { ...n, position: { x: pos.x - w / 2, y: pos.y - GAS_NODE_H / 2 } } : n
      })

      setGasNodes(laidOut)
      setGasEdges(rfEdges)
      setSummary(data.summary)
    } catch (e: any) {
      setError(e?.message ?? String(e))
    } finally { setLoading(false) }
  }

  if (!summary && !loading && !error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-500">
        <button onClick={load} className="btn-primary text-sm px-5 py-2">
          {t('gas_gen_btn')}
        </button>
        <p className="text-xs">{t('gas_gen_desc')}</p>
      </div>
    )
  }

  if (loading) return <p className="p-4 text-gray-500 animate-pulse">{t('gas_graph_loading')}</p>
  if (error)   return <p className="p-4 text-red-400 text-sm">Error: {error}</p>

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-3 py-2 border-b border-gray-800 shrink-0 flex-wrap">
        {summary && (() => {
          const KEY_MAP: Record<string, { type: string; label: string }> = {
            abilities:    { type: 'ability',    label: 'C++ GA' },
            effects:      { type: 'effect',     label: 'C++ GE' },
            attr_sets:    { type: 'attribute_set', label: 'C++ AS' },
            tags:         { type: 'tag',        label: 'Tag' },
            bp_abilities: { type: 'bp_ability', label: 'BP GA' },
            bp_effects:   { type: 'bp_effect',  label: 'BP GE' },
          }
          return Object.entries(summary).map(([k, v]) => {
            const meta = KEY_MAP[k]
            const color = meta ? GAS_NODE_COLORS[meta.type] : '#374151'
            const label = meta?.label ?? k
            return (
              <span key={k} className="flex items-center gap-1 text-xs text-gray-400">
                <span className="inline-block w-2.5 h-2.5 rounded-sm"
                  style={{ background: color, border: meta?.type.startsWith('bp_') ? '1px dashed rgba(255,255,255,0.4)' : undefined }} />
                {label} <b className="text-white">{v}</b>
              </span>
            )
          })
        })()}
        <button onClick={load} className="ml-auto text-xs text-gray-500 hover:text-gray-300">
          {t('gas_refresh')}
        </button>
      </div>
      <div className="flex-1 min-h-0">
        <ReactFlow
          nodes={gasNodes} edges={gasEdges}
          onNodesChange={onGasNodesChange}
          onEdgesChange={onGasEdgesChange}
          fitView
          attributionPosition="bottom-right"
          style={{ background: '#111827' }}
        >
          <Background color="#374151" gap={20} />
          <Controls />
          <MiniMap nodeColor={n => (n.style?.background as string) ?? '#374151'}
            maskColor="rgba(0,0,0,0.75)" style={{ background: '#1f2937' }} />
        </ReactFlow>
      </div>
    </div>
  )
}

function UE5GasTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [result,      setResult]      = useState('')
  const [loading,     setLoading]     = useState(false)
  const [className,   setClassName]   = useState('')
  const [view,        setView]        = useState<'text' | 'graph'>('graph')
  const [detailLevel, setDetailLevel] = useState<'summary' | 'full'>('summary')
  const [category,    setCategory]    = useState('')
  const [query,       setQuery]       = useState('')

  async function run() {
    setLoading(true)
    try {
      const res = await engineApi.ue5Gas(
        scriptsPath,
        className || undefined,
        detailLevel,
        category || undefined,
        query || undefined,
      )
      setResult(res)
    } catch (e: any) {
      setResult(`Error: ${e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 shrink-0 flex-wrap">
        <div className="flex gap-1">
          {(['graph', 'text'] as const).map(v => (
            <button key={v} onClick={() => setView(v)}
              className={`text-xs px-3 py-1 rounded border transition-colors
                ${view === v
                  ? 'border-emerald-500 text-emerald-400 bg-emerald-950'
                  : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
              {v === 'graph' ? t('gas_view_graph') : t('gas_view_text')}
            </button>
          ))}
        </div>
        {view === 'text' && (
          <>
            <div className="flex gap-1">
              {(['summary', 'full'] as const).map(lv => (
                <button key={lv} onClick={() => setDetailLevel(lv)}
                  className={`text-xs px-2 py-1 rounded border transition-colors
                    ${detailLevel === lv
                      ? 'border-violet-500 text-violet-400 bg-violet-950'
                      : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                  {lv}
                </button>
              ))}
            </div>
            <input className="input text-sm w-32" placeholder="class filter"
              value={className} onChange={e => setClassName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()} />
            <input className="input text-sm w-28" placeholder="tag prefix"
              value={category} onChange={e => setCategory(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()} />
            <input className="input text-sm w-28" placeholder="keyword"
              value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && run()} />
            <button onClick={run} disabled={loading}
              className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
              {loading ? t('analyzing') : t('gas_analyze_btn')}
            </button>
          </>
        )}
        <p className="text-xs text-gray-500">
          {view === 'graph' ? t('gas_graph_flow_desc') : t('gas_text_desc')}
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        {view === 'graph'
          ? <GasGraph scriptsPath={scriptsPath} />
          : (
            <div className="flex-1 overflow-y-auto h-full border-0 p-4">
              {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
              <MdResult text={result} loading={loading} />
            </div>
          )
        }
      </div>
    </div>
  )
}

// ── UE5 Animation 탭 (ABP + Montage) ─────────────────────────
function UE5AnimationTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [result,      setResult]      = useState('')
  const [loading,     setLoading]     = useState(false)
  const [assetType,   setAssetType]   = useState<'all'|'abp'|'montage'>('all')
  const [detailLevel, setDetailLevel] = useState<'summary'|'full'>('summary')

  async function run() {
    setLoading(true)
    try {
      const res = await engineApi.ue5Animation(scriptsPath, assetType, detailLevel)
      setResult(res)
    } catch (e: any) {
      setResult(`Error: ${e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <div className="flex gap-1">
          {(['all','abp','montage'] as const).map(v => (
            <button key={v} onClick={() => setAssetType(v)}
              className={`text-xs px-3 py-1 rounded border transition-colors
                ${assetType === v
                  ? 'border-emerald-500 text-emerald-400 bg-emerald-950'
                  : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
              {v === 'all' ? t('anim_all') : v === 'abp' ? 'ABP' : 'Montage'}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(['summary','full'] as const).map(d => (
            <button key={d} onClick={() => setDetailLevel(d)}
              className={`text-xs px-3 py-1 rounded border transition-colors
                ${detailLevel === d
                  ? 'border-blue-500 text-blue-400 bg-blue-950'
                  : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
              {d === 'summary' ? t('anim_summary') : t('anim_full')}
            </button>
          ))}
        </div>
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('anim_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('anim_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}

// ── UE5 AI (BT + StateTree) 탭 ───────────────────────────────
function UE5AITab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [btResult,  setBtResult]  = useState('')
  const [stResult,  setStResult]  = useState('')
  const [loadingBt, setLoadingBt] = useState(false)
  const [loadingSt, setLoadingSt] = useState(false)
  const [activeAi,  setActiveAi]  = useState<'bt'|'st'>('bt')

  async function runBT() {
    setLoadingBt(true)
    try {
      const res = await engineApi.ue5BehaviorTree(scriptsPath)
      setBtResult(res)
    } catch (e: any) { setBtResult(`Error: ${e?.message ?? e}`) }
    finally { setLoadingBt(false) }
  }

  async function runST() {
    setLoadingSt(true)
    try {
      const res = await engineApi.ue5StateTree(scriptsPath)
      setStResult(res)
    } catch (e: any) { setStResult(`Error: ${e?.message ?? e}`) }
    finally { setLoadingSt(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <div className="flex gap-1">
          <button onClick={() => setActiveAi('bt')}
            className={`text-xs px-3 py-1 rounded border transition-colors
              ${activeAi==='bt' ? 'border-orange-500 text-orange-400 bg-orange-950' : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
            {t('ai_bt_tab')}
          </button>
          <button onClick={() => setActiveAi('st')}
            className={`text-xs px-3 py-1 rounded border transition-colors
              ${activeAi==='st' ? 'border-purple-500 text-purple-400 bg-purple-950' : 'border-gray-700 text-gray-400 hover:border-gray-500'}`}>
            {t('ai_st_tab')}
          </button>
        </div>
        {activeAi === 'bt' ? (
          <button onClick={runBT} disabled={loadingBt}
            className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
            {loadingBt ? t('analyzing') : t('ai_bt_btn')}
          </button>
        ) : (
          <button onClick={runST} disabled={loadingSt}
            className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
            {loadingSt ? t('analyzing') : t('ai_st_btn')}
          </button>
        )}
        <p className="text-xs text-gray-500">
          {activeAi === 'bt' ? t('ai_bt_desc') : t('ai_st_desc')}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {activeAi === 'bt'
          ? <MdResult text={btResult}  loading={loadingBt} />
          : <MdResult text={stResult}  loading={loadingSt} />}
      </div>
    </div>
  )
}

// ── UE5 Blueprint ↔ C++ 매핑 탭 ─────────────────────────────
function UE5BpMappingTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [result,    setResult]    = useState('')
  const [loading,   setLoading]   = useState(false)
  const [cppClass,  setCppClass]  = useState('')
  const [total,     setTotal]     = useState<number | undefined>()

  async function run() {
    setLoading(true); setResult(''); setTotal(undefined)
    try {
      const res = await ue5Api.getBlueprintMapping(scriptsPath, cppClass || undefined)
      setResult(res.result)
      setTotal(res.total)
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input
          className="input text-sm w-64"
          placeholder={t('bp_map_input_ph')}
          value={cppClass}
          onChange={e => setCppClass(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
        />
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('bp_map_btn')}
        </button>
        {total !== undefined && !loading && (
          <span className="text-xs text-blue-400">
            Blueprint {total}{t('count_unit')} {t('bp_found_label')}
          </span>
        )}
        <p className="text-xs text-gray-500">{t('bp_map_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}

// ── Unused Assets Tab ─────────────────────────────────────────
function UnusedAssetsTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [scanDir,    setScanDir]    = useState('')
  const [maxResults, setMaxResults] = useState(50)
  const [loading,    setLoading]    = useState(false)
  const [result,     setResult]     = useState('')

  async function run() {
    setLoading(true); setResult('')
    try {
      const res = await analysisNewApi.unusedAssets(scriptsPath, scanDir || undefined, maxResults)
      setResult(res)
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input
          className="input text-sm w-64"
          placeholder={t('unused_scan_dir_ph')}
          value={scanDir}
          onChange={e => setScanDir(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
        />
        <input
          type="number" min={10} max={200}
          className="input text-sm w-24"
          placeholder={t('unused_max_ph')}
          value={maxResults}
          onChange={e => setMaxResults(Number(e.target.value) || 50)}
        />
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('unused_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('unused_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}

// ── Axmol Events 탭 ─────────────────────────────────────────
function AxmolEventsTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [methodFilter, setMethodFilter] = useState('')
  const [loading,      setLoading]      = useState(false)
  const [result,       setResult]       = useState('')

  async function run() {
    setLoading(true); setResult('')
    try {
      const res = await engineAnalysisApi.axmolEvents(scriptsPath, methodFilter || undefined)
      setResult(res.result)
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input
          className="input text-sm w-64"
          placeholder={t('axmol_filter_ph')}
          value={methodFilter}
          onChange={e => setMethodFilter(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
        />
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('axmol_analyze_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('axmol_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {result && !loading && <div className="mb-2"><ConfidenceFromText text={result} /></div>}
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}


// ── 메인 EngineView 컴포넌트 ────────────────────────────────
type EngineTabId = 'prefabs' | 'blueprints' | 'unity_events' | 'unity_animator'
                 | 'ue5_gas' | 'ue5_animation' | 'ue5_ai' | 'ue5_bp_mapping'
                 | 'axmol_events' | 'unused_assets'

export default function EngineView() {
  const { scriptsPath, projectInfo, t } = useApp()
  const [activeTab, setActiveTab] = useState<EngineTabId | ''>('')

  const isAxmol  = !!(projectInfo?.engine?.startsWith('Axmol'))
  const isUnity  = projectInfo?.kind === 'UNITY'
  const isUnreal = projectInfo?.kind === 'UNREAL'

  if (!scriptsPath) return (
    <div className="flex items-center justify-center h-full text-gray-500">
      {t('dep_no_path')}
    </div>
  )

  // 엔진별 탭 목록
  const tabs: [EngineTabId, string][] = []
  if (isUnity) {
    tabs.push(
      ['prefabs',        t('dep_prefabs')],
      ['unity_events',   t('dep_unity_events')],
      ['unity_animator',  t('dep_unity_anim')],
      ['unused_assets',   t('dep_unused_assets')],
    )
  }
  if (isUnreal) {
    tabs.push(
      ['blueprints',     t('dep_blueprints')],
      ['ue5_gas',        t('dep_ue5_gas')],
      ['ue5_animation',  t('dep_ue5_anim')],
      ['ue5_ai',         t('dep_ue5_ai')],
      ['ue5_bp_mapping',  t('dep_ue5_bp_map')],
      ['unused_assets',   t('dep_unused_assets')],
    )
  }
  if (isAxmol) {
    tabs.push(
      ['axmol_events', t('dep_axmol_events')],
    )
  }

  // 엔진 미감지
  if (tabs.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        {t('engine_no_engine')}
      </div>
    )
  }

  // 첫 탭 자동 선택
  const currentTab = (activeTab && tabs.some(([id]) => id === activeTab))
    ? activeTab
    : tabs[0][0]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 서브탭 바 — 수평 스크롤, 드롭다운 없음 */}
      <div className="flex border-b border-gray-800 bg-gray-950 shrink-0 items-stretch overflow-x-auto px-2"
        style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => setActiveTab(id)}
            className={`px-3 py-2.5 text-sm transition-colors whitespace-nowrap shrink-0
              ${currentTab === id ? 'tab-active' : 'tab-inactive'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      <div className="flex-1 overflow-hidden">
        {currentTab === 'prefabs'        && <PrefabRefsTab    scriptsPath={scriptsPath}/>}
        {currentTab === 'blueprints'     && <BlueprintRefsTab scriptsPath={scriptsPath}/>}
        {currentTab === 'unity_events'   && <UnityEventsTab   scriptsPath={scriptsPath}/>}
        {currentTab === 'unity_animator' && <UnityAnimatorTab scriptsPath={scriptsPath}/>}
        {currentTab === 'ue5_gas'        && <UE5GasTab        scriptsPath={scriptsPath}/>}
        {currentTab === 'ue5_animation'  && <UE5AnimationTab  scriptsPath={scriptsPath}/>}
        {currentTab === 'ue5_ai'         && <UE5AITab         scriptsPath={scriptsPath}/>}
        {currentTab === 'ue5_bp_mapping' && <UE5BpMappingTab  scriptsPath={scriptsPath}/>}
        {currentTab === 'axmol_events'   && <AxmolEventsTab   scriptsPath={scriptsPath}/>}
        {currentTab === 'unused_assets'  && <UnusedAssetsTab  scriptsPath={scriptsPath}/>}
      </div>
    </div>
  )
}
