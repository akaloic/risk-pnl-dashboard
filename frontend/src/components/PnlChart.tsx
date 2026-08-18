/**
 * Daily P&L: bars for the day, a line for the running total.
 *
 * Hand-drawn SVG rather than a charting library. The shape is simple enough
 * that a dependency would cost more than it saves, and it keeps the project to
 * two install steps -- which the brief counts as a feature.
 */

import { useMemo, useState } from "react";
import type { DailyPnL } from "../api/types";
import { shortDate, usd } from "../lib/format";

const WIDTH = 900;
const HEIGHT = 260;
const PAD = { top: 16, right: 56, bottom: 26, left: 68 };

interface Day {
  date: string;
  daily: number;
  cumulative: number;
}

function totalsByDate(series: DailyPnL[]): Day[] {
  const byDate = new Map<string, Day>();
  for (const row of series) {
    const day = byDate.get(row.date) ?? { date: row.date, daily: 0, cumulative: 0 };
    day.daily += row.daily_usd;
    day.cumulative += row.cumulative_usd;
    byDate.set(row.date, day);
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export function PnlChart({ series, book }: { series: DailyPnL[]; book: string | null }) {
  const [hovered, setHovered] = useState<Day | null>(null);

  const days = useMemo(
    () => totalsByDate(book ? series.filter((row) => row.book_id === book) : series),
    [series, book],
  );

  if (days.length === 0) return <div className="state">No P&amp;L for this period.</div>;

  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;

  // Bars and line share an axis so the two can be read against each other.
  const values = days.flatMap((day) => [day.daily, day.cumulative]);
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const span = max - min || 1;

  const y = (value: number) => PAD.top + ((max - value) / span) * plotHeight;
  const step = plotWidth / days.length;
  const barWidth = Math.max(2, step * 0.6);
  const zero = y(0);

  const line = days
    .map((day, index) => {
      const x = PAD.left + index * step + step / 2;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y(day.cumulative).toFixed(1)}`;
    })
    .join(" ");

  const ticks = [max, max - span / 2, min].filter(
    (value, index, all) => all.indexOf(value) === index,
  );

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" role="img"
           aria-label="Daily and cumulative P&L in USD">
        {ticks.map((value) => (
          <g key={value}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(value)} y2={y(value)}
                  stroke="#2a333d" strokeDasharray="2 3" />
            <text x={PAD.left - 8} y={y(value) + 4} textAnchor="end"
                  fontSize="10" fill="#8a97a6">
              {usd(value)}
            </text>
          </g>
        ))}

        <line x1={PAD.left} x2={WIDTH - PAD.right} y1={zero} y2={zero} stroke="#3a4653" />

        {days.map((day, index) => {
          const x = PAD.left + index * step + step / 2 - barWidth / 2;
          const top = day.daily >= 0 ? y(day.daily) : zero;
          const height = Math.abs(y(day.daily) - zero);
          return (
            <rect
              key={day.date}
              x={x}
              y={top}
              width={barWidth}
              height={Math.max(height, 0.5)}
              fill={day.daily >= 0 ? "#3fbf7f" : "#f2545b"}
              opacity={hovered && hovered.date !== day.date ? 0.35 : 0.85}
              onMouseEnter={() => setHovered(day)}
              onMouseLeave={() => setHovered(null)}
            />
          );
        })}

        <path d={line} fill="none" stroke="#4a9eff" strokeWidth="1.8" />

        {days.map((day, index) => {
          if (index % Math.ceil(days.length / 8) !== 0 && index !== days.length - 1) return null;
          return (
            <text key={day.date} x={PAD.left + index * step + step / 2}
                  y={HEIGHT - 8} textAnchor="middle" fontSize="10" fill="#8a97a6">
              {shortDate(day.date)}
            </text>
          );
        })}
      </svg>

      <div style={{ display: "flex", gap: 18, fontSize: 11, color: "#8a97a6", marginTop: 4 }}>
        <span><span style={{ color: "#3fbf7f" }}>▮</span> daily move</span>
        <span><span style={{ color: "#4a9eff" }}>—</span> cumulative</span>
        {hovered && (
          <span style={{ marginLeft: "auto", color: "#e4e9ee" }}>
            {shortDate(hovered.date)} · day {usd(hovered.daily)} · total {usd(hovered.cumulative)}
          </span>
        )}
      </div>
    </div>
  );
}
