// @vitest-environment jsdom
/**
 * What the screen does when the data is late or missing. These are the states a
 * user meets on a bad morning, and the ones least likely to be looked at while
 * building on a good one.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Empty, Loadable } from "./Loading";

describe("Loadable", () => {
  it("shows the backend's own explanation rather than a status code", async () => {
    // The API answers a bad date with the range it covers. Replacing that with
    // "something went wrong" throws away the only useful part.
    render(
      <Loadable loading={false} error="2026-08-08 is not a day this extract prices">
        <p>numbers</p>
      </Loadable>,
    );

    expect(screen.getByText(/is not a day this extract prices/)).toBeDefined();
    expect(screen.queryByText("numbers")).toBeNull();
  });

  it("offers a retry only when there is something to retry with", async () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <Loadable loading={false} error="failed" onRetry={onRetry}>
        <p>numbers</p>
      </Loadable>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();

    rerender(
      <Loadable loading={false} error="failed">
        <p>numbers</p>
      </Loadable>,
    );
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("keeps the previous numbers on screen while refreshing", async () => {
    // Stepping through the month a day at a time is the main way this is used.
    // Blanking every panel on each step makes a working tool feel broken.
    render(
      <Loadable loading={false} refreshing error={null}>
        <p>previous numbers</p>
      </Loadable>,
    );

    expect(screen.getByText("previous numbers")).toBeDefined();
    expect(screen.getByText("Updating…")).toBeDefined();
  });

  it("blanks only on a first load, when there is nothing to keep", () => {
    render(
      <Loadable loading error={null}>
        <p>numbers</p>
      </Loadable>,
    );

    expect(screen.getByText("Loading…")).toBeDefined();
    expect(screen.queryByText("numbers")).toBeNull();
  });

  it("prefers the error over a stale result", () => {
    // Leaving the previous date's figures under a new date is worse than an
    // empty panel: both look like an answer, and one of them is wrong.
    render(
      <Loadable loading refreshing error="the request failed">
        <p>previous numbers</p>
      </Loadable>,
    );

    expect(screen.getByText("the request failed")).toBeDefined();
    expect(screen.queryByText("previous numbers")).toBeNull();
  });
});

describe("Empty", () => {
  it("says why a table is empty rather than showing nothing", () => {
    render(<Empty>No positions on this date.</Empty>);

    expect(screen.getByText("No positions on this date.")).toBeDefined();
  });
});
