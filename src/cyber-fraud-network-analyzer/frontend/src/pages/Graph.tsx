/**
 * pages/Graph.tsx
 * Interactive fraud-network graph powered by Cytoscape.js.
 *
 * Features:
 *  - Case selector, entity-type filter, relationship-type filter
 *  - Confidence slider
 *  - Node search
 *  - Click to select → node detail panel (connections, evidence, risk score)
 *  - Neighbor expansion (1–3 hops)
 *  - Shortest / transaction path finder
 *  - Zoom / fit / reset controls
 *  - Connected-components list
 *  - Color-coded legend by entity type
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import cytoscape, { type Core, type NodeSingular } from 'cytoscape'
import PageHeader from '../components/PageHeader'
import {
  fetchGraph,
  fetchNeighbors,
  fetchPath,
  fetchNodeDetail,
  fetchSearch,
  fetchComponents,
  type CytoscapeNode,
  type NodeDetail,
  type Component,
} from '../api/graph'

// ── Constants ─────────────────────────────────────────────────────────────────

const ENTITY_TYPES = [
  'PERSON', 'PHONE', 'SIM', 'DEVICE', 'BANK_ACCOUNT',
  'UPI_ID', 'IP_ADDRESS', 'EMAIL', 'LOCATION',
  'ORGANISATION', 'TRANSACTION', 'VICTIM', 'FIR', 'EVIDENCE', 'OTHER',
]

const REL_TYPES = [
  'OWNS', 'USES', 'CALLED', 'TRANSFERRED_TO', 'PAID_TO', 'REGISTERED_AT',
  'LOCATED_AT', 'ASSOCIATED_WITH', 'SHARED_DEVICE', 'SHARED_SIM', 'FILED',
  'RECEIVED_FROM', 'LINKED_TO', 'CONTROLLED_BY',
]

const NODE_COLORS: Record<string, string> = {
  PERSON:       '#3b82f6',
  PHONE:        '#8b5cf6',
  SIM:          '#06b6d4',
  DEVICE:       '#f59e0b',
  BANK_ACCOUNT: '#10b981',
  UPI_ID:       '#14b8a6',
  IP_ADDRESS:   '#ef4444',
  EMAIL:        '#f97316',
  LOCATION:     '#84cc16',
  ORGANISATION: '#6366f1',
  TRANSACTION:  '#ec4899',
  VICTIM:       '#f43f5e',
  FIR:          '#a78bfa',
  EVIDENCE:     '#94a3b8',
  OTHER:        '#64748b',
}

const DEFAULT_CASE = 'sample'

// ── Cytoscape stylesheet ───────────────────────────────────────────────────────

const STYLESHEET: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      'label': 'data(label)',
      'color': '#1f2937',
      'font-size': '10px',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 4,
      'width': 32,
      'height': 32,
      'border-width': 2,
      'border-color': '#ffffff',
      'text-max-width': '80px',
      'text-wrap': 'ellipsis',
    } as cytoscape.Css.Node,
  },
  {
    selector: 'node[risk_score > 0.7]',
    style: { 'border-color': '#ef4444', 'border-width': 3 } as cytoscape.Css.Node,
  },
  {
    selector: 'node:selected',
    style: {
      'border-color': '#1d4ed8',
      'border-width': 4,
      'background-color': 'data(color)',
    } as cytoscape.Css.Node,
  },
  {
    selector: 'node.highlighted',
    style: { 'border-color': '#fbbf24', 'border-width': 3 } as cytoscape.Css.Node,
  },
  {
    selector: 'node.dimmed',
    style: { opacity: 0.25 } as cytoscape.Css.Node,
  },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#d1d5db',
      'target-arrow-color': '#d1d5db',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(relationship)',
      'font-size': '8px',
      'color': '#6b7280',
      'text-rotation': 'autorotate',
      'text-background-color': '#ffffff',
      'text-background-opacity': 0.8,
      'text-background-padding': '2px',
    } as cytoscape.Css.Edge,
  },
  {
    selector: 'edge.highlighted',
    style: {
      'line-color': '#fbbf24',
      'target-arrow-color': '#fbbf24',
      'width': 3,
    } as cytoscape.Css.Edge,
  },
  {
    selector: 'edge.dimmed',
    style: { opacity: 0.1 } as cytoscape.Css.Edge,
  },
]

// ── Helpers ────────────────────────────────────────────────────────────────────

function riskColor(score: number) {
  if (score >= 0.7) return 'text-red-600'
  if (score >= 0.4) return 'text-amber-500'
  return 'text-green-600'
}

function riskLabel(score: number) {
  if (score >= 0.7) return 'High'
  if (score >= 0.4) return 'Medium'
  return 'Low'
}

function addColorToNodes(nodes: CytoscapeNode[]) {
  return nodes.map((n) => ({
    ...n,
    data: { ...n.data, color: NODE_COLORS[n.data.type] ?? NODE_COLORS.OTHER },
  }))
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  // ── State ──────────────────────────────────────────────────────────────────
  const [caseId, setCaseId] = useState(DEFAULT_CASE)
  const [caseInput, setCaseInput] = useState(DEFAULT_CASE)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [entityTypeFilter, setEntityTypeFilter] = useState<string[]>([])
  const [relTypeFilter, setRelTypeFilter] = useState<string[]>([])
  const [minConfidence, setMinConfidence] = useState(0)

  const [searchQ, setSearchQ] = useState('')
  const [searchLoading, setSearchLoading] = useState(false)

  const [selectedNode, setSelectedNode] = useState<NodeDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [pathSource, setPathSource] = useState('')
  const [pathTarget, setPathTarget] = useState('')
  const [pathMode, setPathMode] = useState<'shortest' | 'transaction'>('shortest')
  const [pathLoading, setPathLoading] = useState(false)
  const [pathMessage, setPathMessage] = useState<string | null>(null)

  const [components, setComponents] = useState<Component[]>([])
  const [showComponents, setShowComponents] = useState(false)

  const [statsNodes, setStatsNodes] = useState(0)
  const [statsEdges, setStatsEdges] = useState(0)

  const [activeTab, setActiveTab] = useState<'detail' | 'path' | 'components'>('detail')

  // ── Init Cytoscape ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: STYLESHEET,
      layout: { name: 'cose' },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      autounselectify: false,
    })

    cy.on('tap', 'node', (evt) => {
      const node: NodeSingular = evt.target
      loadNodeDetail(node.id())
      // dim all, highlight neighbourhood
      cy.elements().addClass('dimmed')
      const hood = node.closedNeighborhood()
      hood.removeClass('dimmed')
      hood.addClass('highlighted')
    })

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass('dimmed').removeClass('highlighted')
        setSelectedNode(null)
      }
    })

    cyRef.current = cy
    return () => { cy.destroy() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Load graph ─────────────────────────────────────────────────────────────
  const loadGraph = useCallback(async (id: string) => {
    if (!cyRef.current) return
    setLoading(true)
    setError(null)
    setSelectedNode(null)
    setPathMessage(null)

    try {
      const params: Record<string, string | number> = {}
      if (entityTypeFilter.length) params.entity_types = entityTypeFilter.join(',')
      if (relTypeFilter.length) params.rel_types = relTypeFilter.join(',')
      if (minConfidence > 0) params.min_confidence = minConfidence / 100

      const data = await fetchGraph(id, params)
      const cy = cyRef.current

      cy.elements().remove()
      cy.add([
        ...addColorToNodes(data.nodes),
        ...data.edges,
      ])

      setStatsNodes(data.stats.node_count)
      setStatsEdges(data.stats.edge_count)

      if (data.nodes.length) {
        cy.layout({ name: 'cose', animate: false, randomize: false, fit: true, padding: 40 } as cytoscape.LayoutOptions).run()
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [entityTypeFilter, relTypeFilter, minConfidence])

  // Auto-load when case changes
  useEffect(() => { loadGraph(caseId) }, [caseId, loadGraph])

  // ── Load node detail ───────────────────────────────────────────────────────
  const loadNodeDetail = useCallback(async (entityId: string) => {
    setDetailLoading(true)
    setActiveTab('detail')
    try {
      const detail = await fetchNodeDetail(caseId, entityId)
      setSelectedNode(detail)
    } catch {
      setSelectedNode(null)
    } finally {
      setDetailLoading(false)
    }
  }, [caseId])

  // ── Search ─────────────────────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    if (!searchQ.trim() || !cyRef.current) return
    setSearchLoading(true)
    try {
      const result = await fetchSearch(caseId, searchQ.trim())
      const cy = cyRef.current
      const matchIds = new Set(result.nodes.map((n) => n.data.id))
      if (matchIds.size === 0) return
      cy.elements().addClass('dimmed').removeClass('highlighted')
      matchIds.forEach((id) => {
        const node = cy.$id(id)
        node.removeClass('dimmed').addClass('highlighted')
      })
      // fit to matched nodes
      const matched = cy.nodes().filter((n) => matchIds.has(n.id()))
      if (matched.length) cy.fit(matched, 80)
    } catch {
      // silent
    } finally {
      setSearchLoading(false)
    }
  }, [caseId, searchQ])

  // ── Expand neighbors ───────────────────────────────────────────────────────
  const expandNeighbors = useCallback(async (entityId: string, depth: number) => {
    if (!cyRef.current) return
    try {
      const data = await fetchNeighbors(caseId, entityId, depth, 'both')
      const cy = cyRef.current
      const existing = new Set(cy.elements().map((el) => el.id()))

      const newNodes = addColorToNodes(data.nodes.filter((n) => !existing.has(n.data.id)))
      const newEdges = data.edges.filter((e) => !existing.has(e.data.id))

      if (newNodes.length || newEdges.length) {
        cy.add([...newNodes, ...newEdges])
        cy.layout({ name: 'cose', animate: false, fit: false, padding: 40 } as cytoscape.LayoutOptions).run()
        setStatsNodes(cy.nodes().length)
        setStatsEdges(cy.edges().length)
      }
    } catch {
      // silent
    }
  }, [caseId])

  // ── Path finding ───────────────────────────────────────────────────────────
  const handleFindPath = useCallback(async () => {
    if (!pathSource.trim() || !pathTarget.trim() || !cyRef.current) return
    setPathLoading(true)
    setPathMessage(null)
    try {
      const result = await fetchPath(caseId, pathSource.trim(), pathTarget.trim(), pathMode)
      const cy = cyRef.current
      cy.elements().removeClass('highlighted').removeClass('dimmed')

      if (!result.found) {
        setPathMessage(result.message ?? 'No path found.')
        return
      }

      // Highlight path nodes/edges (support both single and multi-path responses)
      const pathNodes = result.nodes ?? result.paths?.[0]?.nodes ?? []
      const pathEdges = result.edges ?? result.paths?.[0]?.edges ?? []

      // Add any missing path elements
      const existing = new Set(cy.elements().map((el) => el.id()))
      const newNodes = addColorToNodes(pathNodes.filter((n) => !existing.has(n.data.id)))
      const newEdges = pathEdges.filter((e) => !existing.has(e.data.id))
      if (newNodes.length || newEdges.length) cy.add([...newNodes, ...newEdges])

      cy.elements().addClass('dimmed')
      const pathNodeIds = new Set(pathNodes.map((n) => n.data.id))
      const pathEdgeIds = new Set(pathEdges.map((e) => e.data.id))
      cy.nodes().filter((n) => pathNodeIds.has(n.id())).removeClass('dimmed').addClass('highlighted')
      cy.edges().filter((e) => pathEdgeIds.has(e.id())).removeClass('dimmed').addClass('highlighted')

      const hops = result.path?.length ?? pathNodes.length
      setPathMessage(`Path found: ${hops} node(s)`)

      const pathEls = cy.elements().filter((el) => pathNodeIds.has(el.id()) || pathEdgeIds.has(el.id()))
      if (pathEls.length) cy.fit(pathEls, 80)
    } catch (e) {
      setPathMessage((e as Error).message)
    } finally {
      setPathLoading(false)
    }
  }, [caseId, pathSource, pathTarget, pathMode])

  // ── Connected components ───────────────────────────────────────────────────
  const handleComponents = useCallback(async () => {
    try {
      const result = await fetchComponents(caseId)
      setComponents(result.components)
      setShowComponents(true)
      setActiveTab('components')
    } catch {
      // silent
    }
  }, [caseId])

  const highlightComponent = useCallback((comp: Component) => {
    if (!cyRef.current) return
    const cy = cyRef.current
    const ids = new Set(comp.nodes)
    cy.elements().addClass('dimmed').removeClass('highlighted')
    cy.nodes().filter((n) => ids.has(n.id())).removeClass('dimmed').addClass('highlighted')
    const matched = cy.nodes().filter((n) => ids.has(n.id()))
    if (matched.length) cy.fit(matched, 60)
  }, [])

  // ── Zoom controls ──────────────────────────────────────────────────────────
  const zoomIn  = () => cyRef.current?.zoom(cyRef.current.zoom() * 1.3)
  const zoomOut = () => cyRef.current?.zoom(cyRef.current.zoom() / 1.3)
  const fitAll  = () => cyRef.current?.fit(undefined, 40)
  const resetView = () => {
    cyRef.current?.elements().removeClass('dimmed').removeClass('highlighted')
    cyRef.current?.fit(undefined, 40)
  }

  // ── Apply case input ───────────────────────────────────────────────────────
  const applyCase = () => {
    const id = caseInput.trim()
    if (id) setCaseId(id)
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Network Graph"
        subtitle="Visualise fraud network relationships — click a node to explore"
        actions={
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Case:</span>
            <input
              className="text-sm border border-gray-300 rounded px-2 py-1 w-36 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={caseInput}
              onChange={(e) => setCaseInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyCase()}
              placeholder="Case ID"
            />
            <button className="btn-primary text-sm px-3 py-1" onClick={applyCase}>Load</button>
          </div>
        }
      />

      {/* ── Main layout: sidebar | canvas | right panel ── */}
      <div className="flex flex-1 min-h-0">

        {/* ── Left sidebar: filters ─── */}
        <aside className="w-56 shrink-0 border-r border-gray-200 bg-white flex flex-col overflow-y-auto">
          <div className="p-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Entity Types</p>
            <div className="flex flex-wrap gap-1">
              {ENTITY_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() =>
                    setEntityTypeFilter((prev) =>
                      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
                    )
                  }
                  style={{
                    backgroundColor: entityTypeFilter.includes(t) ? NODE_COLORS[t] : undefined,
                    color: entityTypeFilter.includes(t) ? '#fff' : undefined,
                    borderColor: NODE_COLORS[t],
                  }}
                  className="text-[10px] px-1.5 py-0.5 rounded border transition-colors"
                  title={t}
                >
                  {t.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          <div className="p-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Relationship Types</p>
            <div className="flex flex-col gap-1">
              {REL_TYPES.map((r) => (
                <label key={r} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-3 h-3 accent-brand-600"
                    checked={relTypeFilter.includes(r)}
                    onChange={(e) =>
                      setRelTypeFilter((prev) =>
                        e.target.checked ? [...prev, r] : prev.filter((x) => x !== r)
                      )
                    }
                  />
                  <span className="text-xs text-gray-700">{r.replace('_', ' ')}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="p-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Min Confidence: {minConfidence}%
            </p>
            <input
              type="range" min={0} max={100} step={5}
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="w-full accent-brand-600"
            />
          </div>

          <div className="p-3">
            <button
              className="btn-primary text-xs w-full py-1.5"
              onClick={() => loadGraph(caseId)}
              disabled={loading}
            >
              {loading ? 'Loading…' : 'Apply Filters'}
            </button>
            {(entityTypeFilter.length > 0 || relTypeFilter.length > 0 || minConfidence > 0) && (
              <button
                className="btn-secondary text-xs w-full py-1 mt-1"
                onClick={() => {
                  setEntityTypeFilter([])
                  setRelTypeFilter([])
                  setMinConfidence(0)
                }}
              >
                Clear Filters
              </button>
            )}
          </div>

          {/* Legend */}
          <div className="p-3 border-t border-gray-100 mt-auto">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Legend</p>
            <div className="flex flex-col gap-1">
              {Object.entries(NODE_COLORS).slice(0, 10).map(([type, color]) => (
                <div key={type} className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
                  <span className="text-[10px] text-gray-600">{type.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* ── Canvas area ─── */}
        <div className="flex-1 flex flex-col min-w-0 relative">

          {/* Toolbar */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
            {/* Search */}
            <input
              className="text-sm border border-gray-300 rounded px-2 py-1 w-48 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="Search nodes…"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button
              className="btn-secondary text-xs px-2 py-1"
              onClick={handleSearch}
              disabled={searchLoading}
            >
              {searchLoading ? '…' : 'Search'}
            </button>
            <button className="btn-secondary text-xs px-2 py-1" onClick={resetView} title="Clear highlights">
              Clear
            </button>

            <div className="h-4 w-px bg-gray-300 mx-1" />

            {/* Zoom */}
            <button className="btn-secondary text-xs px-2 py-1" onClick={zoomIn}  title="Zoom in">+</button>
            <button className="btn-secondary text-xs px-2 py-1" onClick={zoomOut} title="Zoom out">−</button>
            <button className="btn-secondary text-xs px-2 py-1" onClick={fitAll}  title="Fit all">Fit</button>

            <div className="h-4 w-px bg-gray-300 mx-1" />

            <button className="btn-secondary text-xs px-2 py-1" onClick={handleComponents}>
              Components
            </button>

            {/* Stats */}
            <div className="ml-auto flex items-center gap-3 text-xs text-gray-500">
              <span>{statsNodes} nodes</span>
              <span>{statsEdges} edges</span>
              <span className="font-medium text-gray-700">Case: {caseId}</span>
            </div>
          </div>

          {/* Graph canvas */}
          <div className="flex-1 relative">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
                <div className="text-gray-600 text-sm">Loading graph…</div>
              </div>
            )}
            {error && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 badge-danger px-4 py-2 rounded-lg text-sm shadow">
                {error}
              </div>
            )}
            {!loading && statsNodes === 0 && !error && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 pointer-events-none">
                <p className="text-4xl mb-3">&#x2610;</p>
                <p className="text-sm font-medium">No graph data for case <strong>{caseId}</strong></p>
                <p className="text-xs mt-1">Run AI extraction first, or try case ID "sample"</p>
              </div>
            )}
            <div ref={containerRef} className="w-full h-full" />
          </div>
        </div>

        {/* ── Right panel: detail / path / components ─── */}
        <aside className="w-72 shrink-0 border-l border-gray-200 bg-white flex flex-col overflow-hidden">

          {/* Tab bar */}
          <div className="flex border-b border-gray-200">
            {(['detail', 'path', 'components'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-2 text-xs font-medium capitalize transition-colors
                  ${activeTab === tab
                    ? 'border-b-2 border-brand-600 text-brand-700'
                    : 'text-gray-500 hover:text-gray-700'}`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">

            {/* ── Detail tab ── */}
            {activeTab === 'detail' && (
              <div className="p-3">
                {detailLoading && <p className="text-xs text-gray-400">Loading…</p>}
                {!detailLoading && !selectedNode && (
                  <div className="text-center py-8">
                    <p className="text-3xl mb-2">&#8635;</p>
                    <p className="text-xs text-gray-400">Click a node in the graph to inspect it</p>
                  </div>
                )}
                {!detailLoading && selectedNode && (
                  <NodeDetailPanel
                    node={selectedNode}
                    onExpand={(depth) => expandNeighbors(selectedNode.entity_id, depth)}
                    onSetPathSource={() => setPathSource(selectedNode.entity_id)}
                    onSetPathTarget={() => setPathTarget(selectedNode.entity_id)}
                  />
                )}
              </div>
            )}

            {/* ── Path tab ── */}
            {activeTab === 'path' && (
              <div className="p-3 flex flex-col gap-3">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Find Path</p>
                <div>
                  <label className="text-xs text-gray-600 block mb-1">Source entity ID</label>
                  <input
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={pathSource}
                    onChange={(e) => setPathSource(e.target.value)}
                    placeholder="e.g. ent_001"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-600 block mb-1">Target entity ID</label>
                  <input
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={pathTarget}
                    onChange={(e) => setPathTarget(e.target.value)}
                    placeholder="e.g. ent_005"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-600 block mb-1">Mode</label>
                  <select
                    className="w-full text-xs border border-gray-300 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    value={pathMode}
                    onChange={(e) => setPathMode(e.target.value as 'shortest' | 'transaction')}
                  >
                    <option value="shortest">Shortest path</option>
                    <option value="transaction">Transaction path</option>
                  </select>
                </div>
                <button
                  className="btn-primary text-xs py-1.5 w-full"
                  onClick={handleFindPath}
                  disabled={pathLoading || !pathSource.trim() || !pathTarget.trim()}
                >
                  {pathLoading ? 'Searching…' : 'Find Path'}
                </button>
                {pathMessage && (
                  <p className={`text-xs rounded px-2 py-1.5 ${
                    pathMessage.startsWith('Path found')
                      ? 'bg-green-50 text-green-700'
                      : 'bg-amber-50 text-amber-700'
                  }`}>
                    {pathMessage}
                  </p>
                )}
                <p className="text-[10px] text-gray-400">
                  Tip: select a node and use "Set as Source / Target" buttons in the Detail tab to pre-fill these fields.
                </p>
              </div>
            )}

            {/* ── Components tab ── */}
            {activeTab === 'components' && (
              <div className="p-3">
                {!showComponents ? (
                  <div className="text-center py-8">
                    <p className="text-xs text-gray-400">Click "Components" in the toolbar to analyse connected sub-networks</p>
                  </div>
                ) : (
                  <>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      {components.length} Component{components.length !== 1 ? 's' : ''}
                    </p>
                    <div className="flex flex-col gap-2">
                      {components.map((comp) => (
                        <button
                          key={comp.id}
                          className="text-left text-xs border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50 transition-colors"
                          onClick={() => highlightComponent(comp)}
                        >
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="font-medium text-gray-700">Component {comp.id + 1}</span>
                            <span className="badge-info badge text-[10px]">{comp.size} nodes</span>
                          </div>
                          <div className="text-gray-500">
                            Dominant: <span className="font-medium">{comp.dominant_type}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

// ── NodeDetailPanel sub-component ─────────────────────────────────────────────

interface NodeDetailPanelProps {
  node: NodeDetail
  onExpand: (depth: number) => void
  onSetPathSource: () => void
  onSetPathTarget: () => void
}

function NodeDetailPanel({ node, onExpand, onSetPathSource, onSetPathTarget }: NodeDetailPanelProps) {
  const color = NODE_COLORS[node.type] ?? NODE_COLORS.OTHER

  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start gap-2">
        <span
          className="mt-0.5 w-4 h-4 rounded-full shrink-0"
          style={{ backgroundColor: color }}
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 break-all leading-tight">{node.label}</p>
          <p className="text-[10px] text-gray-400 mt-0.5">{node.entity_id}</p>
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-1">
        <span className="badge badge-info text-[10px]">{node.type}</span>
        <span className={`badge text-[10px] ${
          node.risk_score >= 0.7 ? 'badge-danger' : node.risk_score >= 0.4 ? 'badge-warn' : 'badge-success'
        }`}>
          Risk: {riskLabel(node.risk_score)}
        </span>
        <span className="badge badge-info text-[10px]">
          Conf: {(node.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Risk score bar */}
      <div>
        <div className="flex justify-between text-[10px] text-gray-500 mb-1">
          <span>Risk Score</span>
          <span className={`font-semibold ${riskColor(node.risk_score)}`}>
            {(node.risk_score * 100).toFixed(0)}%
          </span>
        </div>
        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${node.risk_score * 100}%`,
              backgroundColor: node.risk_score >= 0.7 ? '#ef4444' : node.risk_score >= 0.4 ? '#f59e0b' : '#10b981',
            }}
          />
        </div>
      </div>

      {/* Degree */}
      <div className="flex gap-3 text-xs text-gray-600">
        <span>In: <strong>{node.in_degree}</strong></span>
        <span>Out: <strong>{node.out_degree}</strong></span>
        <span>Total: <strong>{node.in_degree + node.out_degree}</strong></span>
      </div>

      {/* Expand buttons */}
      <div>
        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Expand Neighbors</p>
        <div className="flex gap-1">
          {[1, 2, 3].map((d) => (
            <button
              key={d}
              className="btn-secondary text-[10px] px-2 py-0.5"
              onClick={() => onExpand(d)}
            >
              {d}-hop
            </button>
          ))}
        </div>
      </div>

      {/* Path actions */}
      <div>
        <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Path Finding</p>
        <div className="flex gap-1">
          <button
            className="btn-secondary text-[10px] px-2 py-0.5"
            onClick={() => { onSetPathSource(); }}
          >
            Set as Source
          </button>
          <button
            className="btn-secondary text-[10px] px-2 py-0.5"
            onClick={() => { onSetPathTarget(); }}
          >
            Set as Target
          </button>
        </div>
      </div>

      {/* Connections */}
      {node.neighbors.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
            Connections ({node.neighbors.length})
          </p>
          <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
            {node.neighbors.map((nb, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[10px] text-gray-600">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: NODE_COLORS[nb.type] ?? NODE_COLORS.OTHER }}
                />
                <span className="truncate flex-1" title={nb.label}>{nb.label}</span>
                <span className="text-gray-400 shrink-0">{nb.relationship.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Attributes */}
      {Object.keys(node.attributes).length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">Attributes</p>
          <div className="flex flex-col gap-0.5">
            {Object.entries(node.attributes).slice(0, 8).map(([k, v]) => (
              <div key={k} className="flex text-[10px]">
                <span className="text-gray-400 w-24 shrink-0 truncate">{k}:</span>
                <span className="text-gray-700 truncate" title={String(v)}>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evidence */}
      {Array.isArray(node.evidence) && node.evidence.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-1">
            Evidence ({node.evidence.length})
          </p>
          <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
            {node.evidence.slice(0, 5).map((ev: unknown, i) => {
              const e = ev as Record<string, string>
              return (
                <div key={i} className="text-[10px] border border-gray-100 rounded px-2 py-1">
                  <span className="font-medium text-gray-700">{e.evidence_id}</span>
                  {e.type && <span className="ml-1 text-gray-400">{e.type}</span>}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
