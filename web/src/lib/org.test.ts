import { describe, expect, it, vi, afterEach } from 'vitest'
import { orgStats, jsonToYaml, specToYaml, download, depthOf } from './org'
import type { Spec } from '../types'

describe('orgStats', () => {
  it('reports flat organization shape', () => {
    const roles = [
      { id: 'a', name: 'A', capabilities: ['t1'], autonomy: 'approver' as const },
      { id: 'b', name: 'B', capabilities: ['t1'], autonomy: 'approver' as const },
      { id: 'c', name: 'C', capabilities: ['t1'], autonomy: 'approver' as const },
    ]
    const reporting = { a: null, b: null, c: null }
    expect(orgStats(roles, reporting)).toEqual({
      nRoles: 3,
      nEdges: 0,
      maxDepth: 1,
      maxSpan: 0,
      avgSpan: 0,
      shape: 'flat',
    })
  })

  it('computes depth and span for a hierarchy', () => {
    const roles = [
      { id: 'lead', name: 'Lead', capabilities: ['review'], autonomy: 'approver' as const },
      { id: 'm1', name: 'M1', capabilities: ['t1'], autonomy: 'collaborator' as const },
      { id: 'm2', name: 'M2', capabilities: ['t1'], autonomy: 'collaborator' as const },
      { id: 'a1', name: 'A1', capabilities: ['t1'], autonomy: 'operator' as const },
      { id: 'a2', name: 'A2', capabilities: ['t1'], autonomy: 'operator' as const },
      { id: 'a3', name: 'A3', capabilities: ['t1'], autonomy: 'operator' as const },
    ]
    const reporting = { m1: 'lead', m2: 'lead', a1: 'm1', a2: 'm1', a3: 'm2' }
    const s = orgStats(roles, reporting)
    expect(s.nRoles).toBe(6)
    expect(s.nEdges).toBe(5)
    expect(s.maxDepth).toBe(3)
    expect(s.maxSpan).toBe(2)
    expect(s.avgSpan).toBeCloseTo(5 / 3, 6)
    expect(s.shape).toBe('deep hierarchy')
  })

  it('ignores edges referencing unknown or null parents', () => {
    const roles = [
      { id: 'a', name: 'A', capabilities: [], autonomy: 'observer' as const },
    ]
    const reporting = { a: 'ghost', b: 'a' }
    const s = orgStats(roles, reporting)
    expect(s.nEdges).toBe(0)
    expect(s.shape).toBe('flat')
  })
})

describe('depthOf', () => {
  it('walks the reporting chain', () => {
    const reporting = { a1: 'm1', m1: 'lead', lead: null }
    expect(depthOf(reporting, 'a1')).toBe(3)
    expect(depthOf(reporting, 'lead')).toBe(1)
    expect(depthOf(reporting, 'm1')).toBe(2)
  })
})

describe('jsonToYaml', () => {
  it('renders scalars', () => {
    expect(jsonToYaml('hello')).toBe('hello')
    expect(jsonToYaml('has space')).toBe("'has space'")
    expect(jsonToYaml(42)).toBe('42')
    expect(jsonToYaml(4.2)).toBe('4.2')
    expect(jsonToYaml(true)).toBe('true')
    expect(jsonToYaml(null)).toBe('null')
  })

  it('renders nested objects and arrays', () => {
    const yaml = jsonToYaml({ org: { roles: [{ id: 'a' }, { id: 'b' }], empty: [] } })
    expect(yaml).toContain('org:')
    expect(yaml).toContain('roles:')
    expect(yaml).toContain('- id: a')
    expect(yaml).toContain('empty: []')
  })
})

describe('specToYaml', () => {
  it('serializes a full spec deterministically', () => {
    const spec: Spec = {
      name: 'test-org',
      sim: { turns: 100, seed: 7 },
      organization: {
        roles: [{ id: 'r1', name: 'Role 1', capabilities: ['t1'], autonomy: 'collaborator' }],
        reporting: { r1: null },
      },
      taskflow: { arrival_rate: 1.2, task_types: ['t1', 't2'] },
    }
    const y = specToYaml(spec)
    expect(y).toContain('name: test-org')
    expect(y).toContain('turns: 100')
    expect(y).toContain('autonomy: collaborator')
    expect(specToYaml(spec)).toBe(y)
  })
})

describe('download', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('creates a blob and triggers a click', () => {
    const create = vi.fn(() => 'blob:mock')
    const revoke = vi.fn()
    const click = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    const realCreateElement = document.createElement.bind(document)
    document.createElement = vi.fn((tag: string) => {
      const el = realCreateElement(tag)
      el.click = click
      return el
    }) as unknown as typeof document.createElement

    download('x.json', '{"a":1}', 'application/json')
    expect(click).toHaveBeenCalled()
    expect(revoke).toHaveBeenCalled()
  })
})
