import { useState } from 'react'
import type { SimResult, Spec } from '../types'
import { oddReport } from '../api'
import { download, specToYaml } from '../lib/org'

export function ExportPanel({
  spec,
  result,
}: {
  spec: Spec
  result: SimResult | null
}) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function exportBundle() {
    setBusy(true)
    setError(null)
    setMsg(null)
    try {
      const seed = result?.config.seed ?? spec.sim?.seed ?? 42
      const rep = await oddReport({ spec, seed, note: 'Reproduction bundle from the SlimeMold web testbed.' })
      download(`ODD-report-${spec.name ?? 'org'}.txt`, rep.odd, 'text/plain')
      download(`spec-${spec.name ?? 'org'}.yaml`, specToYaml(spec), 'text/yaml')
      if (result) {
        download(`result-${result.organization.name}.json`, JSON.stringify(result, null, 2))
      }
      setMsg('Exported ODD report, spec.yaml and result.json. Reproduce anywhere with `python reproduce.py`.')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const seed = result?.config.seed ?? spec.sim?.seed ?? 42

  return (
    <div>
      <div className="hero" style={{ padding: '28px 0 24px' }}>
        <div className="container">
          <div className="section-head" style={{ marginBottom: 10 }}>
            <div>
              <span className="label">Reproducibility</span>
              <div className="section-title">Export an ABM-compliant reproduction package</div>
            </div>
          </div>
          <p style={{ maxWidth: '80ch', color: '#4a4a4a', marginBottom: 14 }}>
            Every run is deterministic and fully described by (spec, seed, engine version). The
            exported package — ODD protocol description, spec.yaml, result.json — is everything a
            reviewer needs to regenerate the run byte-for-byte.
          </p>
          <div className="inline-field" style={{ gap: 12 }}>
            <button className="btn btn-red" disabled={busy} onClick={exportBundle}>
              {busy ? <span className="spinner" style={{ borderTopColor: '#fff' }} /> : '↓ Export package'}
            </button>
            <span className="label-mono">seed {seed} · engine version {result?.engine_version ?? '—'}</span>
          </div>
        </div>
      </div>

      <div className="container">
        {msg && (
          <div className="error-box" style={{ borderLeftColor: 'var(--swiss-blue)', background: 'var(--swiss-gray-50)' }}>
            {msg}
          </div>
        )}
        {error && <div className="error-box">{error}</div>}

        <div className="grid-2">
          <div className="panel">
            <div className="panel-head">
              <span className="label">CLI — the same package on disk</span>
            </div>
            <div className="panel-body">
              <p style={{ fontSize: 12, color: '#4a4a4a', marginBottom: 10 }}>
                The Python engine writes a complete bundle (ODD.txt, metadata.json, spec.yaml,
                reproduce.py):
              </p>
              <pre
                style={{
                  background: 'var(--swiss-gray-50)',
                  border: '1px solid var(--swiss-gray-200)',
                  padding: 12,
                  fontSize: 11.5,
                  fontFamily: 'monospace',
                  overflowX: 'auto',
                  margin: 0,
                }}
              >
{`pip install aislimemold

# single run
aislimemold run --spec spec.yaml --seed ${seed} --out result.json

# ODD report + reproduction bundle
aislimemold report --spec spec.yaml --out-dir bundle --seed ${seed}

# regenerate from the bundle, anywhere
cd bundle && python reproduce.py`}
              </pre>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <span className="label">Current design — spec preview</span>
            </div>
            <div className="panel-body">
              <pre
                style={{
                  background: 'var(--swiss-gray-50)',
                  border: '1px solid var(--swiss-gray-200)',
                  padding: 12,
                  fontSize: 11,
                  fontFamily: 'monospace',
                  overflowX: 'auto',
                  maxHeight: 380,
                  overflowY: 'auto',
                  margin: 0,
                }}
              >
{specToYaml(spec)}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
