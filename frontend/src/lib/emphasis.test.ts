import { describe, expect, it } from "vitest";
import { dominates } from "./emphasis";

describe("dominates", () => {
  it("marks the figures worth the eye in a set", () => {
    const isBig = dominates([-14_793_566, 4_500, 2_268, -11_000_000]);

    expect(isBig(-14_793_566)).toBe(true);
    expect(isBig(-11_000_000)).toBe(true);
    expect(isBig(4_500)).toBe(false);
  });

  it("judges on magnitude, so a large short counts as large", () => {
    const isBig = dominates([10_000_000, -9_000_000]);

    expect(isBig(-9_000_000)).toBe(true);
  });

  it("marks nothing when there is only one figure to mark", () => {
    // EQD Delta sits entirely in one bucket. Weighting the only cell in a row
    // says nothing and would put emphasis on most rows in the grid.
    expect(dominates([37_924_168])(37_924_168)).toBe(false);
    expect(dominates([37_924_168, 0, 0])(37_924_168)).toBe(false);
  });

  it("marks nothing in an empty or all-zero set", () => {
    expect(dominates([])(0)).toBe(false);
    expect(dominates([0, 0])(0)).toBe(false);
  });

  it("keeps two comparable figures both marked", () => {
    // A hedge is two big numbers, not one big and one small; both should read
    // as heavy or the row looks one-sided.
    const isBig = dominates([-113_448, 103_301]);

    expect(isBig(-113_448)).toBe(true);
    expect(isBig(103_301)).toBe(true);
  });
});
