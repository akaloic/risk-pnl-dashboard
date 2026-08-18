/**
 * Number formatting for a trading screen.
 *
 * Figures are read at a glance and compared down a column, so they are grouped,
 * right-alignable and never shown in exponent form. Losses carry a minus rather
 * than parentheses -- the desk reports in USD to a mixed audience, and the
 * accounting convention reads as a typo to half of it.
 */

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const USD_PRECISE = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const PLAIN = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

const LEVEL = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

export const usd = (value: number) => USD.format(value);
export const usdPrecise = (value: number) => USD_PRECISE.format(value);
export const plain = (value: number) => PLAIN.format(value);
export const level = (value: number) => LEVEL.format(value);

/** Sign class for colouring a P&L figure, with zero left neutral. */
export function signOf(value: number): "up" | "down" | "flat" {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

/** 2026-08-05 -> 5 Aug, for axis ticks where the year is already known. */
export function shortDate(iso: string): string {
  const [, month, day] = iso.split("-");
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return `${Number(day)} ${months[Number(month) - 1]}`;
}
