# SlimeMold — User Acceptance Test Log

This document records the full test campaign executed against the SlimeMold
deliverable (Python engine + TypeScript/React web testbed). Every test below was
executed live in this session; the results establish that the system was in a
working state at delivery time.

Environment: Python 3.11.2 · Node v22.22.0 · npm 10.9.4 · Linux

---

## 1. Engine unit & integration suite (Python)

Command:

```bash
ruff check src tests
PYTHONPATH=src python3 -m pytest --cov=slime_mold --cov-report=term
```

| Check | Result | Detail |
|---|---|---|
| Ruff lint (src + tests) | PASS | `All checks passed!` |
| Pytest | **189 passed** | `189 passed in 3.60s` |
| Coverage | **93.18%** | threshold `--cov-fail-under=90` satisfied |
| Server endpoints | PASS | health, simulate, experiment (compare/scan), report, spec/example, OPTIONS CORS |

Suites exercised: autonomy, demo, DSL/experiments, institution, knowledge,
metrics/stats, organization (topology + span/depth), simulation protocol,
tasks, turnover/agents/RNG, plus targeted extra-coverage tests (server, stats,
experiments, CLI).

---

## 2. Web testbed — static checks

Command (in `web/`):

```bash
npm run build     # tsc -b && vite build
npm run lint      # oxlint
npm test          # vitest run
```

| Check | Result | Detail |
|---|---|---|
| TypeScript type-check (`tsc -b`) | PASS | no errors |
| Production build (`vite build`) | PASS | `index-CAAEEeZs.js 258.78 kB / 75.65 kB gzip`, CSS `13.45 kB` |
| oxlint | PASS | 0 errors |
| Vitest | **50 passed** (10 files) | see §3 |

---

## 3. Web testbed — automated unit/component tests (50)

Test files (all green):

| File | Cases | Coverage of |
|---|---|---|
| `src/lib/org.test.ts` | 6 | org stats (depth/span/shape), cycle handling, YAML serializer, blob download |
| `src/defaults.test.ts` | 4 | hierarchy/flat/custom presets |
| `src/api.test.ts` | 9 | JSON-protocol client, error handling, request bodies |
| `src/components/Designer.test.tsx` | 7 | drag-tree editor: add/remove/rename/reparent roles, cycle prevention, autonomy edit |
| `src/components/Dashboard.test.tsx` | 3 | six-construct metrics dashboard |
| `src/components/OrgChart.test.tsx` | 4 | SVG chart nodes/edges/environment + flow-dot animation |
| `src/components/RunResults.test.tsx` | 4 | run summary, animation player, ODD export, event log toggle |
| `src/components/ComparePanel.test.tsx` | 3 | A/B comparison flow, statistics, engine-error display |
| `src/components/ScanPanel.test.tsx` | 3 | parameter sweep flow, sensitivity table, engine-error display |
| `src/App.test.tsx` | 4 | masthead/tabs, designer default view, tab navigation |

---

## 4. End-to-end protocol tests (live, through the Vite proxy)

Both services were started (`./start.sh` equivalent): Python engine on
`127.0.0.1:8642` and Vite dev server on `:5173` proxying `/api` → engine.
Every request below hit the **running** system.

| # | Endpoint | Result | Evidence |
|---|---|---|---|
| 1 | `GET /api/health` | PASS | `{"status":"ok","engine_version":"0.1.0"}` |
| 2 | `GET /api/spec/example` | PASS | 3-role hierarchy spec returned |
| 3 | `POST /api/simulate` (spec+seed+turns) | PASS | HTTP 200, 221 kB result, 100 tasks, 463 messages, 657 events |
| 4 | `POST /api/experiment` compare | PASS | A vs B means, Cohen's d, Mann–Whitney p, significance flag |
| 5 | `POST /api/experiment` scan | PASS | arrival-rate sweep curve (0.5→17.5, 1.0→67.5, 1.4→58.3, 2.0→118.3) |
| 6 | `POST /api/report` | PASS | 3 155-char ODD protocol description returned |
| 7 | Vite proxy | PASS | all `/api/*` requests forwarded; `:5173` serves app HTML |

---

## 5. Research use-case reproduction (demo grid)

The canonical demo — "customer-service: 3 roles, 2-level hierarchy vs flat, at
supervision budgets 0% / 50% / 100%" — was executed through the live API:

| Design | Budget | Throughput | Success | Flow | Msg/task | Error | Uncaught risk |
|---|---|---|---|---|---|---|---|
| hierarchy | 0% | 54.2 | 0.348 | 18.2 | 2.60 | 0.606 | 0.959 |
| hierarchy | 50% | 101.7 | 0.652 | 2.2 | 4.13 | 0.341 | 0.388 |
| hierarchy | 100% | 103.3 | 0.663 | 2.2 | 4.14 | 0.330 | 0.367 |
| flat | — | 90.0 | 0.578 | 2.2 | 1.60 | 0.416 | 0.469 |

The pattern matches agency-theory predictions: supervision raises output and
cuts error/uncaught risk at the price of coordination messages (2.60 → 4.14
msg/task), and pure delegation (0% budget) collapses quality — while flat
self-managed agents land in between. This is the story the Compare/Scan panels
let researchers explore interactively.

---

## 6. Determinism & reproducibility

| Check | Result | Evidence |
|---|---|---|
| Same seed → identical run | PASS | hierarchy 50% run twice: throughput, seed, message count all identical |
| CLI run ↔ bundle reproduce | PASS | `reproduce.py` output byte-identical to original: performance, tasks, timeline, messages all `True` |
| Scan/compare derived seeds | PASS | per-point/per-rep seeds deterministic and reported |

Reproduction bundle contents verified: `ODD.txt`, `metadata.json`, `spec.yaml`,
`reproduce.py`.

---

## 7. Production build serving

| Check | Result |
|---|---|
| `vite preview` on :4173 | PASS — `<title>SlimeMold — Organization Design Simulation Testbed</title>`, index 200, JS asset 200 |

---

## Summary

| Suite | Count | Passed | Failed |
|---|---|---|---|
| Python engine tests | 189 | 189 | 0 |
| Python coverage | 93.18% (≥90%) | — | — |
| Web unit/component tests | 50 | 50 | 0 |
| Web build (`tsc` + `vite`) | — | PASS | — |
| Web lint (oxlint) | — | PASS | — |
| Live API E2E (6 endpoints × proxy) | 7 | 7 | 0 |
| Demo grid runs | 4 | 4 | 0 |
| Reproducibility (determinism) | 3 | 3 | 0 |

**Verdict: system delivered in a working state.** All automated suites and all
live end-to-end checks pass at delivery time.
