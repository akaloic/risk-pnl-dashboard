/**
 * Formatting decisions the screen depends on, pinned so a later tidy-up cannot
 * quietly undo them.
 */

import { describe, expect, it } from "vitest";
import { level, plain, shortDate, signOf, usd, usdPrecise } from "./format";

describe("usd", () => {
  it("groups thousands and drops the cents", () => {
    expect(usd(-443_714.9)).toBe("-$443,715");
    expect(usd(1_284_913)).toBe("$1,284,913");
  });

  it("marks a loss with a minus, not parentheses", () => {
    // The desk reports to a mixed audience and the accounting convention reads
    // as a typo to half of it.
    expect(usd(-26_826)).toBe("-$26,826");
    expect(usd(-26_826)).not.toContain("(");
  });

  it("never falls back to exponent form", () => {
    // A JTD of -14.8m rendered as "-1.48e7" is unreadable on a risk grid.
    expect(usd(-14_793_566)).toBe("-$14,793,566");
    expect(usd(19_438_300)).not.toMatch(/e[+-]/i);
  });

  it("keeps zero unsigned", () => {
    expect(usd(0)).toBe("$0");
  });
});

describe("usdPrecise", () => {
  it("keeps both cents where a figure has to tie out", () => {
    // The trade table foots to the book card; rounding there would show a
    // total that disagrees with its own rows.
    expect(usdPrecise(-232_000.24)).toBe("-$232,000.24");
    expect(usdPrecise(330)).toBe("$330.00");
  });
});

describe("level", () => {
  it("shows a market level to the precision it was quoted at", () => {
    // 1.3363 is a rate, not a rounding of 1.34: a forward shown to two places
    // hides the move being priced.
    expect(level(1.3363)).toBe("1.3363");
    expect(level(150)).toBe("150.00");
    expect(level(1_362)).toBe("1,362.00");
  });
});

describe("plain", () => {
  it("groups without a currency symbol", () => {
    expect(plain(38_500)).toBe("38,500");
  });
});

describe("signOf", () => {
  it("leaves zero neutral rather than calling it a gain", () => {
    expect(signOf(0)).toBe("flat");
    expect(signOf(0.4)).toBe("up");
    expect(signOf(-0.4)).toBe("down");
  });
});

describe("shortDate", () => {
  it("drops the year and the leading zero", () => {
    expect(shortDate("2026-08-05")).toBe("5 Aug");
    expect(shortDate("2026-07-03")).toBe("3 Jul");
    expect(shortDate("2026-12-31")).toBe("31 Dec");
  });

  it("reads the string rather than parsing a Date", () => {
    // new Date("2026-08-05") is UTC midnight, which is 4 August in the
    // Americas -- the axis would be a day out for anyone west of Greenwich.
    expect(shortDate("2026-01-01")).toBe("1 Jan");
  });
});
