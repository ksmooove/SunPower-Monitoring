import { useMemo } from "react";
import type { DaySummary } from "../api";

type Point = { time: string; value: number };

function formatKw(n: number): string {
  return `${n.toFixed(2)} kW`;
}

function formatKwh(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(2)} kWh`;
}

export function Overview({
  pv,
  load,
  net,
}: {
  pv: number | null;
  load: number | null;
  net: number | null;
}) {
  const gridMode = net == null ? "unknown" : net < 0 ? "export" : "import";
  const gridAbs = net == null ? null : Math.abs(net);

  return (
    <section className="section">
      <h2>Live power</h2>
      <div className="flow">
        <article className="stat solar">
          <div className="label">Solar</div>
          <div className="value">{pv == null ? "—" : formatKw(pv)}</div>
          <div className="meta">Measured production</div>
        </article>
        <article className="stat load">
          <div className="label">Home</div>
          <div className="value">{load == null ? "—" : formatKw(load)}</div>
          <div className="meta">Site load</div>
        </article>
        <article className={`stat grid ${gridMode}`}>
          <div className="label">Grid</div>
          <div className="value">{gridAbs == null ? "—" : formatKw(gridAbs)}</div>
          <div className="meta">
            {gridMode === "export" ? "Exporting" : gridMode === "import" ? "Importing" : "Net flow"}
          </div>
        </article>
      </div>
    </section>
  );
}

export function TodayEnergy({ summary }: { summary: DaySummary | null }) {
  const gridLabel =
    summary?.grid_direction === "export"
      ? "Exported to grid"
      : summary?.grid_direction === "import"
        ? "Imported from grid"
        : "Grid net";

  return (
    <section className="section">
      <h2>Today ({summary?.local_date ?? "…"})</h2>
      <div className="flow">
        <article className="stat solar">
          <div className="label">Generated</div>
          <div className="value">
            {summary?.generated_insufficient_samples
              ? "…"
              : formatKwh(summary?.generated_kwh)}
          </div>
          <div className="meta">
            Calendar day · {summary?.timezone ?? "America/Los_Angeles"} · measured delta
          </div>
        </article>
        <article
          className={`stat grid ${
            summary?.grid_direction === "export"
              ? "export"
              : summary?.grid_direction === "import"
                ? "import"
                : ""
          }`}
        >
          <div className="label">{gridLabel}</div>
          <div className="value">
            {summary?.grid_insufficient_samples
              ? "…"
              : formatKwh(summary?.grid_kwh)}
          </div>
          <div className="meta">
            {summary?.grid_direction === "export"
              ? "Net to utility today"
              : summary?.grid_direction === "import"
                ? "Net from utility today"
                : "Needs more samples today"}
          </div>
        </article>
        <article className="stat load">
          <div className="label">Home use</div>
          <div className="value">
            {summary?.home_load_insufficient_samples
              ? "…"
              : formatKwh(summary?.home_load_kwh)}
          </div>
          <div className="meta">Site load energy today</div>
        </article>
      </div>
    </section>
  );
}

export function DayChart({
  points,
  hours,
}: {
  points: Point[];
  hours: number;
}) {
  const { path, area, maxY, labels } = useMemo(() => {
    if (points.length === 0) {
      return { path: "", area: "", maxY: 1, labels: [] as string[] };
    }
    const values = points.map((p) => p.value);
    const maxY = Math.max(...values, 0.1);
    const w = 640;
    const h = 220;
    const pad = 16;
    const coords = points.map((p, i) => {
      const x = pad + (i / Math.max(points.length - 1, 1)) * (w - pad * 2);
      const y = h - pad - (p.value / maxY) * (h - pad * 2);
      return [x, y] as const;
    });
    const path = coords
      .map((c, i) => `${i === 0 ? "M" : "L"}${c[0].toFixed(1)},${c[1].toFixed(1)}`)
      .join(" ");
    const area = `${path} L${coords.at(-1)![0].toFixed(1)},${h - pad} L${coords[0][0].toFixed(1)},${h - pad} Z`;
    const fmt = (iso: string) => {
      const d = new Date(iso);
      if (hours > 48) {
        return d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric" });
      }
      return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    };
    const labels = [
      fmt(points[0].time),
      fmt(points[Math.floor(points.length / 2)].time),
      fmt(points.at(-1)!.time),
    ];
    return { path, area, maxY, labels };
  }, [points, hours]);

  const spanHours =
    points.length >= 2
      ? (new Date(points.at(-1)!.time).getTime() - new Date(points[0].time).getTime()) /
        3_600_000
      : 0;

  return (
    <section className="section">
      <h2>Production chart</h2>
      <div className="panel chart-wrap">
        <p className="muted" style={{ marginTop: 0 }}>
          Requested window: last {hours === 168 ? "7 days" : `${hours} hours`} · {points.length}{" "}
          point{points.length === 1 ? "" : "s"}
          {points.length >= 2
            ? ` · data spans ~${spanHours.toFixed(1)} h (chart only shows samples we have stored)`
            : ""}
        </p>
        {points.length < 2 ? (
          <p className="muted">
            Not enough history yet. The collector stores one sample every poll (~5 min). Longer
            ranges will look the same until more time has accumulated.
          </p>
        ) : (
          <svg viewBox="0 0 640 240" role="img" aria-label="Solar production over time">
            <defs>
              <linearGradient id="fillGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            <path d={area} fill="url(#fillGrad)" />
            <path
              d={path}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
            <text x="16" y="18" fill="var(--muted)" fontSize="12">
              max {maxY.toFixed(2)} kW
            </text>
            <text x="16" y="232" fill="var(--muted)" fontSize="12">
              {labels[0]}
            </text>
            <text x="300" y="232" fill="var(--muted)" fontSize="12" textAnchor="middle">
              {labels[1]}
            </text>
            <text x="624" y="232" fill="var(--muted)" fontSize="12" textAnchor="end">
              {labels[2]}
            </text>
          </svg>
        )}
      </div>
    </section>
  );
}
