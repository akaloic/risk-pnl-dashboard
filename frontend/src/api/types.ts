/**
 * Wire types, mirroring the pydantic response models the backend publishes.
 *
 * Written by hand rather than generated: the backend serves its own OpenAPI
 * schema at /openapi.json, so a generator is available if this ever grows, but
 * for six endpoints a hand-kept file is easier to read and adds no build step.
 * The API integration tests assert the shapes these types assume.
 */

export type PositionStatus = "OPEN" | "SETTLED";
export type Severity = "ERROR" | "WARNING" | "INFO";

export interface Health {
  status: string;
  as_of: string;
  reporting_currency: string;
  trades: number;
  business_days: number;
  first_business_day: string;
  last_business_day: string;
}

export interface Position {
  book_id: string;
  asset_class: string;
  product_type: string;
  instrument_id: string;
  instrument_description: string;
  currency: string;
  position_status: PositionStatus;
  maturity_date: string | null;
  net_quantity: number;
  gross_quantity: number;
  net_notional: number;
  trade_count: number;
  trade_ids: string[];
}

export interface BookSummary {
  book_id: string;
  day_usd: number;
  inception_usd: number;
  trade_count: number;
  open_positions: number;
}

export interface DailyPnL {
  date: string;
  book_id: string;
  daily_usd: number;
  cumulative_usd: number;
}

export interface PnLResponse {
  as_of: string;
  reporting_currency: string;
  total_day_usd: number;
  total_inception_usd: number;
  by_book: BookSummary[];
  series: DailyPnL[];
}

export interface TradePnL {
  trade_id: string;
  book_id: string;
  asset_class: string;
  product_type: string;
  instrument_id: string;
  currency: string;
  method: string;
  valuation_date: string;
  reference_level: number;
  current_level: number;
  pnl_ccy: number;
  pnl_currency: string;
  pnl_usd: number;
}

export interface RiskAggregate {
  book_id: string;
  risk_metric: string;
  open_usd: number;
  settled_usd: number;
  total_usd: number;
  trade_count: number;
}

export interface RiskResponse {
  as_of: string;
  by_book: RiskAggregate[];
  per_trade_tenors: Record<string, unknown>[];
}

export interface DataQualityIssue {
  code: string;
  severity: Severity;
  entity_type: string;
  entity_id: string;
  detail: string;
  treatment: string;
}

export interface DataQualityResponse {
  as_of: string;
  counts: Record<string, number>;
  issues: DataQualityIssue[];
}

export interface ReconciliationResponse {
  as_of: string;
  coverage: Record<string, unknown>[];
  issues: DataQualityIssue[];
}
