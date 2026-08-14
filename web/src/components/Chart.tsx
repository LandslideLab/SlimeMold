import { useMemo } from 'react'

interface LineChartProps {
  points: Array<{ x: number; label?: string; value: number }>
  height?: number
  yLabel?: string
  color?: string
  baseline?: number | null
}

export function LineChart({
  points,
  height = 200,
  yLabel = '',
  color = '#141414',
  baseline = null,
}: LineChartProps) {
  const { width, path, area, yTicks, xTicks, baselineY, xPos, yVal } = useMemo(() => {
    const W = 640
    const H = height
    const padL = 46
    const padR = 12
    const padT = 12
    const padB = 26
    const innerW = W - padL - padR
    const innerH = H - padT - padB

    if (points.length === 0) {
      return {
        width: W,
        path: '',
        area: '',
        yTicks: [] as Array<{ y: number; v: string }>,
        xTicks: [] as Array<{ x: number; label: string }>,
        baselineY: null as number | null,
        xPos: () => 0,
        yVal: () => 0,
      }
    }
    const xs = points.map((p) => p.x)
    const vals = points.map((p) => p.value)
    let yMin = Math.min(...vals, 0)
    let yMax = Math.max(...vals)
    if (yMin === yMax) {
      yMin -= 1
      yMax += 1
    }
    const span = yMax - yMin
    yMax += span * 0.08
    yMin = yMin < 0 ? yMin : 0

    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const xSpan = maxX - minX || 1

    const x = (v: number) => padL + ((v - minX) / xSpan) * innerW
    const y = (v: number) => padT + (1 - (v - yMin) / (yMax - yMin)) * innerH
    const xPos = (v: number) => x(v)
    const yVal = (v: number) => y(v)

    const d = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.x).toFixed(1)},${y(p.value).toFixed(1)}`)
      .join(' ')
    const areaD = `${d} L${x(maxX).toFixed(1)},${y(0).toFixed(1)} L${x(minX).toFixed(1)},${y(0).toFixed(1)} Z`

    const nTicks = 4
    const yTicks = Array.from({ length: nTicks + 1 }, (_, i) => {
      const v = yMin + ((yMax - yMin) * i) / nTicks
      return { y: y(v), v: v.toFixed(v >= 100 ? 0 : 1) }
    })
    const nXTicks = Math.min(points.length, 6)
    const step = Math.max(1, Math.floor(points.length / nXTicks))
    const xTicks = points
      .filter((_, i) => i % step === 0)
      .map((p) => ({ x: x(p.x), label: p.label ?? String(p.x) }))

    return {
      width: W,
      path: d,
      area: areaD,
      yTicks,
      xTicks,
      baselineY: baseline === null ? null : y(baseline),
      xPos,
      yVal,
    }
  }, [points, height, baseline])

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="org-chart-svg" role="img" aria-label={yLabel}>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={46} y1={t.y} x2={width - 12} y2={t.y} stroke="#e7e7e3" strokeWidth={1} />
          <text x={42} y={t.y + 3} textAnchor="end" fontSize={9.5} fill="#7d7d76" fontFamily="monospace">
            {t.v}
          </text>
        </g>
      ))}
      {xTicks.map((t, i) => (
        <text key={i} x={t.x} y={height - 8} textAnchor="middle" fontSize={9.5} fill="#7d7d76" fontFamily="monospace">
          {t.label}
        </text>
      ))}
      {baselineY !== null && (
        <line x1={46} y1={baselineY} x2={width - 12} y2={baselineY} stroke="#e2001a" strokeWidth={1.5} strokeDasharray="4 3" />
      )}
      <path d={area} fill="#141414" opacity={0.06} />
      <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p, i) => (
        <circle key={i} cx={xPos(p.x)} cy={yVal(p.value)} r={3} fill={color} stroke="#fff" strokeWidth={1} />
      ))}
      <text x={46} y={10} fontSize={9.5} fill="#7d7d76" fontFamily="monospace">
        {yLabel}
      </text>
    </svg>
  )
}

interface BarChartProps {
  data: Array<{ label: string; value: number }>
  height?: number
  colorA?: string
}

export function BarChart({ data, height = 220, colorA = '#141414' }: BarChartProps) {
  const W = 640
  const H = height
  const padL = 46
  const padR = 12
  const padT = 14
  const padB = 26
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const maxV = Math.max(...data.map((d) => d.value), 1e-9)
  const barW = Math.min(40, (innerW / data.length) * 0.6)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="org-chart-svg" role="img" aria-label="bar chart">
      <line x1={padL} y1={padT} x2={padL} y2={padT + innerH} stroke="#141414" strokeWidth={1} />
      <line x1={padL} y1={padT + innerH} x2={W - padR} y2={padT + innerH} stroke="#141414" strokeWidth={1} />
      {data.map((d, i) => {
        const x = padL + (i + 0.5) * (innerW / data.length) - barW / 2
        const h = (d.value / maxV) * innerH
        const y = padT + innerH - h
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={Math.max(h, 1)} fill={colorA} />
            <text x={padL + (i + 0.5) * (innerW / data.length)} y={padT + innerH + 14} textAnchor="middle" fontSize={9.5} fill="#7d7d76" fontFamily="monospace">
              {d.label}
            </text>
            <text x={padL + (i + 0.5) * (innerW / data.length)} y={y - 5} textAnchor="middle" fontSize={10} fill="#141414" fontFamily="monospace" fontWeight={600}>
              {d.value.toFixed(1)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

interface PairedBarProps {
  labels: string[]
  valuesA: number[]
  valuesB: number[]
  height?: number
}

export function PairedBarChart({ labels, valuesA, valuesB, height = 260 }: PairedBarProps) {
  const W = 640
  const H = height
  const padL = 46
  const padR = 12
  const padT = 14
  const padB = 28
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const maxV = Math.max(...valuesA, ...valuesB, 1e-9)
  const groupW = innerW / labels.length
  const barW = Math.max(6, Math.min(30, groupW * 0.32))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="org-chart-svg" role="img" aria-label="paired bar chart">
      <line x1={padL} y1={padT} x2={padL} y2={padT + innerH} stroke="#141414" strokeWidth={1} />
      <line x1={padL} y1={padT + innerH} x2={W - padR} y2={padT + innerH} stroke="#141414" strokeWidth={1} />
      {labels.map((label, i) => {
        const gx = padL + i * groupW + groupW / 2
        const hA = (valuesA[i] / maxV) * innerH
        const hB = (valuesB[i] / maxV) * innerH
        return (
          <g key={i}>
            <rect x={gx - barW - 2} y={padT + innerH - hA} width={barW} height={Math.max(hA, 1)} fill="#141414" />
            <rect x={gx + 2} y={padT + innerH - hB} width={barW} height={Math.max(hB, 1)} fill="#e2001a" />
            <text x={gx} y={padT + innerH + 15} textAnchor="middle" fontSize={9} fill="#7d7d76" fontFamily="monospace">
              {label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
