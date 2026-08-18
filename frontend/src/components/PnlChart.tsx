/**
 * Daily P&L: bars for the day, a line for the running total.
 *
 * One shared axis covers both series — on this extract they span 1.29m and
 * 1.35m, within 5% of each other, so a single axis costs nothing and lets a
 * bar and the line be read directly against the same zero. Ticks land on round
 * numbers ($500k, $0, −$500k) rather than data artifacts like $906,542.
 *
 * Hand-drawn SVG rather than a charting library: the shape is simple enough
 * that a dependency would cost more than it saves, and the project stays at
 * two install steps.
 */

import { useMemo, useState } from "react";
import type { DailyPnL } from "../api/types";
import { shortDate, usd } from "../lib/format";
import { niceScale } from "../lib/scale";

const WIDTH = 900;
const HEIGHT = 280;
const PAD = { top: 18, right: 74, bottom: 28, left: 74 };

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

  const scale = useMemo(
    () => niceScale([...days.map((day) => day.daily), ...days.map((day) => day.cumulative)]),
    [days],
  );

  if (days.length === 0) return <div className="state">No P&amp;L for this period.</div>;

  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;

  const y = (value: number) =>
    PAD.top + ((scale.max - value) / (scale.max - scale.min || 1)) * plotHeight;

  const zero = y(0);

  const step = plotWidth / days.length;
  const barWidth = Math.max(2, step * 0.58);

  const line = days
    .map((day, index) => {
      const x = PAD.left + index * step + step / 2;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y(day.cumulative).toFixed(1)}`;
    })
    .join(" ");

  const shown = hovered ?? days[days.length - 1];

  return (
    <div style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        role="img"
        aria-label={`Daily and cumulative P&L in USD, ${days[0].date} to ${days[days.length - 1].date}`}
      >
        {scale.ticks.map((value) => (
          <g key={`tick${value}`}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={y(value)}
              y2={y(value)}
              stroke={value === 0 ? "#3a4653" : "#232b34"}
              strokeDasharray={value === 0 ? undefined : "2 4"}
            />
            <text
              x={PAD.left - 8}
              y={y(value) + 4}
              textAnchor="end"
              fontSize="10"
              fill="#7f8b99"
            >
              {usd(value)}
            </text>
          </g>
        ))}

        {days.map((day, index) => {
          const x = PAD.left + index * step;
          const barX = x + step / 2 - barWidth / 2;
          const top = day.daily >= 0 ? y(day.daily) : zero;
          return (
            <g key={day.date}>
              <rect
                x={barX}
                y={top}
                width={barWidth}
                height={Math.max(Math.abs(y(day.daily) - zero), 0.75)}
                fill={day.daily >= 0 ? "#3fbf7f" : "#f2545b"}
                opacity={hovered && hovered.date !== day.date ? 0.3 : 0.85}
              />
              {/* Full-height target: a thin bar is hard to hit with a mouse. */}
              <rect
                x={x}
                y={PAD.top}
                width={step}
                height={plotHeight}
                fill="transparent"
                onMouseEnter={() => setHovered(day)}
                onMouseLeave={() => setHovered(null)}
              />
            </g>
          );
        })}

        <path d={line} fill="none" stroke="#4a9eff" strokeWidth="1.8" />

        {hovered && (
          <circle
            cx={PAD.left + days.indexOf(hovered) * step + step / 2}
            cy={y(hovered.cumulative)}
            r="3.5"
            fill="#4a9eff"
          />
        )}

        {days.map((day, index) => {
          const every = Math.ceil(days.length / 8);
          if (index % every !== 0 && index !== days.length - 1) return null;
          return (
            <text
              key={day.date}
              x={PAD.left + index * step + step / 2}
              y={HEIGHT - 9}
              textAnchor="middle"
              fontSize="10"
              fill="#7f8b99"
            >
              {shortDate(day.date)}
            </text>
          );
        })}
      </svg>

      <div className="chart-legend">
        <span>
          <span style={{ color: "#3fbf7f" }}>▮</span> daily move
        </span>
        <span>
          <span style={{ color: "#4a9eff" }}>—</span> cumulative
        </span>
        <span style={{ marginLeft: "auto", color: "#e4e9ee" }}>
          {shortDate(shown.date)} · day{" "}
          <span className={shown.daily >= 0 ? "up" : "down"}>{usd(shown.daily)}</span> · total{" "}
          <span className={shown.cumulative >= 0 ? "up" : "down"}>{usd(shown.cumulative)}</span>
        </span>
      </div>
    </div>
  );
}
