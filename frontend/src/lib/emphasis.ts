/**
 * Making a figure's size visible before it is read.
 *
 * Every number in these tables carries the same typographic weight, so a JTD of
 * -14.8m and a CS01 of 4,500 look equally important and the eye has nothing to
 * land on. On a screen meant to be read before the open, that is the difference
 * between seeing where the risk is and having to work it out.
 *
 * The rule is deliberately narrow, because the obvious version of it is wrong.
 * Weight is only assigned *within a set of figures in the same unit*: down the
 * P&L column of a trade table, or across one row of the curve grid where every
 * cell is the same metric at a different tenor. Comparing down a column of the
 * curve grid would be comparing a JTD to a CS01, and comparing notionals across
 * a positions table would be comparing yen to dollars -- in both cases the
 * heaviest number on screen would be the one in the smallest currency.
 */

/** Fraction of the largest magnitude at which a figure is worth the eye. */
const DOMINANT_SHARE = 0.5;

/**
 * Which of `values` dominate their own set, as a predicate on magnitude.
 *
 * Returns a function rather than a list so a component can ask about a cell it
 * is already rendering without a second pass. A set with nothing in it, or
 * nothing but zeroes, dominates nothing.
 */
export function dominates(values: number[]): (value: number) => boolean {
  const largest = Math.max(0, ...values.map((value) => Math.abs(value)));
  if (largest === 0) return () => false;

  // A lone figure is not "the big one" -- there is nothing for it to be big
  // against, and marking it would put weight on every single-cell row.
  const meaningful = values.filter((value) => value !== 0);
  if (meaningful.length < 2) return () => false;

  return (value: number) => Math.abs(value) >= largest * DOMINANT_SHARE;
}
