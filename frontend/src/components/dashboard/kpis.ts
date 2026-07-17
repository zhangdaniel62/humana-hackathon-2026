import type { StatTileDelta } from '@/components/ui'
import { formatPp } from '@/lib/format'

/**
 * Baseline comparisons with the contract's directionality: lower is better
 * for AHT and repeat rate, higher is better for FCR. Baselines are synthetic
 * assumptions, and deltas for rates are percentage points, never "% change".
 */

/** AHT: relative percent vs baseline, e.g. "9.8% lower than baseline". */
export function ahtDelta(current: number | null, baseline: number | null): StatTileDelta | undefined {
  if (current === null || baseline === null || baseline === 0) return undefined
  const relative = ((baseline - current) / baseline) * 100
  if (Math.abs(relative) < 0.05) {
    return { text: 'On baseline', tone: 'neutral', direction: 'flat' }
  }
  const lower = relative > 0
  return {
    text: `${Math.abs(relative).toFixed(1)}% ${lower ? 'lower' : 'higher'} than baseline`,
    tone: lower ? 'good' : 'bad',
    direction: lower ? 'down' : 'up',
  }
}

/** FCR: percentage-point delta, higher is better. */
export function fcrDelta(current: number | null, baseline: number | null): StatTileDelta | undefined {
  if (current === null || baseline === null) return undefined
  const pp = (current - baseline) * 100
  if (Math.abs(pp) < 0.05) return { text: 'On baseline', tone: 'neutral', direction: 'flat' }
  return {
    text: `${formatPp(pp)} vs baseline`,
    tone: pp > 0 ? 'good' : 'bad',
    direction: pp > 0 ? 'up' : 'down',
  }
}

/** Repeat rate: favorable percentage-point reduction, lower is better. */
export function repeatDelta(
  current: number | null,
  baseline: number | null,
): StatTileDelta | undefined {
  if (current === null || baseline === null) return undefined
  const reductionPp = (baseline - current) * 100
  if (Math.abs(reductionPp) < 0.05) return { text: 'On baseline', tone: 'neutral', direction: 'flat' }
  const lower = reductionPp > 0
  return {
    text: `${Math.abs(reductionPp).toFixed(1)} pp ${lower ? 'below' : 'above'} baseline`,
    tone: lower ? 'good' : 'bad',
    direction: lower ? 'down' : 'up',
  }
}

/** Sparkline series for a tile: display-scaled trend values, nulls skipped. */
export function sparklineOf<T>(points: T[], accessor: (p: T) => number | null): number[] {
  return points.map(accessor).filter((v): v is number => v !== null)
}
