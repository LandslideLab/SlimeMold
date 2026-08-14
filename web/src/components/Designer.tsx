import { useState } from 'react'
import type { Autonomy, OrgRoleSpec, Spec } from '../types'
import { AUTONOMIES, AUTONOMY_LABEL } from '../types'
import { orgStats } from '../lib/org'
import { fmt } from '../lib/format'

interface DesignerProps {
  spec: Spec
  onChange: (spec: Spec) => void
}

const PALETTE: Array<{ name: string; caps: string[]; autonomy: Autonomy }> = [
  { name: 'Operator', caps: ['t1'], autonomy: 'operator' },
  { name: 'Collaborator', caps: ['t1', 't2'], autonomy: 'collaborator' },
  { name: 'Consultant', caps: ['t1', 't2', 't3'], autonomy: 'consultant' },
  { name: 'Approver', caps: ['review'], autonomy: 'approver' },
  { name: 'Observer', caps: [], autonomy: 'observer' },
]

function nextRoleId(org: Spec['organization']): string {
  let n = 1
  const ids = new Set(org.roles.map((r) => r.id))
  while (ids.has(`r${n}`)) n += 1
  return `r${n}`
}

function wouldCycle(reporting: Record<string, string | null>, child: string, parent: string): boolean {
  if (child === parent) return true
  let cur: string | null | undefined = parent
  const guard = new Set<string>()
  while (cur) {
    if (cur === child) return true
    if (guard.has(cur)) break
    guard.add(cur)
    cur = reporting[cur]
  }
  return false
}

export function Designer({ spec, onChange }: DesignerProps) {
  const org = spec.organization
  const stats = orgStats(org.roles, org.reporting)
  const [selectedId, setSelectedId] = useState<string | null>(org.roles[0]?.id ?? null)
  const [dragId, setDragId] = useState<string | null>(null)
  const [dropTarget, setDropTarget] = useState<string | null>(null)
  const [tab, setTab] = useState<'role' | 'institution' | 'taskflow' | 'knowledge' | 'turnover' | 'sim'>('role')

  const selected = org.roles.find((r) => r.id === selectedId) ?? null

  function updateRole(id: string, patch: Partial<OrgRoleSpec>) {
    onChange({
      ...spec,
      organization: {
        ...org,
        roles: org.roles.map((r) => (r.id === id ? { ...r, ...patch } : r)),
      },
    })
  }

  function addRole(tmpl: (typeof PALETTE)[number]) {
    const id = nextRoleId(org)
    onChange({
      ...spec,
      organization: {
        ...org,
        roles: [...org.roles, { id, name: `${tmpl.name} ${id.toUpperCase()}`, capabilities: [...tmpl.caps], autonomy: tmpl.autonomy }],
        reporting: { ...org.reporting, [id]: null },
      },
    })
    setSelectedId(id)
  }

  function renameRole(oldId: string, newId: string) {
    if (!newId || oldId === newId) return
    const reporting: Record<string, string | null> = {}
    for (const [child, parent] of Object.entries(org.reporting)) {
      reporting[child === oldId ? newId : child] = parent === oldId ? newId : parent
    }
    const roles = org.roles.map((r) => (r.id === oldId ? { ...r, id: newId } : r))
    onChange({ ...spec, organization: { ...org, roles, reporting } })
    if (selectedId === oldId) setSelectedId(newId)
  }

  function removeRole(id: string) {
    const reporting: Record<string, string | null> = {}
    for (const [child, parent] of Object.entries(org.reporting)) {
      if (child === id) continue
      reporting[child] = parent === id ? null : parent
    }
    onChange({
      ...spec,
      organization: {
        ...org,
        roles: org.roles.filter((r) => r.id !== id),
        reporting,
      },
    })
    if (selectedId === id) setSelectedId(org.roles.find((r) => r.id !== id)?.id ?? null)
  }

  function setParent(child: string, parent: string | null) {
    if (parent && wouldCycle(org.reporting, child, parent)) return
    onChange({
      ...spec,
      organization: {
        ...org,
        reporting: { ...org.reporting, [child]: parent },
      },
    })
  }

  function onDrop(target: string | null) {
    if (dragId && target !== dragId && !wouldCycle(org.reporting, dragId, target ?? '')) {
      setParent(dragId, target)
    }
    setDragId(null)
    setDropTarget(null)
  }

  const roots = org.roles.filter((r) => !org.reporting[r.id])

  function renderNode(id: string, depth: number) {
    const role = org.roles.find((r) => r.id === id)
    if (!role) return null
    const children = org.roles
      .filter((r) => org.reporting[r.id] === id)
      .map((r) => r.id)
    return (
      <li key={id}>
        <div
          className={`org-node${dragId === id ? ' drag-source' : ''}${dropTarget === id ? ' drag-over' : ''}`}
          draggable
          onDragStart={(e) => {
            setDragId(id)
            e.dataTransfer.effectAllowed = 'move'
          }}
          onDragEnd={() => {
            setDragId(null)
            setDropTarget(null)
          }}
          onDragOver={(e) => {
            e.preventDefault()
            if (dragId && dragId !== id) setDropTarget(id)
          }}
          onDrop={(e) => {
            e.preventDefault()
            onDrop(id)
          }}
          onClick={(e) => {
            e.stopPropagation()
            setSelectedId(id)
            setTab('role')
          }}
        >
          <span className="org-node-role">{role.id}</span>
          <span className="org-node-name">{role.name}</span>
          <span className="org-node-badges">
            <span className="chip chip-soft">{AUTONOMY_LABEL[role.autonomy]}</span>
            <span className="chip chip-soft">{role.capabilities.length ? role.capabilities.join('+') : '—'}</span>
          </span>
          <select
            value={org.reporting[id] ?? ''}
            onChange={(e) => setParent(id, e.target.value || null)}
            onClick={(e) => e.stopPropagation()}
            style={{ width: 'auto', padding: '3px 6px', fontSize: '11px' }}
            aria-label={`Manager of ${role.id}`}
          >
            <option value="">(root)</option>
            {org.roles
              .filter((r) => r.id !== id && !wouldCycle(org.reporting, id, r.id))
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id} — {r.name}
                </option>
              ))}
          </select>
          <button
            className="btn btn-ghost btn-sm"
            onClick={(e) => {
              e.stopPropagation()
              removeRole(id)
            }}
            aria-label={`Delete ${role.id}`}
          >
            ×
          </button>
        </div>
        {children.length > 0 && <ul>{children.map((c) => renderNode(c, depth + 1))}</ul>}
      </li>
    )
  }

  return (
    <div className="designer-layout">
      {/* structure column */}
      <div style={{ paddingRight: 28 }}>
        <div className="section-head">
          <div>
            <span className="label">Reporting topology</span>
            <div className="section-title">Structure</div>
          </div>
          <div className="legend">
            <span>
              depth {stats.maxDepth} · span {stats.maxSpan} · avg {fmt(stats.avgSpan, 1)} · shape{' '}
              {stats.shape}
            </span>
          </div>
        </div>

        <div
          className="statusbar"
          style={{ cursor: 'pointer', marginBottom: 8 }}
          onDragOver={(e) => {
            e.preventDefault()
            setDropTarget('__root__')
          }}
          onDrop={(e) => {
            e.preventDefault()
            onDrop(null)
          }}
        >
          <span className="status-dot" data-state="ok" />
          Drag a role here to make it a root
        </div>

        <ul className="org-tree">
          {roots.map((r) => renderNode(r.id, 0))}
          {org.roles.length === 0 && <li className="empty">No roles. Add one from the palette.</li>}
        </ul>

        <div className="palette" style={{ marginTop: 16 }}>
          <div className="panel-head">
            <span className="label">Role palette</span>
            <span className="label-mono">click to add</span>
          </div>
          <div className="palette-list">
            {PALETTE.map((p) => (
              <button key={p.name} className="palette-item" onClick={() => addRole(p)}>
                <span className="pi-name">{p.name}</span>
                <span className="pi-sub">
                  {AUTONOMY_LABEL[p.autonomy]} · {p.caps.length ? p.caps.join('+') : 'no caps'}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* inspector column */}
      <div>
        <div className="section-head">
          <div>
            <span className="label">Configuration</span>
            <div className="section-title">Inspector</div>
          </div>
        </div>

        <div className="tabbar" style={{ borderBottom: '1px solid var(--swiss-gray-200)', marginLeft: 0, marginBottom: 14 }}>
          {(
            [
              ['role', 'Role'],
              ['institution', 'Institution'],
              ['taskflow', 'Task flow'],
              ['knowledge', 'Knowledge'],
              ['turnover', 'Turnover'],
              ['sim', 'Sim'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              className="tab"
              data-active={tab === id}
              onClick={() => setTab(id)}
              style={{ padding: '8px 14px', borderLeft: 'none', borderTop: 'none', borderBottom: tab === id ? '3px solid var(--swiss-red)' : '3px solid transparent' }}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'role' && (
          <RoleInspector role={selected} allRoles={org.roles} onChange={updateRole} onRename={renameRole} />
        )}
        {tab === 'institution' && <InstitutionInspector spec={spec} onChange={onChange} />}
        {tab === 'taskflow' && <TaskflowInspector spec={spec} onChange={onChange} />}
        {tab === 'knowledge' && <KnowledgeInspector spec={spec} onChange={onChange} />}
        {tab === 'turnover' && <TurnoverInspector spec={spec} onChange={onChange} />}
        {tab === 'sim' && <SimInspector spec={spec} onChange={onChange} />}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------- role inspector */

function RoleInspector({
  role,
  allRoles,
  onChange,
  onRename,
}: {
  role: OrgRoleSpec | null
  allRoles: OrgRoleSpec[]
  onChange: (id: string, patch: Partial<OrgRoleSpec>) => void
  onRename: (oldId: string, newId: string) => void
}) {
  if (!role) {
    return <div className="empty">Select a role to edit its capabilities, autonomy and mandate.</div>
  }
  const selected = role
  const allCaps = Array.from(new Set(allRoles.flatMap((r) => r.capabilities)))
  const candidateCaps = allCaps.length ? allCaps : ['t1', 't2', 't3', 'review']

  function toggleCap(cap: string) {
    const has = selected.capabilities.includes(cap)
    onChange(selected.id, {
      capabilities: has ? selected.capabilities.filter((c) => c !== cap) : [...selected.capabilities, cap],
    })
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label-mono">{selected.id}</span>
        <span className="chip">{AUTONOMY_LABEL[selected.autonomy]}</span>
      </div>
      <div className="panel-body">
        <div className="field">
          <label htmlFor="role-name">Role name</label>
          <input
            id="role-name"
            type="text"
            value={selected.name}
            onChange={(e) => onChange(selected.id, { name: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="role-id">Role id</label>
          <input
            id="role-id"
            type="text"
            value={selected.id}
            onChange={(e) => {
              const newId = e.target.value.replace(/[^a-zA-Z0-9_-]/g, '')
              if (!newId || newId === selected.id) return
              onRename(selected.id, newId)
            }}
          />
          <span className="hint">Renames the role and re-maps its reporting references.</span>
        </div>
        <div className="field">
          <label>Autonomy baseline</label>
          <div className="checkbox-list">
            {AUTONOMIES.map((a) => (
              <label key={a} className="checkbox-item">
                <input
                  type="radio"
                  name="autonomy"
                  checked={selected.autonomy === a}
                  onChange={() => onChange(selected.id, { autonomy: a })}
                />
                {AUTONOMY_LABEL[a]}
              </label>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Capabilities</label>
          <div className="checkbox-list">
            {candidateCaps.map((c) => (
              <label key={c} className="checkbox-item">
                <input type="checkbox" checked={selected.capabilities.includes(c)} onChange={() => toggleCap(c)} />
                {c}
              </label>
            ))}
            <label className="checkbox-item" style={{ alignItems: 'center', gap: 4 }}>
              <AddCapInput onAdd={(c) => onChange(selected.id, { capabilities: [...selected.capabilities, c] })} />
            </label>
          </div>
        </div>
        <div className="field">
          <label htmlFor="role-resp">Responsibilities (comma-separated)</label>
          <input
            id="role-resp"
            type="text"
            value={(selected.responsibilities ?? []).join(', ')}
            onChange={(e) =>
              onChange(selected.id, {
                responsibilities: e.target.value
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>
      </div>
    </div>
  )
}

function AddCapInput({ onAdd }: { onAdd: (cap: string) => void }) {
  const [v, setV] = useState('')
  return (
    <>
      <input
        type="text"
        value={v}
        placeholder="+cap"
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && v.trim()) {
            onAdd(v.trim())
            setV('')
          }
        }}
        style={{ width: 90, padding: '3px 6px', fontSize: '11px' }}
      />
    </>
  )
}

/* --------------------------------------------------- institutional inspector */

function InstitutionInspector({ spec, onChange }: { spec: Spec; onChange: (s: Spec) => void }) {
  const inst = spec.institution ?? {}
  const set = (patch: Partial<Spec['institution']>) =>
    onChange({ ...spec, institution: { ...inst, ...patch } })

  const budgets = inst.supervision_budget ?? {}
  const roles = spec.organization.roles

  function setBudget(roleId: string, value: string) {
    const parsed = value === '' || value.toLowerCase() === 'none' ? null : Number(value)
    const next: Record<string, number | null> = { ...budgets }
    if (parsed === null) next[roleId] = null
    else next[roleId] = parsed
    set({ supervision_budget: next })
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label">Institution — delegation &amp; supervision</span>
      </div>
      <div className="panel-body">
        <div className="field">
          <label htmlFor="delegation">Delegation strategy</label>
          <select
            id="delegation"
            value={inst.delegation_strategy ?? 'controlled'}
            onChange={(e) => set({ delegation_strategy: e.target.value })}
          >
            <option value="full">full</option>
            <option value="controlled">controlled</option>
            <option value="restricted">restricted</option>
          </select>
          <span className="hint">
            full: agents act independently · controlled: managers approve · restricted: managers execute
          </span>
        </div>

        <div className="field">
          <label>Supervision budget (approvals / turn)</label>
          {roles.map((r) => (
            <div key={r.id} className="inline-field" style={{ marginBottom: 6 }}>
              <label style={{ minWidth: 100 }}>{r.id}</label>
              <input
                type="text"
                value={budgets[r.id] === undefined || budgets[r.id] === null ? 'none' : String(budgets[r.id])}
                onChange={(e) => setBudget(r.id, e.target.value)}
                style={{ width: 90 }}
              />
              <span className="hint">“none” = unlimited</span>
            </div>
          ))}
        </div>

        <div className="field">
          <label>Approval gates</label>
          {inst.approval_gates?.map((g, i) => (
            <div key={i} className="inline-field" style={{ marginBottom: 6 }}>
              <select
                value={g.kind}
                onChange={(e) => {
                  const gates = [...(inst.approval_gates ?? [])]
                  gates[i] = { ...g, kind: e.target.value }
                  set({ approval_gates: gates })
                }}
                style={{ width: 120 }}
              >
                <option value="risk">risk</option>
                <option value="cost">cost</option>
                <option value="novel">novel</option>
                <option value="anomaly">anomaly</option>
              </select>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={g.threshold}
                onChange={(e) => {
                  const gates = [...(inst.approval_gates ?? [])]
                  gates[i] = { ...g, threshold: Number(e.target.value) }
                  set({ approval_gates: gates })
                }}
                style={{ width: 90 }}
              />
              <button className="btn btn-ghost btn-sm" onClick={() => set({ approval_gates: (inst.approval_gates ?? []).filter((_, j) => j !== i) })}>
                ×
              </button>
            </div>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={() => set({ approval_gates: [...(inst.approval_gates ?? []), { kind: 'risk', threshold: 0.7 }] })}>
            + gate
          </button>
        </div>

        <div className="grid-2">
          <div className="field">
            <label htmlFor="esc">Escalation timeout (turns)</label>
            <input id="esc" type="number" min={1} value={inst.escalation_timeout ?? 5} onChange={(e) => set({ escalation_timeout: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="maxwait">Max wait turns (deadlock)</label>
            <input id="maxwait" type="number" min={1} value={inst.max_wait_turns ?? 12} onChange={(e) => set({ max_wait_turns: Number(e.target.value) })} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="riskacc">Risk acceptance (0–1)</label>
          <input id="riskacc" type="number" min={0} max={1} step={0.05} value={inst.risk_acceptance ?? 0} onChange={(e) => set({ risk_acceptance: Number(e.target.value) })} />
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------ taskflow inspector */

function TaskflowInspector({ spec, onChange }: { spec: Spec; onChange: (s: Spec) => void }) {
  const tf = spec.taskflow ?? {}
  const set = (patch: Partial<Spec['taskflow']>) =>
    onChange({ ...spec, taskflow: { ...tf, ...patch } })
  const types = tf.task_types ?? ['t1']
  const [newType, setNewType] = useState('')

  function addType() {
    if (newType.trim() && !types.includes(newType.trim())) {
      set({ task_types: [...types, newType.trim()] })
      setNewType('')
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label">Task flow — environment</span>
      </div>
      <div className="panel-body">
        <div className="field">
          <label>Task types</label>
          <div className="checkbox-list">
            {types.map((t) => (
              <span key={t} className="chip">
                {t}
                <button
                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0, fontFamily: 'monospace' }}
                  onClick={() => set({ task_types: types.filter((x) => x !== t) })}
                  aria-label={`Remove ${t}`}
                >
                  ×
                </button>
              </span>
            ))}
            <span className="inline-field">
              <input type="text" value={newType} onChange={(e) => setNewType(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addType()} placeholder="+type" style={{ width: 90, padding: '3px 6px', fontSize: '11px' }} />
            </span>
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="arrival">Arrival rate (tasks / turn)</label>
            <input id="arrival" type="number" min={0} step={0.1} value={tf.arrival_rate ?? 1} onChange={(e) => set({ arrival_rate: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="dyn">Dynamism</label>
            <input id="dyn" type="number" min={0} max={1} step={0.01} value={tf.dynamism ?? 0} onChange={(e) => set({ dynamism: Number(e.target.value) })} />
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="cmplx">Complexity μ</label>
            <input id="cmplx" type="number" min={0} max={1} step={0.05} value={tf.complexity_mu ?? 0.4} onChange={(e) => set({ complexity_mu: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="riskmu">Risk μ</label>
            <input id="riskmu" type="number" min={0} max={1} step={0.05} value={tf.risk_mu ?? 0.3} onChange={(e) => set({ risk_mu: Number(e.target.value) })} />
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="anom">Anomaly probability</label>
            <input id="anom" type="number" min={0} max={1} step={0.01} value={tf.anomaly_probability ?? 0.02} onChange={(e) => set({ anomaly_probability: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="nov">Novelty probability</label>
            <input id="nov" type="number" min={0} max={1} step={0.01} value={tf.novelty_probability ?? 0.05} onChange={(e) => set({ novelty_probability: Number(e.target.value) })} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------ knowledge inspector */

function KnowledgeInspector({ spec, onChange }: { spec: Spec; onChange: (s: Spec) => void }) {
  const kn = spec.knowledge ?? {}
  const set = (patch: Partial<Spec['knowledge']>) => onChange({ ...spec, knowledge: { ...kn, ...patch } })
  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label">Knowledge mechanism — organizational learning</span>
      </div>
      <div className="panel-body">
        <div className="grid-2">
          <div className="field">
            <label htmlFor="share">Sharing probability</label>
            <input id="share" type="number" min={0} max={1} step={0.05} value={kn.sharing_probability ?? 0.7} onChange={(e) => set({ sharing_probability: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="half">Knowledge half-life (turns)</label>
            <input id="half" type="number" min={1} value={kn.half_life ?? 40} onChange={(e) => set({ half_life: Number(e.target.value) })} />
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="reval">Revalidation probability</label>
            <input id="reval" type="number" min={0} max={1} step={0.02} value={kn.revalidation_probability ?? 0.1} onChange={(e) => set({ revalidation_probability: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="noise">Knowledge noise</label>
            <input id="noise" type="number" min={0} max={1} step={0.02} value={kn.noise ?? 0.1} onChange={(e) => set({ noise: Number(e.target.value) })} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------ turnover inspector */

function TurnoverInspector({ spec, onChange }: { spec: Spec; onChange: (s: Spec) => void }) {
  const tn = spec.turnover ?? {}
  const set = (patch: Partial<Spec['turnover']>) => onChange({ ...spec, turnover: { ...tn, ...patch } })
  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label">Turnover — membership mobility</span>
      </div>
      <div className="panel-body">
        <div className="grid-2">
          <div className="field">
            <label htmlFor="turnp">Per-turn departure probability</label>
            <input id="turnp" type="number" min={0} max={0.2} step={0.001} value={tn.per_turn_probability ?? 0} onChange={(e) => set({ per_turn_probability: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="onboard">Onboarding turns</label>
            <input id="onboard" type="number" min={0} value={tn.onboarding_turns ?? 10} onChange={(e) => set({ onboarding_turns: Number(e.target.value) })} />
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="rexp">Replacement experience</label>
            <input id="rexp" type="number" min={0} max={1} step={0.05} value={tn.replace_experience ?? 0.2} onChange={(e) => set({ replace_experience: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="kloss">Knowledge loss fraction</label>
            <input id="kloss" type="number" min={0} max={1} step={0.05} value={tn.knowledge_loss_fraction ?? 0.8} onChange={(e) => set({ knowledge_loss_fraction: Number(e.target.value) })} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------- sim inspector */

function SimInspector({ spec, onChange }: { spec: Spec; onChange: (s: Spec) => void }) {
  const sim = spec.sim ?? {}
  const set = (patch: Partial<Spec['sim']>) => onChange({ ...spec, sim: { ...sim, ...patch } })
  return (
    <div className="panel">
      <div className="panel-head">
        <span className="label">Simulation — determinism controls</span>
      </div>
      <div className="panel-body">
        <div className="grid-2">
          <div className="field">
            <label htmlFor="turns">Turns</label>
            <input id="turns" type="number" min={1} value={sim.turns ?? 120} onChange={(e) => set({ turns: Math.max(1, Number(e.target.value)) })} />
          </div>
          <div className="field">
            <label htmlFor="seed">Random seed</label>
            <input id="seed" type="number" value={sim.seed ?? 42} onChange={(e) => set({ seed: Number(e.target.value) })} />
          </div>
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="attempts">Max attempts / task</label>
            <input id="attempts" type="number" min={1} value={sim.max_attempts ?? 2} onChange={(e) => set({ max_attempts: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="kw">Knowledge weight</label>
            <input id="kw" type="number" min={0} max={1} step={0.05} value={sim.knowledge_weight ?? 0.4} onChange={(e) => set({ knowledge_weight: Number(e.target.value) })} />
          </div>
        </div>
        <label className="checkbox-item" style={{ marginTop: 4 }}>
          <input type="checkbox" checked={sim.supervision_enabled !== false} onChange={(e) => set({ supervision_enabled: e.target.checked })} />
          Supervision enabled
        </label>
      </div>
    </div>
  )
}
