import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * The flag is read once, when the module is first imported, so each mode needs
 * its own fresh copy of the module rather than a value flipped underneath one.
 */
async function clientReading(source: "a live backend" | "the recording") {
  vi.stubEnv("VITE_STATIC_API", source === "the recording" ? "1" : "");
  vi.resetModules();
  return await import("./client");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("reading the recording", () => {
  it("asks for the file the export actually wrote", async () => {
    const { api } = await clientReading("the recording");
    const fetcher = vi.fn().mockResolvedValue(Response.json([]));
    vi.stubGlobal("fetch", fetcher);

    await api.pnlByTrade("2026-07-15");

    expect(fetcher).toHaveBeenCalledWith("/api/2026-07-15/pnl/trades.json");
  });

  it("refuses a Saturday in the words the live API would have used", async () => {
    const { api } = await clientReading("the recording");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<!doctype html>", { status: 404 })),
    );

    await expect(api.pnl("2026-08-11")).rejects.toThrow(
      "2026-08-11 is not a business day this dataset prices.",
    );
  });

  it("says the same thing when the host answers the miss with its index page", async () => {
    // Not hypothetical: `vite preview` does exactly this, and so does every
    // host configured to fall back for a single-page app. The status is 200
    // and the body is HTML, so without the content-type check the screen
    // reported `SyntaxError: Unexpected token '<'` -- which reads as the site
    // being broken rather than as a day that never had a price.
    const { api } = await clientReading("the recording");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!doctype html><div id=root></div>", {
          status: 200,
          headers: { "content-type": "text/html" },
        }),
      ),
    );

    await expect(api.pnl("2026-07-11")).rejects.toThrow(
      "2026-07-11 is not a business day this dataset prices.",
    );
  });
});

describe("reading a live backend", () => {
  it("carries the backend's own explanation through rather than a status code", async () => {
    const { api } = await clientReading("a live backend");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json(
          { detail: "as_of=2030-01-01 is not a day this extract prices" },
          { status: 400 },
        ),
      ),
    );

    await expect(api.pnl("2030-01-01")).rejects.toThrow("not a day this extract prices");
  });

  it("names the address it could not reach, which is the usual cause", async () => {
    const { api } = await clientReading("a live backend");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));

    await expect(api.health()).rejects.toThrow("Is the backend running?");
  });
});
