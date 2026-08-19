import { describe, expect, it } from "vitest";
import type { TradePnL } from "../api/types";
import { positionKey, positionsByInstrument } from "./legs";

const trade = (
  id: string,
  instrument: string,
  product: string,
  usd: number,
): TradePnL => ({
  trade_id: id,
  book_id: "EQD-ASIA-01",
  asset_class: "EQUITY",
  product_type: product,
  instrument_id: instrument,
  currency: "JPY",
  method: "EQUITY_CONTRACT",
  valuation_date: "2026-08-05",
  reference_level: 0,
  current_level: 0,
  pnl_ccy: 0,
  pnl_currency: "JPY",
  pnl_usd: usd,
});

describe("positionsByInstrument", () => {
  it("nets the two legs of one instrument", () => {
    // The real case: read as separate lines these are the desk's two worst
    // trades. Netted they are one position that lost a tenth as much.
    const groups = positionsByInstrument([
      trade("TRD-034", "NKY-FUT-2026-09", "EQ_FUTURE", -113_448),
      trade("TRD-039", "NKY-FUT-2026-09", "EQ_FUTURE", 103_301),
    ]);

    const position = groups.get("NKY-FUT-2026-09/EQ_FUTURE");
    expect(position?.tradeIds).toEqual(["TRD-034", "TRD-039"]);
    expect(position?.net).toBeCloseTo(-10_147, 0);
  });

  it("keeps a spot and a forward on the same pair apart", () => {
    // They close on different dates, so they are two positions. The positions
    // engine keys them separately and this has to agree with it.
    const groups = positionsByInstrument([
      trade("TRD-021", "USDJPY", "FX_SPOT", 1_000),
      trade("TRD-028", "USDJPY", "FX_FORWARD", -74_437),
    ]);

    expect(groups.size).toBe(2);
    expect(groups.get("USDJPY/FX_SPOT")?.net).toBe(1_000);
    expect(groups.get("USDJPY/FX_FORWARD")?.net).toBe(-74_437);
  });

  it("leaves a lone trade as a group of one", () => {
    // The component keys off the group size, so a single trade must not be
    // flagged as a leg of anything.
    const groups = positionsByInstrument([trade("TRD-005", "JGB-0.5-2033", "GOVT_BOND", 20_440)]);

    expect(groups.get("JGB-0.5-2033/GOVT_BOND")?.tradeIds).toHaveLength(1);
  });

  it("handles an empty book", () => {
    expect(positionsByInstrument([]).size).toBe(0);
  });
});

describe("positionKey", () => {
  it("agrees with the key the grouping used", () => {
    const row = trade("TRD-034", "NKY-FUT-2026-09", "EQ_FUTURE", -1);
    expect(positionsByInstrument([row]).has(positionKey(row))).toBe(true);
  });
});
