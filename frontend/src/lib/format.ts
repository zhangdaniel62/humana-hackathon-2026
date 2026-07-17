/**
 * Display formatting for dashboard figures, per the contract's
 * "Formatting and derived display values" rules.
 */

/** AHT: 2 decimals plus "min"; null → "—". */
export function formatMinutes(value: number | null): string {
  return value === null ? '—' : `${value.toFixed(2)} min`
}

/** Rates: ×100 with 1–2 decimals; null → "—". */
export function formatRate(value: number | null, decimals = 1): string {
  return value === null ? '—' : `${(value * 100).toFixed(decimals)}%`
}

/** Percentage-point delta between two decimal rates — never labeled "%". */
export function formatPp(deltaPp: number): string {
  const sign = deltaPp > 0 ? '+' : deltaPp < 0 ? '−' : '±'
  return `${sign}${Math.abs(deltaPp).toFixed(1)} pp`
}

export function formatInt(value: number): string {
  return value.toLocaleString('en-US')
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-03-09" → "Mar 9" (or "Mar 9, 2026" with year). */
export function formatDay(iso: string, withYear = false): string {
  const [y, m, d] = iso.split('-').map(Number)
  return `${MONTHS[m - 1]} ${d}${withYear ? `, ${y}` : ''}`
}

/** "2026-03-01" → "Mar 2026" — monthly bucket axis/tooltip label. */
export function formatMonth(iso: string): string {
  const [y, m] = iso.split('-').map(Number)
  return `${MONTHS[m - 1]} ${y}`
}

/** Inclusive range label, e.g. "Jan 12 – Jul 12, 2026". */
export function formatDateRange(start: string, end: string): string {
  const sameYear = start.slice(0, 4) === end.slice(0, 4)
  return `${formatDay(start, !sameYear)} – ${formatDay(end, true)}`
}
