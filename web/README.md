# SlimeMold Web Testbed

The interactive testbed for SlimeMold: a Swiss-style (International Typographic
Style) React application that talks to the Python engine over a headless JSON
protocol. It provides the organization designer, run-trajectory animation,
metrics dashboard, compare / scan experiments and reproduction-package export.

## Architecture

```
browser  ──/api──▶  Vite dev server  ──proxy──▶  Python engine (:8642)
  (React)           (this package)                aislimemold.server
```

In development the Vite server proxies `/api` to the engine. On Vercel the same
handlers would be deployed as serverless functions; for local research use the
dev server.

## Run

```bash
# from the repository root (starts engine + frontend together):
./start.sh

# or manually, two terminals:
cd web
npm run dev:engine     # terminal 1: engine on :8642
npm run dev            # terminal 2: Vite on :5173
```

Open http://localhost:5173 (the exposed preview port).

## Scripts

- `npm run dev` — Vite dev server (proxies `/api` → `:8642`)
- `npm run dev:engine` — run the Python engine headless server
- `npm run build` — type-check (`tsc -b`) + production build
- `npm run lint` — oxlint
- `npm run preview` — serve the production build

## Source layout

- `src/api.ts` — JSON-protocol client (`/api/simulate`, `/api/experiment`,
  `/api/report`, `/api/health`, `/api/spec/example`)
- `src/types.ts` — the protocol contract (spec + result TypeScript types)
- `src/defaults.ts` — hierarchy / flat customer-service presets
- `src/lib/org.ts` — topology stats, YAML serialization, downloads
- `src/components/Designer.tsx` — drag-to-build organization designer
- `src/components/Simulate.tsx` + `RunResults.tsx` — single-run + dashboard
- `src/components/OrgChart.tsx` + `TimelinePlayer.tsx` — task-flow animation
- `src/components/ComparePanel.tsx` / `ScanPanel.tsx` — experiment modes
- `src/components/ExportPanel.tsx` — ODD report + spec/result export
