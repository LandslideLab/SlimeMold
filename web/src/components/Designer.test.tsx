import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Designer } from './Designer'
import { hierarchySpec } from '../defaults'
import type { Spec } from '../types'

function setup() {
  const state: { spec: Spec } = { spec: hierarchySpec() }
  const view = render(<Designer spec={state.spec} onChange={(s) => { state.spec = s }} />)
  return { state, ...view }
}

describe('Designer', () => {
  it('renders the roles of the hierarchy tree', () => {
    setup()
    expect(screen.getAllByText('lead').length).toBeGreaterThan(0)
    expect(screen.getAllByText('agent1').length).toBeGreaterThan(0)
    expect(screen.getAllByText('agent2').length).toBeGreaterThan(0)
    expect(screen.getByText(/hierarchy/)).toBeInTheDocument()
  })

  it('adds a role from the palette', async () => {
    const user = userEvent.setup()
    const { state } = setup()
    const addBtn = screen.getAllByRole('button').find((b) => b.textContent?.includes('Collaborator'))
    expect(addBtn).toBeDefined()
    await user.click(addBtn!)
    expect(state.spec.organization.roles.length).toBe(4)
    const newRole = state.spec.organization.roles[3]
    expect(state.spec.organization.reporting[newRole.id]).toBeNull()
  })

  it('reparents a role to root through its manager select', async () => {
    const user = userEvent.setup()
    const { state } = setup()
    const select = screen.getByRole('combobox', { name: 'Manager of agent1' })
    await user.selectOptions(select, '')
    expect(state.spec.organization.reporting.agent1).toBeNull()
  })

  it('does not offer a descendant as a manager (cycle prevention)', () => {
    setup()
    const leadSelect = screen.getByRole('combobox', { name: 'Manager of lead' })
    const options = Array.from(leadSelect.querySelectorAll('option')).map((o) => o.value)
    expect(options).not.toContain('agent1')
    expect(options).not.toContain('agent2')
  })

  it('removes a role and detaches its children', async () => {
    const user = userEvent.setup()
    const { state } = setup()
    await user.click(screen.getByRole('button', { name: 'Delete lead' }))
    expect(state.spec.organization.roles.find((r) => r.id === 'lead')).toBeUndefined()
    expect(state.spec.organization.reporting.agent1).toBeNull()
    expect(state.spec.organization.reporting.agent2).toBeNull()
  })

  it('renames a role and remaps reporting references', () => {
    const { state } = setup()
    const nameInput = screen.getByLabelText('Role id')
    fireEvent.change(nameInput, { target: { value: 'boss' } })
    expect(state.spec.organization.roles.find((r) => r.id === 'boss')).toBeDefined()
    expect(state.spec.organization.roles.find((r) => r.id === 'lead')).toBeUndefined()
    expect(state.spec.organization.reporting.agent1).toBe('boss')
  })

  it('edits autonomy via the inspector', async () => {
    const user = userEvent.setup()
    const { state } = setup()
    await user.click(screen.getAllByText('agent1')[0])
    await user.click(screen.getByLabelText('Operator'))
    const agent = state.spec.organization.roles.find((r) => r.id === 'agent1')
    expect(agent?.autonomy).toBe('operator')
  })
})
