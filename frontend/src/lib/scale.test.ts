/**
 * The axis has one job beyond covering the data: its boundaries have to look
 * like boundaries. An axis topping out at $906,542 reads as a stray print, and
 * that is what these pin down.
 */

import { describe, expect, it } from "vitest";
import { niceScale } from "./scale";

/** 1, 2 or 5 times a power of ten -- what a person would have chosen. */
function isRound(value: number): boolean {
  if (value === 0) return true;
  const magnitude = 10 ** Math.floor(Math.log10(Math.abs(value)));
  return [1, 2, 5, 10].includes(Math.round(Math.abs(value) / magnitude));
}

describe("niceScale", () => {
  it("puts every tick on a round number", () => {
    const { ticks } = niceScale([-906_542, 431_007, 1_284_913]);

    expect(ticks.every(isRound)).toBe(true);
  });

  it("covers the data it was given", () => {
    const values = [-906_542, 431_007, 1_284_913];
    const { min, max } = niceScale(values);

    expect(min).toBeLessThanOrEqual(Math.min(...values));
    expect(max).toBeGreaterThanOrEqual(Math.max(...values));
  });

  it("includes zero even when the data never crosses it", () => {
    // Bars are read against the baseline, so an axis floating above zero would
    // show a book down 400k as though it were the worst possible outcome.
    const gains = niceScale([220_000, 480_000, 310_000]);
    const losses = niceScale([-220_000, -480_000, -310_000]);

    expect(gains.ticks).toContain(0);
    expect(gains.min).toBe(0);
    expect(losses.ticks).toContain(0);
    expect(losses.max).toBe(0);
  });

  it("returns ticks in ascending order, evenly spaced", () => {
    const { ticks } = niceScale([-1_100_000, 900_000]);
    const gaps = ticks.slice(1).map((tick, index) => tick - ticks[index]);

    expect(gaps.every((gap) => gap > 0)).toBe(true);
    expect(new Set(gaps.map((gap) => gap.toFixed(6))).size).toBe(1);
  });

  it("lands exactly on zero rather than near it", () => {
    // Ticks are produced by repeated addition, which drifts. A gridline at
    // 1.4e-11 instead of 0 would be drawn a hair off the baseline and labelled
    // "$0" anyway, so the zero line and the bars' origin would disagree.
    const { ticks } = niceScale([-333_333, 666_667]);

    expect(ticks.filter((tick) => tick === 0)).toHaveLength(1);
    expect(ticks.some((tick) => tick !== 0 && Math.abs(tick) < 1)).toBe(false);
  });

  it("survives a flat series without collapsing the axis", () => {
    // A book with a single day, or one that has not moved, would otherwise
    // give max === min and a division by zero in the y projection.
    const flat = niceScale([0, 0, 0]);
    const single = niceScale([50_000]);

    expect(flat.max).toBeGreaterThan(flat.min);
    expect(single.max).toBeGreaterThan(single.min);
    expect(single.ticks).toContain(0);
  });

  it("scales down to a quiet book as readily as a loud one", () => {
    // Filtering the chart to one book drops the range by an order of
    // magnitude; the ticks have to follow rather than stay at desk scale.
    const { ticks } = niceScale([-164_123, 43_000]);

    expect(ticks.every(isRound)).toBe(true);
    expect(Math.max(...ticks)).toBeLessThan(1_000_000);
  });
});
