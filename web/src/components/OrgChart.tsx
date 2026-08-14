import { useMemo } from 'react'
import type { BusMessage, OrgDerived, SimResult } from '../types'
import { AUTONOMY_LABEL } from '../types'

const ROW = 92
const COL = 96
const NODE_W = 132
const NODE_H = 44
const MARGIN = 56

interface OrgChartProps {
  result: SimResult
  turn: number
  messages: BusMessage[]
}

interface NodePos {
  x: number
  y: number
  depth: number
}

export function OrgChart({ result, turn, messages }: OrgChartProps) {
  const org: OrgDerived = result.organization
  const roleList = useMemo(() => Object.values(org.roles), [org])
  const { positions, edges, width, height, orgPos } = useMemo(() => {
    const ids = roleList.map((r) => r.id)
    const reporting = org.reporting
    const childrenOf = (id: string) => ids.filter((r) => reporting[r] === id)
    const roots = ids.filter((r) => !reporting[r])

    const positions = new Map<string, NodePos>()
    let cursor = 0
    const assign = (id: string, depth: number) => {
      const children = childrenOf(id)
      const y = 30 + depth * ROW
      if (children.length === 0) {
        positions.set(id, { x: 60 + cursor * COL, y, depth })
        cursor += 1
      } else {
        const xs: number[] = []
        for (const c of children) {
          assign(c, depth + 1)
          xs.push(positions.get(c)!.x)
        }
        positions.set(id, { x: xs.reduce((a, b) => a + b, 0) / xs.length, y, depth })
      }
    }
    for (const r of roots) assign(r, 0)

    const rootXs = roots.map((r) => positions.get(r)?.x ?? 60)
    const orgX = rootXs.length ? rootXs.reduce((a, b) => a + b, 0) / rootXs.length : 60
    const orgPos = { x: orgX, y: 12 }

    const maxX = Math.max(orgPos.x, ...Array.from(positions.values()).map((p) => p.x), 60)
    const maxDepth = Math.max(0, ...Array.from(positions.values()).map((p) => p.depth))
    const width = maxX + MARGIN + 40
    const height = 40 + (maxDepth + 1) * ROW + 40

    const edges: Array<{ id: string; x1: number; y1: number; x2: number; y2: number }> = []
    for (const child of ids) {
      const parent = reporting[child]
      const c = positions.get(child)
      const p = parent ? positions.get(parent) : orgPos
      if (c && p) {
        edges.push({ id: child, x1: p.x, y1: p.y + NODE_H / 2, x2: c.x, y2: c.y - NODE_H / 2 })
      }
    }

    return { positions, edges, width, height, orgPos }
  }, [org, roleList])

  const current = Math.floor(turn)
  const phase = Math.min(1, Math.max(0, turn - current))
  const active = messages.filter((m) => m.turn === current)

  const posOf = (id: string) => {
    if (id === 'org') return orgPos
    return positions.get(id) ?? orgPos
  }

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="org-chart-svg"
      role="img"
      aria-label="Organization chart with task flow animation"
    >
      <text x={orgPos.x} y={orgPos.y + 3} textAnchor="middle" fontSize={8.5} fill="#7d7d76" fontFamily="monospace" letterSpacing={1}>
        ENVIRONMENT
      </text>
      {edges.map((e) => {
        const isActive = active.some(
          (m) =>
            (m.sender === e.id && m.receiver === (org.reporting[e.id] ?? 'org')) ||
            (m.receiver === e.id && m.sender === (org.reporting[e.id] ?? 'org')),
        )
        return (
          <line
            key={e.id}
            x1={e.x1}
            y1={e.y1}
            x2={e.x2}
            y2={e.y2}
            className={isActive ? 'edge-line edge-line-active' : 'edge-line'}
          />
        )
      })}

      {roleList.map((r) => {
        const p = positions.get(r.id)
        if (!p) return null
        const involved = active.some((m) => m.sender === r.id || m.receiver === r.id)
        return (
          <g key={r.id} className="org-node-svg" transform={`translate(${p.x - NODE_W / 2}, ${p.y - NODE_H / 2})`}>
            {involved && <rect x={-3} y={-3} width={NODE_W + 6} height={NODE_H + 6} fill="none" stroke="#e2001a" strokeWidth={1.5} />}
            <rect width={NODE_W} height={NODE_H} fill={involved ? '#fdecee' : '#ffffff'} stroke="#141414" strokeWidth={1.2} />
            <text x={8} y={15} fontSize={11} fontWeight={700} fontFamily="monospace" fill="#141414">
              {r.id}
            </text>
            <text x={NODE_W - 8} y={15} textAnchor="end" fontSize={8} fontFamily="monospace" fill="#7d7d76">
              {AUTONOMY_LABEL[r.autonomy].slice(0, 4).toUpperCase()}
            </text>
            <text x={8} y={30} fontSize={9.5} fill="#4a4a4a" fontFamily="'Helvetica Neue', Helvetica, sans-serif">
              {r.name.length > 20 ? `${r.name.slice(0, 19)}…` : r.name}
            </text>
            <text x={8} y={40.5} fontSize={7.5} fill="#7d7d76" fontFamily="monospace">
              {r.capabilities.length ? r.capabilities.join('·') : '—'}
            </text>
          </g>
        )
      })}

      {active.map((m) => {
        const s = posOf(m.sender)
        const t = posOf(m.receiver)
        if (!s || !t) return null
        const dx = (t.x - s.x) * phase
        const dy = (t.y - s.y) * phase
        const px = s.x + dx
        const py = s.y + dy
        return (
          <g key={m.id}>
            <circle cx={px} cy={py} r={5} className="flow-dot" />
            <text
              x={px + 8}
              y={py - 6}
              fontSize={8}
              fontFamily="monospace"
              fill="#e2001a"
              fontWeight={600}
            >
              {m.kind.toUpperCase()}
              {m.task_id ? ` ${m.task_id}` : ''}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
