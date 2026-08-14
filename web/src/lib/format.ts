export function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toLocaleString('en-US', {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  })
}

export function pct(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(digits)}%`
}

export function fmtSeed(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return String(n)
}

export function shortId(id: string | null | undefined, max = 14): string {
  if (!id) return '—'
  return id.length > max ? `${id.slice(0, max)}…` : id
}
