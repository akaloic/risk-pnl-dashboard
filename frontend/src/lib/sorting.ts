/**
 * Sorting a positions table the way a desk reads one.
 *
 * Two rules, and the first is the one that is not obvious.
 *
 * *Numbers sort by magnitude, not by value.* On a risk table the question is
 * "what is my biggest position", and a short of 5m matters exactly as much as a
 * long of 5m. Sorting signed would bury every short at the bottom of the table
 * behind every long, however small. The sign is carried by colour instead.
 *
 * *The direction toggles.* Clicking a column that is already sorted reverses
 * it, which is the convention everywhere else and therefore the only thing a
 * user will predict. It is a plain reversal rather than a switch to signed
 * order: answering "biggest short" by making the second click mean something
 * different from the first is cleverer than it is usable, and the biggest short
 * is already near the top of a magnitude sort.
 */

export type SortDirection = "asc" | "desc";

export interface SortState<K> {
  key: K;
  direction: SortDirection;
}

/** What the next click on `key` should produce, given where the table is now. */
export function nextSort<K>(current: SortState<K>, key: K): SortState<K> {
  if (current.key !== key) return { key, direction: "desc" };
  return { key, direction: current.direction === "desc" ? "asc" : "desc" };
}

/**
 * Order `rows` by `state`. Numbers compare on magnitude, everything else on
 * its text, and `desc` means largest or last first.
 */
export function sortRows<T, K extends keyof T>(rows: T[], state: SortState<K>): T[] {
  const factor = state.direction === "desc" ? 1 : -1;

  return [...rows].sort((a, b) => {
    const left = a[state.key];
    const right = b[state.key];

    if (typeof left === "number" && typeof right === "number") {
      return factor * (Math.abs(right) - Math.abs(left));
    }
    return factor * String(right).localeCompare(String(left));
  });
}

/** The value for a header's `aria-sort`, so the order is announced not implied. */
export function ariaSortFor<K>(state: SortState<K>, key: K): "ascending" | "descending" | "none" {
  if (state.key !== key) return "none";
  return state.direction === "asc" ? "ascending" : "descending";
}
