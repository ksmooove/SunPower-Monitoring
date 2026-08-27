import { useEffect, useMemo, useRef, useState } from "react";
import type { Device, PlaybackResponse } from "../api";

function powerStyle(powerKw: number | null, maxKw: number): { background: string; lightText: boolean } {
  if (powerKw == null || maxKw <= 0) {
    return { background: "color-mix(in srgb, var(--muted) 25%, transparent)", lightText: false };
  }
  const t = Math.max(0, Math.min(1, powerKw / maxKw));
  const low = [108, 54, 168];
  const mid = [46, 140, 160];
  const high = [46, 160, 90];
  const from = t < 0.5 ? low : mid;
  const to = t < 0.5 ? mid : high;
  const u = t < 0.5 ? t * 2 : (t - 0.5) * 2;
  const rgb = from.map((c, i) => Math.round(c + (to[i] - c) * u));
  const luminance = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
  return {
    background: `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`,
    lightText: luminance < 0.55,
  };
}

function defaultLayout(index: number, cols: number): { row: number; col: number } {
  return { row: Math.floor(index / cols), col: index % cols };
}

export function DayScrubber({
  playback,
  devices,
}: {
  playback: PlaybackResponse | null;
  devices: Device[];
}) {
  const cols = 11;
  const frames = playback?.frames ?? [];
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [playback?.start, playback?.frame_count]);

  useEffect(() => {
    if (!playing || frames.length < 2) return;
    timer.current = window.setInterval(() => {
      setIndex((i) => (i + 1) % frames.length);
    }, 280);
    return () => {
      if (timer.current != null) window.clearInterval(timer.current);
    };
  }, [playing, frames.length]);

  const frame = frames[index] ?? null;
  const maxKw = Math.max(playback?.max_kw ?? 0.05, 0.05);

  const layoutDevices = useMemo(() => {
    const inv = devices.filter((d) => d.device_type === "inverter");
    if (inv.length > 0) return inv;
    return (playback?.devices ?? []).map((d) => ({
      id: d.pvs_path_id,
      device_type: "inverter",
      pvs_path_id: d.pvs_path_id,
      model: null,
      name: d.name,
      rated_watts: 360,
      grid_row: d.grid_row,
      grid_col: d.grid_col,
      enabled: true,
      first_seen_at: "",
      last_seen_at: "",
    }));
  }, [devices, playback?.devices]);

  const placed = useMemo(() => {
    return layoutDevices.map((d, i) => {
      const fallback = defaultLayout(Number(d.pvs_path_id) || i, cols);
      const power = frame?.powers[d.pvs_path_id] ?? null;
      return {
        key: d.pvs_path_id,
        row: d.grid_row ?? fallback.row,
        col: d.grid_col ?? fallback.col,
        power,
      };
    });
  }, [layoutDevices, frame]);

  const rows = Math.max(4, ...placed.map((p) => p.row + 1), 4);

  return (
    <section className="section">
      <h2>Day scrubber</h2>
      <div className="panel">
        <p className="muted" style={{ marginTop: 0 }}>
          Replay today’s (or last-24h) per-panel power as a time-lapse. Drag the slider or press Play.
        </p>
        {frames.length < 2 ? (
          <p className="muted">
            Need at least two stored inverter samples to animate. Keep collecting — new frames appear
            each poll (~5 min).
          </p>
        ) : (
          <>
            <div className="scrubber-controls">
              <button
                type="button"
                className="icon-btn"
                onClick={() => setPlaying((p) => !p)}
              >
                {playing ? "Pause" : "Play"}
              </button>
              <input
                className="scrubber-range"
                type="range"
                min={0}
                max={frames.length - 1}
                value={index}
                onChange={(e) => {
                  setPlaying(false);
                  setIndex(Number(e.target.value));
                }}
              />
              <span className="muted scrubber-time">
                {frame ? new Date(frame.time).toLocaleString() : "—"} · frame {index + 1}/
                {frames.length}
              </span>
            </div>
            <div
              className="heatmap-grid"
              style={{ ["--cols" as string]: cols, gridTemplateRows: `repeat(${rows}, auto)` }}
            >
              {placed.map((p) => {
                const style = powerStyle(p.power, maxKw);
                const watts = p.power == null ? null : Math.round(p.power * 1000);
                return (
                  <div
                    key={p.key}
                    className={`cell${style.lightText ? " light-text" : ""}`}
                    style={{
                      gridRow: p.row + 1,
                      gridColumn: p.col + 1,
                      background: style.background,
                      cursor: "default",
                    }}
                    title={`${p.key}: ${watts == null ? "n/a" : `${watts} W`}`}
                  >
                    <span className="w">
                      {watts == null ? "—" : watts}
                      {watts != null ? <span className="unit"> W</span> : null}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="legend">
              <span>Low</span>
              <div className="legend-bar legend-bar-violet-green" aria-hidden />
              <span>High (W)</span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
