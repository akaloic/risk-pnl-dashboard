/**
 * Axis scale for the P&L chart.
 *
 * Ticks land on round numbers. Taking the raw minimum and maximum as bounds
 * produces an axis reading $906,542, which looks like a stray data point
 * rather than a boundary.
 *
 * One axis carries both series. That is worth stating because it is a
 * judgement, not an oversight: on this extract the daily moves span 1.29m and
 * the running total 1.35m, within 5% of each other, so a shared axis costs
 * nothing and lets a bar and the line be compared directly against the same
 * zero. If a longer history pushed the cumulative range well beyond the daily
 * one, the bars would flatten into the baseline and this would need splitting
 * onto a second axis.
 */

export interface Scale {
  min: number;
  max: number;
  ticks: number[];
}

/** Round a step up to 1, 2 or 5 times a power of ten. */
function niceStep(range: number, targetTicks: number): number {
  if (range <= 0) return 1;
  const raw = range / targetTicks;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const normalised = raw / magnitude;
  const rounded = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10;
  return rounded * magnitude;
}

/** Bounds and tick values covering `values`, always including zero. */
export function niceScale(values: number[], targetTicks = 4): Scale {
  const rawMax = Math.max(...values, 0);
  const rawMin = Math.min(...values, 0);
  const step = niceStep(rawMax - rawMin || Math.abs(rawMax) || 1, targetTicks);

  const min = Math.floor(rawMin / step) * step;
  const max = Math.ceil(rawMax / step) * step;

  const ticks: number[] = [];
  for (let value = min; value <= max + step / 2; value += step) {
    // Snap away the float drift that repeated addition introduces.
    ticks.push(Math.abs(value) < step / 2 ? 0 : Number(value.toPrecision(12)));
  }

  return { min, max: max === min ? min + step : max, ticks };
}
