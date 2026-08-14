import { describe, expect, it } from 'vitest'
import { hierarchySpec, flatSpec, emptySpec } from './defaults'

describe('preset specs', () => {
  it('hierarchy has 3 roles across 2 levels with supervision budget', () => {
    const s = hierarchySpec()
    expect(s.organization.roles).toHaveLength(3)
    expect(s.organization.reporting.agent1).toBe('lead')
    expect(s.institution?.supervision_budget?.lead).toBe(3)
    expect(s.institution?.delegation_strategy).toBe('controlled')
  })

  it('hierarchy supports unlimited budget (null)', () => {
    expect(hierarchySpec(null).institution?.supervision_budget?.lead).toBeNull()
  })

  it('flat has 3 self-managed approvers', () => {
    const s = flatSpec()
    expect(s.organization.roles).toHaveLength(3)
    expect(s.organization.roles.every((r) => r.autonomy === 'approver')).toBe(true)
    expect(Object.values(s.organization.reporting).every((p) => p === null)).toBe(true)
    expect(s.institution?.delegation_strategy).toBe('full')
    expect(s.institution?.approval_gates).toHaveLength(0)
  })

  it('emptySpec starts with one collaborator root', () => {
    const s = emptySpec()
    expect(s.organization.roles).toHaveLength(1)
    expect(s.organization.roles[0].autonomy).toBe('collaborator')
    expect(s.organization.reporting.r1).toBeNull()
  })
})
