/**
 * Where a request goes: a running backend, or a recording of one.
 *
 * The screen is published on GitHub Pages, which serves files and runs no
 * processes, so the same React app has to be able to read a directory of JSON
 * written by scripts/export_static_api.py. The two modes differ in exactly one
 * thing -- how a path and a date become a URL -- so that is the only thing
 * this file decides, and every hook and component above it is unaware there
 * are two.
 *
 * The recording mirrors the URLs, which is what keeps the rule to one line:
 * /pnl/trades on 2026-07-15 is api/2026-07-15/pnl/trades.json, and a call
 * naming no date reads latest/, the directory the export writes for whatever
 * the API's own default as-of turns out to be.
 */

/** A live backend, which reads the date off the query string. */
export function liveUrl(base: string, path: string, date?: string): string {
  const url = new URL(path, base);
  if (date) url.searchParams.set("as_of", date);
  return url.toString();
}

/**
 * The recorded copy, which reads it off the path.
 *
 * `base` is Vite's BASE_URL: "/" in development, "/risk-pnl-dashboard/" on
 * Pages. Getting that wrong is the one way this can fail in production and
 * nowhere else, so the trailing slash is enforced here rather than assumed.
 */
export function recordedUrl(base: string, path: string, date?: string): string {
  const root = base.endsWith("/") ? base : `${base}/`;
  return `${root}api/${date ?? "latest"}${path}.json`;
}
