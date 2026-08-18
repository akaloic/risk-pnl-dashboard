/**
 * Typed access to the backend.
 *
 * One place that knows the base URL and how a failure is surfaced. The backend
 * answers a bad date with a 400 and an explanation naming the range it covers,
 * so that message is carried through to the screen rather than replaced by a
 * generic "something went wrong" -- a trader who asked for a Saturday should be
 * told so.
 */

import type {
  DataQualityResponse,
  Health,
  PnLResponse,
  Position,
  ReconciliationResponse,
  RiskResponse,
  TradePnL,
} from "./types";

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
  const url = new URL(path, BASE_URL);
  if (date) url.searchParams.set("date", date);

  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${BASE_URL}. Is the backend running?`,
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await explain(response), response.status);
  }
  return (await response.json()) as T;
}

/** Prefer the backend's own explanation over a status code. */
async function explain(response: Response): Promise<string> {
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
  dataQuality: (date?: string) => get<DataQualityResponse>("/data-quality", date),
  reconciliation: (date?: string) =>
    get<ReconciliationResponse>("/reconciliation", date),
};
