import type { OrgRoleSpec, Spec } from '../types'

export interface OrgStats {
  nRoles: number
  nEdges: number
  maxDepth: number
  maxSpan: number
  avgSpan: number
  shape: string
}

export function childrenOf(reporting: Record<string, string | null>, roleId: string): string[] {
  return Object.entries(reporting)
    .filter(([, parent]) => parent === roleId)
    .map(([child]) => child)
}

export function depthOf(reporting: Record<string, string | null>, roleId: string): number {
  let depth = 0
  let cur: string | null | undefined = roleId
  const guard = new Set<string>()
  while (cur && !guard.has(cur)) {
    guard.add(cur)
    cur = reporting[cur]
    depth += 1
  }
  return depth
}

export function orgStats(roles: OrgRoleSpec[], reporting: Record<string, string | null>): OrgStats {
  const ids = new Set(roles.map((r) => r.id))
  const edges = Object.entries(reporting).filter(
    ([child, parent]) => parent && ids.has(child) && ids.has(parent),
  )
  const spans: Record<string, number> = {}
  for (const edge of edges) {
    const parent = edge[1]
    if (parent) {
      spans[parent] = (spans[parent] ?? 0) + 1
    }
  }
  let maxDepth = 0
  for (const r of roles) maxDepth = Math.max(maxDepth, depthOf(reporting, r.id))
  const spanValues = Object.values(spans)
  const maxSpan = spanValues.length ? Math.max(...spanValues) : 0
  const avgSpan = spanValues.length ? spanValues.reduce((a, b) => a + b, 0) / spanValues.length : 0
  const roleChildren = (id: string) => roles.filter((r) => reporting[r.id] === id)
  const nLeaves = roles.filter((r) => roleChildren(r.id).length === 0).length
  const shape =
    nLeaves === roles.length ? 'flat' : maxDepth >= 3 ? 'deep hierarchy' : 'hierarchy'
  return {
    nRoles: roles.length,
    nEdges: edges.length,
    maxDepth,
    maxSpan,
    avgSpan,
    shape,
  }
}

export function stripOrganization(org: Spec['organization']): Spec['organization'] {
  const roles = org.roles.map((r) => {
    const out: OrgRoleSpec = {
      id: r.id,
      name: r.name,
      capabilities: [...r.capabilities],
      autonomy: r.autonomy,
    }
    if (r.responsibilities && r.responsibilities.length) out.responsibilities = [...r.responsibilities]
    if (r.mandate && r.mandate.length) out.mandate = [...r.mandate]
    return out
  })
  const reporting: Record<string, string | null> = {}
  for (const [child, parent] of Object.entries(org.reporting)) reporting[child] = parent ?? null
  const out: Spec['organization'] = { roles, reporting }
  if (org.name) out.name = org.name
  return out
}

export function jsonToYaml(value: unknown, indent = 0): string {
  const pad = ' '.repeat(indent)
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'number') {
    if (Number.isInteger(value)) return String(value)
    return String(Math.round(value * 1000000) / 1000000)
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'string') {
    if (value === '' || value.includes(' ') || /^[-0-9]/.test(value) || value.includes(':'))
      return `'${value}'`
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '[]'
    const lines = value.map((item) => {
      if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>
        const keys = Object.keys(obj)
        const out: string[] = []
        keys.forEach((k, i) => {
          const v = obj[k]
          const nested = typeof v === 'object' && v !== null && !Array.isArray(v)
          if (i === 0) {
            out.push(nested ? `${pad}  - ${k}:\n${jsonToYaml(v, indent + 6)}` : `${pad}  - ${k}: ${jsonToYaml(v, indent + 4)}`)
          } else {
            out.push(nested ? `${' '.repeat(indent + 4)}${k}:\n${jsonToYaml(v, indent + 6)}` : `${' '.repeat(indent + 4)}${k}: ${jsonToYaml(v, indent + 4)}`)
          }
        })
        return out.join('\n')
      }
      return `${pad}  - ${jsonToYaml(item, indent + 2)}`
    })
    return lines.join('\n')
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return '{}'
    const lines = entries.map(([k, v]) => {
      if (Array.isArray(v)) {
        const arr = jsonToYaml(v, indent + 2)
        return arr === '[]' ? `${pad}${k}: []` : `${pad}${k}:\n${arr}`
      }
      if (typeof v === 'object' && v !== null) {
        const inner = jsonToYaml(v, indent + 2).split('\n')
        return `${pad}${k}:\n${inner.join('\n')}`
      }
      return `${pad}${k}: ${jsonToYaml(v, indent + 2)}`
    })
    return lines.join('\n')
  }
  return String(value)
}

export function specToYaml(spec: Spec): string {
  return jsonToYaml(spec)
}

export function download(filename: string, content: string, mime = 'application/json'): void {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
