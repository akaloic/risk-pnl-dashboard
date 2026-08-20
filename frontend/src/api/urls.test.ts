import { describe, expect, it } from "vitest";
import { liveUrl, recordedUrl } from "./urls";

describe("liveUrl", () => {
  it("puts the date on the query string under the name the API reads", () => {
    expect(liveUrl("http://localhost:8000", "/pnl", "2026-07-15")).toBe(
      "http://localhost:8000/pnl?as_of=2026-07-15",
    );
  });

  it("leaves the date off when none was asked for", () => {
    expect(liveUrl("http://localhost:8000", "/health")).toBe("http://localhost:8000/health");
  });
});

describe("recordedUrl", () => {
  it("mirrors a nested path into a nested file", () => {
    expect(recordedUrl("/", "/pnl/trades", "2026-07-15")).toBe(
      "/api/2026-07-15/pnl/trades.json",
    );
  });

  it("reads latest/ when no date is named, which is what health does", () => {
    expect(recordedUrl("/", "/health")).toBe("/api/latest/health.json");
  });

  it("keeps the project prefix Pages serves the site under", () => {
    // The failure this exists to prevent: correct in development, where the
    // base is "/", and 404 on every request once deployed under a project
    // path -- which is the one place nobody runs the tests.
    expect(recordedUrl("/risk-pnl-dashboard/", "/risk", "2026-08-05")).toBe(
      "/risk-pnl-dashboard/api/2026-08-05/risk.json",
    );
  });

  it("tolerates a base handed over without its trailing slash", () => {
    expect(recordedUrl("/risk-pnl-dashboard", "/positions")).toBe(
      "/risk-pnl-dashboard/api/latest/positions.json",
    );
  });
});
