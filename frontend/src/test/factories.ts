/**
 * Payload builders for the rendering tests.
 *
 * Every field is filled with something plausible and overridden per test, so a
 * test reads as the one thing it is about rather than as forty lines of
 * scaffolding. The shapes come from api/types.ts, which mirrors the pydantic
 * models -- if the API contract changes, these stop compiling.
 */

import type {
  BookSummary,
  DailyPnL,
  DataQualityIssue,
  PnLResponse,
  Position,
  RiskResponse,
  TenorExposure,
  TradePnL,
} from "../api/types";

export const book = (over: Partial<BookSummary> = {}): BookSummary => ({
  book_id: "EQD-ASIA-01",
  day_usd: -142_919,
  inception_usd: -128_798,
  trade_count: 10,
  open_positions: 6,
  ...over,
});

export const pnlResponse = (over: Partial<PnLResponse> = {}): PnLResponse => ({
  as_of: "2026-08-05",
  reporting_currency: "USD",
  total_day_usd: -178_379,
  total_inception_usd: -443_715,
  by_book: [book()],
  series: [],
  ...over,
});

export const daily = (over: Partial<DailyPnL> = {}): DailyPnL => ({
  date: "2026-08-05",
  book_id: "EQD-ASIA-01",
  daily_usd: -1_000,
  cumulative_usd: -5_000,
  ...over,
});

export const trade = (over: Partial<TradePnL> = {}): TradePnL => ({
  trade_id: "TRD-034",
  book_id: "EQD-ASIA-01",
  asset_class: "EQUITY",
  product_type: "EQ_FUTURE",
  instrument_id: "NKY-FUT-2026-09",
  currency: "JPY",
  method: "EQUITY_CONTRACT",
  valuation_date: "2026-08-05",
  reference_level: 37_880,
  current_level: 37_794.75,
  pnl_ccy: -17_049_820,
  pnl_currency: "JPY",
  pnl_usd: -113_448.1,
  ...over,
});

export const tenor = (over: Partial<TenorExposure> = {}): TenorExposure => ({
  book_id: "EQD-ASIA-01",
  risk_metric: "Delta_USD",
  tenor_bucket: "0-3M",
  open_usd: 37_924_168,
  trade_count: 10,
  ...over,
});

export const riskResponse = (over: Partial<RiskResponse> = {}): RiskResponse => ({
  as_of: "2026-08-05",
  by_book: [
    {
      book_id: "EQD-ASIA-01",
      risk_metric: "Delta_USD",
      open_usd: 37_924_168,
      settled_usd: 0,
      total_usd: 37_924_168,
      trade_count: 10,
    },
  ],
  by_tenor: [tenor()],
  per_trade_tenors: [],
  ...over,
});

export const position = (over: Partial<Position> = {}): Position => ({
  book_id: "EQD-ASIA-01",
  instrument_id: "NKY-FUT-2026-09",
  instrument_description: "Nikkei 225 Future Sep26",
  product_type: "EQ_FUTURE",
  asset_class: "EQUITY",
  currency: "JPY",
  net_quantity: 100,
  gross_quantity: 300,
  net_notional: 0,
  trade_count: 2,
  trade_ids: ["TRD-034", "TRD-039"],
  position_status: "OPEN",
  maturity_date: "2026-09-11",
  ...over,
});

export const issue = (over: Partial<DataQualityIssue> = {}): DataQualityIssue => ({
  code: "DUPLICATE_TRADE_ROW",
  severity: "ERROR",
  entity_type: "trade",
  entity_id: "TRD-015",
  detail: "1 exact duplicate row in the blotter",
  treatment: "Duplicate row dropped, first occurrence kept.",
  ...over,
});
