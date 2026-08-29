import { useMemo, useState } from "react";
import type { DaySummary } from "../api";

type Point = { time: string; value: number };

function formatKw(n: number): string {
  return `${n.toFixed(2)} kW`;
}

function formatKwh(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(2)} kWh`;
}

export function TodaysProduction({
  summary,
  pv,
  points,
}: {
  summary: DaySummary | null;
  pv: number | null;
  points: Point[];
}) {
  return (
    <section className="section">
      <h2>Today's Production</h2>
      <div className="flow">
        <article className="stat solar">
          <div className="label">Generated</div>
          <div className="value">
            {summary?.generated_insufficient_samples ? "…" : formatKwh(summary?.generated_kwh)}
          </div>
          <div className="meta">Today</div>
        </article>
        <article className="stat solar">
          <div className="label">Current Solar</div>
          <div className="value">{pv == null ? "—" : formatKw(pv)}</div>
          <div className="meta">Live output</div>
        </article>
        <article className="stat solar">
          <div className="label">Peak Power</div>
          <div className="value">{summary?.peak_power_kw == null ? "—" : formatKw(summary.peak_power_kw)}</div>
          <div className="meta">Highest today</div>
        </article>
      </div>
      <DayChart points={points} />
    </section>
  );
}

export function DayChart({
  points,
}: {
  points: Point[];
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  const { maxY, bars } = useMemo(() => {
    if (points.length === 0) {
      return { maxY: 1, bars: [] as Array<{ x: number; y: number; width: number; height: number }> };
    }
    const values = points.map((p) => p.value);
    const maxY = Math.max(...values, 0.1);
    const first = new Date(points[0].time);
    const dayStart = new Date(first.getFullYear(), first.getMonth(), first.getDate()).getTime();
    const w = 720;
    const plotLeft = 44;
    const plotRight = 704;
    const plotTop = 24;
    const plotBottom = 232;
    const plotWidth = plotRight - plotLeft;
    const bars = points.map((point) => {
      const fraction = Math.max(0, Math.min(1, (new Date(point.time).getTime() - dayStart) / 86_400_000));
      const x = plotLeft + fraction * plotWidth;
      const height = (point.value / maxY) * (plotBottom - plotTop);
      return { x: x - 2, y: plotBottom - height, width: 4, height };
    });
    return { maxY, bars };
  }, [points]);

  return (
    <div className="panel chart-wrap">
        {points.length === 0 ? (
          <p className="muted">
            No solar production samples have been collected today.
          </p>
        ) : (
          <svg
            viewBox="0 0 720 280"
            role="img"
            aria-label="Solar production over today's calendar day"
            onMouseLeave={() => setHovered(null)}
          >
            {[0, 6, 12, 18, 24].map((hour) => {
              const x = 44 + (hour / 24) * 660;
              return (
                <g key={hour}>
                  <line x1={x} y1="24" x2={x} y2="232" stroke="var(--line)" strokeDasharray="3 5" />
                  <text x={x} y="258" fill="var(--muted)" fontSize="12" textAnchor={hour === 0 ? "start" : hour === 24 ? "end" : "middle"}>
                    {hour === 0 || hour === 24 ? "12 AM" : hour === 12 ? "12 PM" : `${hour > 12 ? hour - 12 : hour} ${hour > 12 ? "PM" : "AM"}`}
                  </text>
                </g>
              );
            })}
            <text x="44" y="16" fill="var(--muted)" fontSize="12">
              max {maxY.toFixed(2)} kW
            </text>
            {bars.map((bar, index) => (
              <rect
                key={points[index].time}
                x={bar.x}
                y={bar.y}
                width={bar.width}
                height={bar.height}
                rx="1"
                fill="var(--accent)"
                opacity={hovered === index ? 1 : 0.82}
                onMouseEnter={() => setHovered(index)}
              />
            ))}
          </svg>
        )}
        {hovered != null && points[hovered] && (
          <div className="chart-tooltip">
            <strong>{formatKw(points[hovered].value)}</strong>
            <span>{new Date(points[hovered].time).toLocaleString()}</span>
          </div>
        )}
    </div>
  );
}
