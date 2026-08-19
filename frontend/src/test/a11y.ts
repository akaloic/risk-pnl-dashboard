/**
 * Running axe over what a component actually renders.
 *
 * The linter reads the source and catches an attribute that is wrong on sight.
 * It does not catch a `role="tab"` with no tablist around it, an aria-controls
 * pointing at an id that never renders, or a table whose headers are fine in
 * isolation and unassociated once the rows are there. Those are properties of
 * the output, and this project shipped two of them: `aria-selected` on plain
 * buttons survived an accessibility pass, and the tab strip claimed a pattern
 * it did not implement. Both are exactly what axe reports in one line.
 *
 * Colour rules are left out. jsdom computes no layout and no cascade, so
 * contrast checks there are guesswork -- switching them on would produce
 * confident results about a page nobody has painted.
 */

import axe, { type AxeResults, type RunOptions } from "axe-core";
import { expect } from "vitest";

const OPTIONS: RunOptions = {
  resultTypes: ["violations"],
  rules: {
    "color-contrast": { enabled: false },
    // A rendered fragment is not a document: a component under test has no
    // landmarks, no <main> and no page title, and saying so on every test
    // would train the reader to skim past the output.
    region: { enabled: false },
  },
};

function describeViolations(results: AxeResults): string {
  return results.violations
    .map((violation) => {
      const where = violation.nodes.map((node) => `      ${node.html}`).join("\n");
      return `  [${violation.impact}] ${violation.id}: ${violation.help}\n${where}`;
    })
    .join("\n");
}

/** Fail with what axe found and where, rather than with a count. */
export async function expectNoViolations(container: HTMLElement): Promise<void> {
  const results = await axe.run(container, OPTIONS);

  expect(describeViolations(results), describeViolations(results)).toBe("");
}
