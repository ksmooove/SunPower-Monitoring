import { useEffect, useMemo, useState } from "react";
import type { CurrentResponse, Device } from "../api";
import { api } from "../api";

/** Violet (low) → green (high); returns background and whether text should be light. */
function powerStyle(powerKw: number | null, maxKw: number): { background: string; lightText: boolean } {
  if (powerKw == null || maxKw <= 0) {
    return { background: "color-mix(in srgb, var(--muted) 25%, transparent)", lightText: false };
  }
  const t = Math.max(0, Math.min(1, powerKw / maxKw));
  const low = [108, 54, 168]; // violet
  const mid = [46, 140, 160]; // teal bridge
  const high = [46, 160, 90]; // green
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

export function Heatmap({
  current,
  devices,
  onDevicesChange,
}: {
  current: CurrentResponse;
  devices: Device[];
  onDevicesChange: (devices: Device[]) => void;
}) {
  const cols = 11;
  const inverters = useMemo(
    () => devices.filter((d) => d.device_type === "inverter"),
    [devices],
  );
  const powerByPath = useMemo(() => {
    const m = new Map<string, number | null>();
    for (const inv of current.inverters) m.set(inv.pvs_path_id, inv.power_kw);
    return m;
  }, [current.inverters]);

  const maxKw = useMemo(() => {
    const vals = current.inverters.map((i) => i.power_kw ?? 0);
    return Math.max(...vals, 0.05);
  }, [current.inverters]);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = inverters.find((d) => d.id === selectedId) ?? null;
  const [row, setRow] = useState(0);
  const [col, setCol] = useState(0);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selected) return;
    const idx = Number(selected.pvs_path_id);
    const fallback = defaultLayout(Number.isFinite(idx) ? idx : 0, cols);
    setRow(selected.grid_row ?? fallback.row);
    setCol(selected.grid_col ?? fallback.col);
    setName(selected.name ?? `Inverter ${selected.pvs_path_id}`);
  }, [selected]);

  const placed = useMemo(() => {
    return inverters.map((d, i) => {
      const fallback = defaultLayout(Number(d.pvs_path_id) || i, cols);
      return {
        device: d,
        row: d.grid_row ?? fallback.row,
        col: d.grid_col ?? fallback.col,
        power: powerByPath.get(d.pvs_path_id) ?? null,
      };
    });
  }, [inverters, powerByPath]);

  const rows = Math.max(4, ...placed.map((p) => p.row + 1));

  async function saveLayout() {
    if (!selected) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await api.updateLayout(selected.id, {
        grid_row: row,
        grid_col: col,
        name: name.trim() || undefined,
      });
      onDevicesChange(devices.map((d) => (d.id === res.device.id ? res.device : d)));
      setMessage("Layout saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="section">
      <h2>Panel heatmap</h2>
      <div className="panel">
        <p className="muted" style={{ marginTop: 0 }}>
          Violet = low power, green = high. Values are watts (W). Tap a panel to rename or move it —
          physical roof layout is user-editable (not available via owner local API).
        </p>
        <div
          className="heatmap-grid"
          style={{ ["--cols" as string]: cols, gridTemplateRows: `repeat(${rows}, auto)` }}
        >
          {placed.map((p) => {
            const style = powerStyle(p.power, maxKw);
            const watts = p.power == null ? null : Math.round(p.power * 1000);
            return (
              <button
                key={p.device.id}
                type="button"
                className={`cell${selectedId === p.device.id ? " selected" : ""}${
                  style.lightText ? " light-text" : ""
                }`}
                style={{
                  gridRow: p.row + 1,
                  gridColumn: p.col + 1,
                  background: style.background,
                }}
                onClick={() => setSelectedId(p.device.id)}
                title={`${p.device.name ?? p.device.pvs_path_id}: ${
                  watts == null ? "n/a" : `${watts} W`
                }`}
              >
                <span className="w">
                  {watts == null ? "—" : watts}
                  {watts != null ? <span className="unit"> W</span> : null}
                </span>
              </button>
            );
          })}
        </div>
        <div className="legend">
          <span>Low</span>
          <div className="legend-bar legend-bar-violet-green" aria-hidden />
          <span>High (W)</span>
        </div>

        {selected && (
          <div className="detail">
            <strong>{selected.name ?? `Inverter ${selected.pvs_path_id}`}</strong>
            <span className="muted">
              Path {selected.pvs_path_id}
              {selected.model ? ` · ${selected.model}` : ""} · last seen{" "}
              {new Date(selected.last_seen_at).toLocaleString()}
            </span>
            <div className="layout-controls">
              <label>
                Name
                <input value={name} onChange={(e) => setName(e.target.value)} style={{ width: "12rem" }} />
              </label>
              <label>
                Row
                <input
                  type="number"
                  min={0}
                  max={50}
                  value={row}
                  onChange={(e) => setRow(Number(e.target.value))}
                />
              </label>
              <label>
                Col
                <input
                  type="number"
                  min={0}
                  max={50}
                  value={col}
                  onChange={(e) => setCol(Number(e.target.value))}
                />
              </label>
              <button type="button" className="icon-btn" disabled={saving} onClick={() => void saveLayout()}>
                {saving ? "Saving…" : "Save layout"}
              </button>
            </div>
            {message && <span className="muted">{message}</span>}
          </div>
        )}
      </div>
    </section>
  );
}
