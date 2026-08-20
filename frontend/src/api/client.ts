/**
 * Typed access to the backend.
 *
 * One place that knows where the data comes from and how a failure is
 * surfaced. The backend answers a bad date with a 400 and an explanation
 * naming the range it covers, so that message is carried through to the screen
 * rather than replaced by a generic "something went wrong" -- a trader who
 * asked for a Saturday should be told so.
 *
 * The screen also runs with no backend at all, off the recording written by
 * scripts/export_static_api.py, which is what the published copy reads. The
 * difference is confined to two lines here and to api/urls.ts; a recorded run
 * has to fail the same way a live one does, so a day the recording does not
 * hold produces the same sentence a live 400 would.
 */

import { liveUrl, recordedUrl } from "./urls";
import type {
  CounterpartyExposure,
  DataQualityResponse,
  Health,
  PnLResponse,
  Position,
  ReconciliationResponse,
  RiskResponse,
  TradePnL,
} from "./types";

/**
 * Whether the screen is reading a recording rather than a running backend.
 *
 * Set at build time, by the workflow that publishes to Pages. Worth exporting:
 * the export script refuses to read anything but the demo desk, so this flag
 * is also the answer to "are the figures on this screen invented?" -- which the
 * header then says out loud rather than leaving to be discovered.
 */
export const RECORDED = import.meta.env.VITE_STATIC_API === "1";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function get<T>(path: string, date?: string): Promise<T> {
  const url = RECORDED
    ? recordedUrl(import.meta.env.BASE_URL, path, date)
    : liveUrl(BASE_URL, path, date);

  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new ApiError(
      RECORDED
        ? "Cannot load the published data files."
        : `Cannot reach the API at ${BASE_URL}. Is the backend running?`,
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await explain(response, date), response.status);
  }

  // A file server asked for something it does not have answers in one of two
  // ways: a 404, or -- where it falls back to the app's own index.html, which
  // most do -- a 200 with a page of HTML in it. Both mean the same thing here,
  // and neither may reach JSON.parse, whose complaint about an unexpected "<"
  // reads as a broken site rather than as a day that was never priced.
  if (RECORDED && !holdsJson(response)) {
    throw new ApiError(missing(date), 404);
  }
  return (await response.json()) as T;
}

function holdsJson(response: Response): boolean {
  return response.headers.get("content-type")?.includes("json") ?? false;
}

/**
 * What a recording says when it does not hold the day it was asked for.
 *
 * The live API refuses that day with a sentence naming the range it covers, so
 * the recorded one says something of the same kind. Picking a Saturday has to
 * read the same way in both.
 */
function missing(date?: string): string {
  return date
    ? `${date} is not a business day this dataset prices.`
    : "This view is missing from the published data.";
}

/** Prefer the backend's own explanation over a status code. */
async function explain(response: Response, date?: string): Promise<string> {
  if (RECORDED && response.status === 404) return missing(date);

  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      return `Invalid request: ${body.detail[0].msg}`;
    }
  } catch {
    /* fall through to the status text */
  }
  return `${response.status} ${response.statusText}`;
}

export const api = {
  health: () => get<Health>("/health"),
  positions: (date?: string) => get<Position[]>("/positions", date),
  pnl: (date?: string) => get<PnLResponse>("/pnl", date),
  pnlByTrade: (date?: string) => get<TradePnL[]>("/pnl/trades", date),
  risk: (date?: string) => get<RiskResponse>("/risk", date),
  counterparty: (date?: string) => get<CounterpartyExposure[]>("/counterparty", date),
  dataQuality: (date?: string) => get<DataQualityResponse>("/data-quality", date),
  reconciliation: (date?: string) =>
    get<ReconciliationResponse>("/reconciliation", date),
};
