import { useState, useEffect } from 'react'
import dagre from '@dagrejs/dagre'
import {
  ReactFlow, Background, Controls,
  useNodesState, useEdgesState,
  type Node, type Edge, MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Search } from 'lucide-react'
import { useApp } from '../store'
import {
  projectApi, classesApi, ue5Api, analysisApi, analysisNewApi,
  type CouplingItem, type ClassInfo, type BlueprintRef,
  type DeadNode, type ImpactNode, type TestScopeFile, type LintFixIssue,
} from '../api/client'
import MdResult from './MdResult'


// ── 상속 그래프 빌더 ─────────────────────────────────────────
function buildInheritanceGraph(target: string, classMap: Record<string, ClassInfo>) {
  const nodeSet = new Set<string>()
  const edgeSet = new Set<string>()
  const ns: Node[] = []
  const es: Edge[] = []

  function addNode(name: string, center = false) {
    if (nodeSet.has(name)) return
    nodeSet.add(name)
    ns.push({
      id: name, data: { label: name },
      position: { x: 0, y: 0 },
      style: {
        background: center ? '#1D9E75' : '#7F77DD', color: '#fff',
        border: center ? '2px solid #34D399' : '1px solid #6366F1',
        borderRadius: 8, fontSize: 12, padding: '6px 12px',
        fontWeight: center ? 700 : 400,
      },
    })
  }

  function findParents(cls: string, d: number) {
    if (d <= 0) return
    for (const b of classMap[cls]?.bases ?? []) {
      if (!classMap[b]) continue
      addNode(b)
      const key = `${cls}→${b}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        es.push({
          id: key, source: cls, target: b, label: 'extends',
          style: { stroke: '#7F77DD' },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#7F77DD' },
          labelStyle: { fontSize: 10, fill: '#9CA3AF' },
          labelBgStyle: { fill: '#1F2937' },
        })
      }
      findParents(b, d - 1)
    }
  }

  function findChildren(cls: string, d: number) {
    if (d <= 0) return
    for (const [name, data] of Object.entries(classMap)) {
      if (!data.bases.includes(cls)) continue
      addNode(name)
      const key = `${name}→${cls}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        es.push({
          id: key, source: name, target: cls, label: 'extends',
          style: { stroke: '#7F77DD' },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#7F77DD' },
          labelStyle: { fontSize: 10, fill: '#9CA3AF' },
          labelBgStyle: { fill: '#1F2937' },
        })
      }
      findChildren(name, d - 1)
    }
  }

  addNode(target, true)
  findParents(target, 3)
  findChildren(target, 3)

  const arr = Array.from(nodeSet)
  arr.forEach((name, i) => {
    const n = ns.find(x => x.id === name)!
    n.position = name === target
      ? { x: 280, y: 180 }
      : { x: (i % 4) * 200, y: Math.floor(i / 4) * 120 }
  })

  return { nodes: ns, edges: es }
}


// ── 결합도 탭 ────────────────────────────────────────────────
function CouplingTab({ scriptsPath }: { scriptsPath: string }) {
  const { getCache, setCache, t } = useApp()
  const [coupling, setCoupling] = useState<CouplingItem[]>([])
  const [cycles,   setCycles]   = useState<string[]>([])
  const [loading,  setLoading]  = useState(false)

  useEffect(() => {
    const cached = getCache(scriptsPath).scanResult
    if (cached) { setCoupling(cached.coupling); setCycles(cached.cycles); return }
    setLoading(true)
    projectApi.scan(scriptsPath, 50, true)
      .then(d => {
        setCoupling(d.coupling); setCycles(d.cycles)
        setCache(scriptsPath, { scanResult: d })
      })
      .finally(() => setLoading(false))
  }, [scriptsPath])

  const direct   = cycles.filter(c => c.split('→').length <= 2)
  const indirect = cycles.filter(c => c.split('→').length > 2)

  return (
    <div className="flex gap-6 p-4 h-full overflow-y-auto">
      <div className="flex-1 max-w-lg">
        <p className="text-xs text-gray-500 mb-3">
          {t('coupling_desc')}
          <span className="text-red-400 ml-1">{t('coupling_danger')}</span>
          <span className="text-yellow-400 ml-1">{t('coupling_warn')}</span>
          <span className="text-emerald-400 ml-1">{t('coupling_ok')}</span>
        </p>
        {loading && <p className="text-gray-500 text-sm animate-pulse">{t('coupling_analyzing')}</p>}
        <div className="space-y-1.5">
          {coupling.map((item, idx) => {
            const color = item.score >= 10 ? '#E24B4A' : item.score >= 5 ? '#EF9F27' : '#1D9E75'
            const rank  = item.rank ?? idx + 1
            return (
              <div key={item.name} className="flex items-center gap-3 py-1">
                <span className="text-xs text-gray-500 w-5 text-right">{rank}</span>
                <span className="text-sm w-44 truncate text-gray-200">{item.name}</span>
                <div className="flex items-center gap-1.5 flex-1">
                  <div className="h-1.5 rounded"
                    style={{ width: Math.min(item.score / 2 + 1, 20) * 8, background: color }} />
                  <span className="text-sm font-mono" style={{ color }}>{item.score}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="w-72 shrink-0">
        <h3 className="text-sm font-medium text-gray-300 mb-3">
          {t('cycle_label')}
          {cycles.length > 0 && (
            <span className="ml-2 bg-red-900 text-red-300 text-xs px-1.5 py-0.5 rounded-full">
              {cycles.length}
            </span>
          )}
        </h3>
        {cycles.length === 0
          ? <p className="text-emerald-400 text-sm">{t('cycle_none')}</p>
          : <>
            {direct.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-red-400 mb-1">{t('cycle_direct')} {direct.length}</p>
                {direct.map((c, i) => (
                  <div key={i} className="text-xs font-mono bg-red-950 border border-red-900
                                          rounded px-2 py-1 mb-1 text-gray-300">↻ {c}</div>
                ))}
              </div>
            )}
            {indirect.length > 0 && (
              <div>
                <p className="text-xs text-yellow-400 mb-1">{t('cycle_indirect')} {indirect.length}</p>
                {indirect.map((c, i) => (
                  <div key={i} className="text-xs font-mono bg-gray-900 border border-gray-700
                                          rounded px-2 py-1 mb-1 text-gray-400">↻ {c}</div>
                ))}
              </div>
            )}
          </>
        }
      </div>
    </div>
  )
}


// ── 상속 관계 탭 ─────────────────────────────────────────────
function InheritanceTab({
  scriptsPath,
  isUnreal,
}: {
  scriptsPath: string
  isUnreal:    boolean
}) {
  const { getCache, setCache, t } = useApp()
  const [classMap, setClassMap] = useState<Record<string, ClassInfo>>({})
  const [loading,  setLoading]  = useState(false)
  const [query,    setQuery]    = useState('')
  const [selected, setSelected] = useState('')
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [bpRef,     setBpRef]    = useState<BlueprintRef | null>(null)
  const [bpLoading, setBpLoading] = useState(false)
  const [hierarchyDir,     setHierarchyDir]     = useState<'up'|'down'|'both'>('both')
  const [hierarchyResult,  setHierarchyResult]  = useState('')
  const [hierarchyLoading, setHierarchyLoading] = useState(false)

  useEffect(() => {
    const cached = getCache(scriptsPath).classMap
    if (cached) { setClassMap(cached); return }
    setLoading(true)
    classesApi.list(scriptsPath)
      .then(d => { setClassMap(d.classes); setCache(scriptsPath, { classMap: d.classes }) })
      .finally(() => setLoading(false))
  }, [scriptsPath])

  useEffect(() => {
    if (!selected || !isUnreal) { setBpRef(null); return }
    setBpLoading(true)
    ue5Api.getClassBlueprintRefs(scriptsPath, selected)
      .then(r => setBpRef(r.total > 0 ? r : null))
      .catch(() => setBpRef(null))
      .finally(() => setBpLoading(false))
  }, [selected, scriptsPath, isUnreal])

  const classesWithRel = Object.keys(classMap).filter(name => {
    const d = classMap[name]
    return d.bases.length > 0 || Object.values(classMap).some(x => x.bases.includes(name))
  }).sort()

  const filtered = query
    ? classesWithRel.filter(c => c.toLowerCase().includes(query.toLowerCase()))
    : classesWithRel

  function selectClass(name: string) {
    setSelected(name)
    const { nodes: ns, edges: es } = buildInheritanceGraph(name, classMap)
    setNodes(ns); setEdges(es)
  }

  const cls      = selected ? classMap[selected] : null
  const parents  = cls ? cls.bases.filter(b => classMap[b]) : []
  const children = selected
    ? Object.keys(classMap).filter(n => classMap[n].bases.includes(selected))
    : []

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-56 shrink-0 border-r border-gray-800 flex flex-col">
        <div className="p-3 border-b border-gray-800">
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-2.5 text-gray-500"/>
            <input className="input pl-8 text-xs" placeholder="Class..."
              value={query} onChange={e => setQuery(e.target.value)} />
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {filtered.length} {loading && <span className="animate-pulse">{t('inh_loading')}</span>}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {filtered.slice(0, 150).map(name => (
            <button key={name} onClick={() => selectClass(name)}
              className={`w-full text-left text-xs px-2 py-1 rounded truncate
                ${selected === name
                  ? 'bg-purple-900 text-purple-200 border border-purple-700'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'}`}>
              {name}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            {t('inh_select')}
          </div>
        ) : (
          <>
            <div className="p-3 border-b border-gray-800 flex gap-8 shrink-0 flex-wrap">
              <div>
                <p className="text-xs text-gray-500 mb-1">{t('inh_parent')}</p>
                {parents.length === 0
                  ? <p className="text-xs text-gray-600">{t('inh_none')}</p>
                  : parents.map(p => (
                    <button key={p} onClick={() => selectClass(p)}
                      className="text-xs text-purple-400 hover:text-purple-300 block">{p}</button>
                  ))}
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">{t('inh_child')} ({children.length})</p>
                <div className="max-h-20 overflow-y-auto">
                  {children.length === 0
                    ? <p className="text-xs text-gray-600">{t('inh_none')}</p>
                    : children.slice(0, 20).map(c => (
                      <button key={c} onClick={() => selectClass(c)}
                        className="text-xs text-emerald-400 hover:text-emerald-300 block">{c}</button>
                    ))
                  }
                </div>
              </div>

              <div>
                <p className="text-xs text-gray-500 mb-1">{t('inh_hierarchy_btn')}</p>
                <div className="flex gap-1 mb-1">
                  {(['up', 'down', 'both'] as const).map(d => (
                    <button key={d} onClick={() => setHierarchyDir(d)}
                      className={`text-xs px-2 py-0.5 rounded ${
                        hierarchyDir === d ? 'bg-indigo-700 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                      }`}>
                      {t(d === 'up' ? 'inh_dir_up' : d === 'down' ? 'inh_dir_down' : 'inh_dir_both')}
                    </button>
                  ))}
                </div>
                <button
                  onClick={async () => {
                    setHierarchyLoading(true); setHierarchyResult('')
                    try {
                      const res = await analysisNewApi.hierarchy(scriptsPath, selected, hierarchyDir)
                      setHierarchyResult(res)
                    } catch (e: any) {
                      setHierarchyResult(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
                    } finally { setHierarchyLoading(false) }
                  }}
                  disabled={hierarchyLoading}
                  className="btn-primary text-xs px-3 py-1 disabled:opacity-50">
                  {hierarchyLoading ? t('analyzing') : t('inh_hierarchy_btn')}
                </button>
              </div>

              {isUnreal && (
                <div>
                  <p className="text-xs text-gray-500 mb-1">{t('inh_bp_usage')}</p>
                  {bpLoading ? (
                    <p className="text-xs text-gray-600 animate-pulse">{t('inh_loading')}</p>
                  ) : bpRef && bpRef.total > 0 ? (
                    <div className="space-y-0.5 max-h-20 overflow-y-auto">
                      {(bpRef.blueprints ?? []).map(p => (
                        <p key={p} className="text-xs text-blue-400 truncate max-w-48" title={p}>
                          {p.split(/[\\/]/).pop()}
                        </p>
                      ))}
                      {(bpRef.maps ?? []).map(m => (
                        <p key={m} className="text-xs text-yellow-400 truncate max-w-48" title={m}>
                          {m.split(/[\\/]/).pop()}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-gray-600">{t('inh_no_usage')}</p>
                  )}
                </div>
              )}
            </div>

            <div className="flex-1 min-h-0 flex flex-col">
              <div className={hierarchyResult ? 'h-1/2 min-h-0' : 'flex-1 min-h-0'}>
                {nodes.length > 1 ? (
                  <ReactFlow
                    nodes={nodes} edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    fitView
                    attributionPosition="bottom-right"
                    style={{ background: '#111827' }}
                  >
                    <Background color="#374151" gap={20}/>
                    <Controls/>
                  </ReactFlow>
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                    {t('inh_no_rel')}
                  </div>
                )}
              </div>
              {(hierarchyResult || hierarchyLoading) && (
                <div className="h-1/2 min-h-0 border-t border-gray-800 overflow-y-auto p-3 bg-gray-900/50">
                  <MdResult text={hierarchyResult} loading={hierarchyLoading} />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}


// ── Dead Code 탭 ─────────────────────────────────────────────
function DeadCodeTab({ scriptsPath, isUnity }: { scriptsPath: string; isUnity: boolean }) {
  const { t } = useApp()
  const [nodes,   setNodes]   = useState<DeadNode[]>([])
  const [loading, setLoading] = useState(false)
  const [query,   setQuery]   = useState('')
  const [loaded,  setLoaded]  = useState(false)

  function load() {
    setLoading(true)
    projectApi.scan(scriptsPath, 20, false, true, false, isUnity)
      .then(d => { setNodes(d.deadNodes ?? []); setLoaded(true) })
      .catch(() => setNodes([]))
      .finally(() => setLoading(false))
  }

  const filtered = query
    ? nodes.filter(n => n.name.toLowerCase().includes(query.toLowerCase())
                     || n.ns.toLowerCase().includes(query.toLowerCase()))
    : nodes

  return (
    <div className="flex flex-col h-full overflow-hidden p-4 gap-3">
      <div className="flex items-center gap-3 shrink-0">
        <div className="relative flex-1 max-w-sm">
          <Search size={13} className="absolute left-2.5 top-2.5 text-gray-500"/>
          <input className="input pl-8 text-sm" placeholder={t('dead_search_ph')}
            value={query} onChange={e => setQuery(e.target.value)}/>
        </div>
        <button onClick={load} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : loaded ? t('dead_reanalyze') : t('dead_analyze_btn')}
        </button>
        {loaded && (
          <span className="text-sm text-gray-400">
            {nodes.length === 0
              ? <span className="text-emerald-400">{t('dead_none_found')}</span>
              : <span className="text-yellow-400">{filtered.length} / {nodes.length}{t('count_unit')}</span>}
          </span>
        )}
      </div>

      {!loaded ? (
        <div className="flex items-center justify-center flex-1 text-gray-500 text-sm">
          {t('dead_hint')}
        </div>
      ) : nodes.length === 0 ? (
        <div className="flex items-center justify-center flex-1 text-emerald-400 text-sm">
          {t('dead_all_ok')}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-gray-900">
              <tr className="text-left text-xs text-gray-500 border-b border-gray-700">
                <th className="py-2 px-3 w-1/3">{t('dead_col_class')}</th>
                <th className="py-2 px-3 w-1/4">{t('dead_col_ns')}</th>
                <th className="py-2 px-3">{t('dead_col_file')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(n => (
                <tr key={n.name} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="py-1.5 px-3 text-yellow-300 font-medium">{n.name}</td>
                  <td className="py-1.5 px-3 text-gray-400">{n.ns || '—'}</td>
                  <td className="py-1.5 px-3 text-gray-500 text-xs font-mono truncate max-w-xs"
                      title={n.file}>{n.file}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}


// ── Impact 탭 ─────────────────────────────────────────────────
function ImpactTreeNode({ node, depth = 0 }: { node: ImpactNode; depth?: number }) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = node.children.length > 0
  const indent = depth * 20

  return (
    <div>
      <div className="flex items-center gap-1.5 py-1 hover:bg-gray-800/50 rounded px-2 cursor-pointer"
           style={{ paddingLeft: indent + 8 }}
           onClick={() => hasChildren && setOpen(v => !v)}>
        {hasChildren
          ? <span className="text-gray-500 text-xs w-3">{open ? '▼' : '▶'}</span>
          : <span className="text-gray-700 text-xs w-3">•</span>}
        <span className={`text-sm font-medium ${depth === 0 ? 'text-emerald-300' : 'text-gray-200'}`}>
          {node.name}
        </span>
        {node.file && (
          <span className="text-xs text-gray-600 truncate ml-1" title={node.file}>
            {node.file.split(/[\\/]/).pop()}
          </span>
        )}
        {hasChildren && (
          <span className="text-xs text-gray-600 ml-1">({node.children.length})</span>
        )}
      </div>
      {open && hasChildren && node.children.map((child, i) => (
        <ImpactTreeNode key={`${child.name}-${i}`} node={child} depth={depth + 1}/>
      ))}
    </div>
  )
}

function ImpactTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [className, setClassName] = useState('')
  const [depth,     setDepth]     = useState(3)
  const [loading,   setLoading]   = useState(false)
  const [tree,      setTree]      = useState<ImpactNode | null>(null)
  const [total,     setTotal]     = useState(0)

  async function run() {
    if (!className.trim()) return
    setLoading(true); setTree(null)
    try {
      const res = await projectApi.impact(scriptsPath, className.trim(), depth)
      setTree(res.tree); setTotal(res.total_affected)
    } catch { setTree(null) }
    finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden p-4 gap-3">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input
          className="input text-sm w-64"
          placeholder={t('impact_class_ph')}
          value={className}
          onChange={e => setClassName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()}
        />
        <select
          className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300"
          value={depth}
          onChange={e => setDepth(Number(e.target.value))}
        >
          {[1,2,3,4,5].map(d => <option key={d} value={d}>depth {d}</option>)}
        </select>
        <button onClick={run} disabled={loading || !className.trim()}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('impact_btn')}
        </button>
        {tree && !loading && (
          <span className="text-sm text-yellow-400">{t('impact_affected')} {total}{t('count_unit')}</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-3">
        {loading && <p className="text-gray-500 text-sm animate-pulse">{t('analyzing')}</p>}
        {tree && !loading && <ImpactTreeNode node={tree}/>}
        {!tree && !loading && (
          <p className="text-gray-600 text-sm">{t('impact_hint')}</p>
        )}
      </div>
    </div>
  )
}


// ── 테스트 범위 탭 ───────────────────────────────────────────
function TestScopeTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [className, setClassName] = useState('')
  const [depth,     setDepth]     = useState(3)
  const [loading,   setLoading]   = useState(false)
  const [result,    setResult]    = useState<{ target_class: string; affected_count: number; test_file_count: number; test_files: TestScopeFile[] } | null>(null)
  const [error,     setError]     = useState('')

  async function run() {
    if (!className.trim()) return
    setLoading(true); setResult(null); setError('')
    try {
      const res = await analysisApi.testScope(scriptsPath, className.trim(), depth)
      setResult(res)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? String(e))
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input className="input text-sm w-64" placeholder={t('test_class_input_ph')}
          value={className} onChange={e => setClassName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()} />
        <select className="bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300"
          value={depth} onChange={e => setDepth(Number(e.target.value))}>
          {[1,2,3,4,5].map(d => <option key={d} value={d}>depth {d}</option>)}
        </select>
        <button onClick={run} disabled={loading || !className.trim()}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('test_run_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('test_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {loading && <p className="text-gray-400 animate-pulse">{t('analyzing')}</p>}
        {error   && <p className="text-red-400 text-sm">{error}</p>}
        {result  && !loading && (
          <div className="space-y-4">
            <div className="flex gap-4 text-sm">
              <span className="text-gray-400">{t('test_target_label')} <span className="text-white font-medium">{result.target_class}</span></span>
              <span className="text-gray-400">{t('test_affected_label')} <span className="text-yellow-400 font-medium">{result.affected_count}{t('count_unit')}</span></span>
              <span className="text-gray-400">{t('test_files_count')} <span className="text-green-400 font-medium">{result.test_file_count}{t('count_unit')}</span></span>
            </div>
            {result.test_files.length === 0 ? (
              <p className="text-gray-500 text-sm">{t('test_no_match')}</p>
            ) : (
              <div className="space-y-1">
                {result.test_files.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-gray-800/50 group">
                    <span className="text-green-400 text-xs font-mono shrink-0">✓</span>
                    <span className="text-xs text-gray-300 font-mono flex-1 truncate cursor-pointer hover:text-white"
                      title={f.path} onClick={() => navigator.clipboard.writeText(f.path)}>{f.path}</span>
                    {f.matched_class && <span className="text-xs text-indigo-400 shrink-0">{f.matched_class}</span>}
                    <span className="text-xs text-gray-600 shrink-0">{f.engine}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {!loading && !error && !result && <p className="text-gray-600 text-sm">{t('test_run_hint')}</p>}
      </div>
    </div>
  )
}


// ── 아키텍처 어드바이저 탭 ───────────────────────────────────
function AdviseTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [focusClass, setFocusClass] = useState('')
  const [loading,    setLoading]    = useState(false)
  const [report,     setReport]     = useState('')

  async function run() {
    setLoading(true); setReport('')
    try {
      const res = await analysisApi.advise(scriptsPath, focusClass || undefined)
      setReport(res.report)
    } catch (e: any) {
      setReport(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input className="input text-sm w-64" placeholder={t('advise_focus_ph')}
          value={focusClass} onChange={e => setFocusClass(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()} />
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('advise_diagnosing') : t('advise_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('advise_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        <MdResult text={report} loading={loading} />
      </div>
    </div>
  )
}


// ── Lint Fix 탭 ──────────────────────────────────────────────
function LintFixTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [loading, setLoading] = useState(false)
  const [total,   setTotal]   = useState<number | null>(null)
  const [fixable, setFixable] = useState<number | null>(null)
  const [issues,  setIssues]  = useState<LintFixIssue[]>([])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [error,    setError]    = useState('')

  async function run() {
    setLoading(true); setIssues([]); setTotal(null); setFixable(null); setError('')
    try {
      const res = await analysisApi.lintFix(scriptsPath)
      setTotal(res.total); setFixable(res.fixable); setIssues(res.results)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? String(e))
    } finally { setLoading(false) }
  }

  function toggleExpand(i: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const severityColor = (s: string) =>
    s === 'Error' ? 'text-red-400' : s === 'Warning' ? 'text-yellow-400' : 'text-blue-400'

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('lint_scanning') : t('lint_fix_scan_btn')}
        </button>
        {total !== null && !loading && (
          <div className="flex gap-3 text-sm">
            <span className="text-gray-400">{t('lint_fix_total_lbl')} <span className="text-white font-medium">{total}{t('count_unit')}</span></span>
            <span className="text-gray-400">{t('lint_fix_fixable_lbl')} <span className="text-green-400 font-medium">{fixable}{t('count_unit')}</span></span>
          </div>
        )}
        <p className="text-xs text-gray-500">{t('lint_fix_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        {loading && <p className="text-gray-400 animate-pulse">{t('lint_scanning')}</p>}
        {error   && <p className="text-red-400 text-sm">{error}</p>}
        {!loading && issues.length === 0 && total !== null && <p className="text-gray-500 text-sm">{t('lint_fix_none_found')}</p>}
        {!loading && total === null && !error && <p className="text-gray-600 text-sm">{t('lint_fix_run_hint')}</p>}
        <div className="space-y-2">
          {issues.map((issue, i) => (
            <div key={i} className="border border-gray-700 rounded overflow-hidden">
              <button onClick={() => toggleExpand(i)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-800/50 transition-colors">
                <span className={`text-xs font-bold shrink-0 ${severityColor(issue.severity)}`}>[{issue.severity}]</span>
                <span className="text-xs text-purple-400 font-mono shrink-0">{issue.rule_id}</span>
                <span className="text-sm text-gray-300 flex-1 truncate">
                  {issue.class_name}{issue.method_name ? `.${issue.method_name}` : ''}
                </span>
                <span className="text-xs text-gray-500 shrink-0">{expanded.has(i) ? '▲' : '▼'}</span>
              </button>
              {expanded.has(i) && (
                <div className="px-3 pb-3 space-y-2 border-t border-gray-700">
                  <p className="text-xs text-gray-400 pt-2">{issue.message}</p>
                  {issue.file_path && <p className="text-xs text-gray-600 font-mono truncate">{issue.file_path}</p>}
                  <div className="rounded bg-gray-950 border border-gray-700 overflow-x-auto">
                    <pre className="text-xs text-green-300 p-3 whitespace-pre-wrap">{issue.fix_suggestion}</pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


// ── Diff 요약 탭 ─────────────────────────────────────────────
function DiffSummaryTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [commit,  setCommit]  = useState('HEAD~1')
  const [loading, setLoading] = useState(false)
  const [report,  setReport]  = useState('')

  async function run() {
    setLoading(true); setReport('')
    try {
      const res = await analysisApi.diffSummary(scriptsPath, commit || undefined)
      setReport(res.report)
    } catch (e: any) {
      setReport(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input className="input text-sm w-48" placeholder={t('diff_commit_ph')}
          value={commit} onChange={e => setCommit(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && run()} />
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('diff_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('diff_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        <MdResult text={report} loading={loading} />
      </div>
    </div>
  )
}


// ── Patterns Tab ─────────────────────────────────────────────
function PatternsTab({ scriptsPath }: { scriptsPath: string }) {
  const { t } = useApp()
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState('')
  const [maxResults, setMaxResults] = useState(30)

  async function run() {
    setLoading(true); setResult('')
    try {
      const res = await analysisNewApi.detectPatterns(scriptsPath, maxResults)
      setResult(res)
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail ?? e?.message ?? e}`)
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-full p-4 gap-3 overflow-hidden">
      <div className="flex items-center gap-3 shrink-0 flex-wrap">
        <input type="number" min={5} max={100} className="input text-sm w-24"
          placeholder={t('patterns_max_ph')} value={maxResults}
          onChange={e => setMaxResults(Number(e.target.value) || 30)} />
        <button onClick={run} disabled={loading}
          className="btn-primary text-sm px-4 py-1.5 disabled:opacity-50">
          {loading ? t('analyzing') : t('patterns_btn')}
        </button>
        <p className="text-xs text-gray-500">{t('patterns_desc')}</p>
      </div>
      <div className="flex-1 overflow-y-auto border border-gray-800 rounded bg-gray-900/50 p-4">
        <MdResult text={result} loading={loading} />
      </div>
    </div>
  )
}


// ── 메인 AnalysisView ────────────────────────────────────────
type TabId = 'coupling' | 'inheritance' | 'deadcode' | 'impact'
           | 'test_scope' | 'advise' | 'lint_fix' | 'diff_summary' | 'patterns'

export default function AnalysisView() {
  const { scriptsPath, projectInfo, t } = useApp()
  const [activeTab, setActiveTab] = useState<TabId>('coupling')

  const isUnity  = projectInfo?.kind === 'UNITY'
  const isUnreal = projectInfo?.kind === 'UNREAL'

  if (!scriptsPath) return (
    <div className="flex items-center justify-center h-full text-gray-500">
      {t('dep_no_path')}
    </div>
  )

  const tabs: [TabId, string][] = [
    ['coupling',    t('dep_coupling')],
    ['inheritance', t('dep_inheritance')],
    ['deadcode',    t('dep_deadcode')],
    ['impact',      t('dep_impact')],
    ['test_scope',  t('dep_test_scope')],
    ['advise',      t('dep_advise')],
    ['lint_fix',    t('dep_lint_fix')],
    ['diff_summary',t('dep_diff_summary')],
    ['patterns',    t('dep_patterns')],
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 탭바 — 수평 스크롤 */}
      <div className="flex border-b border-gray-800 bg-gray-950 shrink-0 items-stretch overflow-x-auto px-2"
        style={{ scrollbarWidth: 'thin', scrollbarColor: '#374151 transparent' }}>
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => setActiveTab(id)}
            className={`px-3 py-2.5 text-sm transition-colors whitespace-nowrap shrink-0
              ${activeTab === id ? 'tab-active' : 'tab-inactive'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'coupling'       && <CouplingTab    scriptsPath={scriptsPath}/>}
        {activeTab === 'inheritance'    && <InheritanceTab scriptsPath={scriptsPath} isUnreal={isUnreal}/>}
        {activeTab === 'deadcode'       && <DeadCodeTab    scriptsPath={scriptsPath} isUnity={isUnity}/>}
        {activeTab === 'impact'         && <ImpactTab      scriptsPath={scriptsPath}/>}
        {activeTab === 'test_scope'     && <TestScopeTab   scriptsPath={scriptsPath}/>}
        {activeTab === 'advise'         && <AdviseTab      scriptsPath={scriptsPath}/>}
        {activeTab === 'lint_fix'       && <LintFixTab     scriptsPath={scriptsPath}/>}
        {activeTab === 'diff_summary'   && <DiffSummaryTab scriptsPath={scriptsPath}/>}
        {activeTab === 'patterns'       && <PatternsTab    scriptsPath={scriptsPath}/>}
      </div>
    </div>
  )
}
