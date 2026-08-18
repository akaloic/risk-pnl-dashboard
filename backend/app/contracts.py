"""Contract multipliers for the index derivatives.

The extracts do not carry a multiplier anywhere: trades.csv books equity
options and futures with a notional of 0 and a quantity in contracts, and
market_data.csv quotes them in index points. Without the point value an equity
P&L is wrong by the size of the multiplier -- a factor of 1,000 on the Nikkei
book.

The values below were recovered from the risk file rather than taken on faith.
For a future the pricing library's delta is the full notional exposure, so

    Delta_USD = quantity x multiplier x price / fx

which inverts to a multiplier once the other three are known. Testing each
round market convention against that identity leaves exactly one candidate per
contract that implies a believable index level:

    NKY-FUT-2026-09       multiplier 1,000 -> implied price   37,920.00
                          (the next candidates imply 3,792,000 or 151.68)
    KOSPI200-FUT-2026-09  multiplier   250 -> implied price      358.90
                          (the next candidates imply 89,725 or 0.3589)

Both were derived twice over, from independent trades -- the long and short
legs of the Nikkei future, and the two KOSPI futures -- and agree to eight
significant figures. Applying them to the equity options as a cross-check
implies deltas of 0.54, -0.44, 0.58 and -0.48, all of them credible.

HSI is the exception, and it is worth stating plainly rather than papering
over. The blotter holds Hang Seng *options* but no Hang Seng future, and an
option's delta carries the option's own sensitivity as a second unknown, so
the identity above cannot be inverted. 50 is the exchange's contract
specification (HK$50 per index point) and the extract is consistent with it:
it implies a call delta of 0.58, while any multiplier of 25 or below implies a
delta above 1, which is impossible. That rules out the small candidates but
not 100, which would imply 0.29. So HSI is corroborated, not derived, and that
distinction is the reason this paragraph exists.

Two further points for whoever picks this up:

*The risk file prices are not the market data prices.* The implied levels
above appear nowhere in market_data.csv, whose quotes all carry four decimals
of noise, so the pricing library valued these contracts off a snapshot we were
not given. On KOSPI the gap is material -- 358.90 against a close of 343.4536,
some 4.5% -- so equity delta taken from the risk file and equity P&L computed
from the market data cannot be expected to tie out exactly.

*KOSPI 200 does not match the live exchange spec.* The KRX quotes its future
at KRW 250,000 per point, not 250. Every delta in this extract is consistent
with 250 and none with 250,000, so the data wins here -- but the value must
not be copied into a system pricing real KOSPI risk without rechecking it.
"""

# Point value of one contract, in the contract's own currency, keyed on the
# underlying prefix of the instrument id (NKY-FUT-2026-09 -> NKY).
CONTRACT_MULTIPLIERS: dict[str, float] = {
    "NKY": 1_000.0,  # JPY per index point -- derived from the future's delta
    "HSI": 50.0,  # HKD per index point -- exchange spec, corroborated only
    "KOSPI200": 250.0,  # KRW per index point -- derived from the future's delta
}


def multiplier_for(instrument_id: str) -> float:
    """Point value of one contract of `instrument_id`, in the trade currency.

    Raises rather than defaulting to 1.0: a silent default would price a
    Nikkei future at a thousandth of its size and still return a number that
    looks entirely plausible on a screen.
    """
    underlying = str(instrument_id).split("-", 1)[0].upper()
    try:
        return CONTRACT_MULTIPLIERS[underlying]
    except KeyError:
        raise KeyError(
            f"No contract multiplier configured for {instrument_id!r} "
            f"(underlying {underlying!r}). Known underlyings: "
            f"{sorted(CONTRACT_MULTIPLIERS)}. Add it to CONTRACT_MULTIPLIERS "
            "together with the derivation used to obtain it."
        ) from None
