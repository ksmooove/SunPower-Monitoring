import { useEffect, useMemo, useState } from "react";
import type { CurrentResponse, Device, InverterSummaryResponse, ProductionRange } from "../api";
import { api } from "../api";

/** Violet (low) → green (high); returns background and whether text should be light. */
function energyStyle(energyKwh: number | null, maxKwh: number): { background: string; lightText: boolean } {
  if (energyKwh == null || maxKwh <= 0) {
    return { background: "color-mix(in srgb, var(--muted) 25%, transparent)", lightText: false };
  }
  const t = Math.max(0, Math.min(1, energyKwh / maxKwh));
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
  summary,
  range,
  onRangeChange,
  devices,
  onDevicesChange,
}: {
  current: CurrentResponse;
  summary: InverterSummaryResponse | null;
  range: ProductionRange;
  onRangeChange: (range: ProductionRange) => void;
  devices: Device[];
  onDevicesChange: (devices: Device[]) => void;
}) {
  const cols = 11;
  const inverters = useMemo(
    () => devices.filter((d) => d.device_type === "inverter"),
    [devices],
  );

  const maxKwh = Math.max(summary?.max_kwh ?? 0, 0.01);

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
        energyKwh: summary?.values_kwh[d.pvs_path_id] ?? null,
      };
    });
  }, [inverters, summary]);

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

  const subtitle = summary
    ? summary.is_lifetime
      ? `Lifetime energy generated · ${summary.timezone}`
      : `Energy generated · ${summary.timezone}`
    : "Loading panel history…";

  return (
    <section className="section">
      <div className="production-header">
        <div>
          <h2>Panel heatmap</h2>
          <p className="muted production-subtitle">{subtitle}</p>
        </div>
        <div className="production-tabs">
          {(["day", "week", "month", "year", "all"] as ProductionRange[]).map((key) => (
            <button
              key={key}
              type="button"
              className={range === key ? "production-tab active" : "production-tab"}
              onClick={() => onRangeChange(key)}
            >
              {key === "all" ? "All" : key[0].toUpperCase() + key.slice(1)}
            </button>
          ))}
        </div>
      </div>
      <div className="panel">
        <p className="muted" style={{ marginTop: 0 }}>
          Violet = low energy, green = high. Values are kilowatt-hours (kWh) generated over the
          selected range. Tap a panel to rename or move it — physical roof layout is user-editable
          (not available via owner local API).
        </p>
        <div
          className="heatmap-grid"
          style={{ ["--cols" as string]: cols, gridTemplateRows: `repeat(${rows}, auto)` }}
        >
          {placed.map((p) => {
            const style = energyStyle(p.energyKwh, maxKwh);
            const kwh = p.energyKwh == null ? null : p.energyKwh.toFixed(2);
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
                  kwh == null ? "n/a" : `${kwh} kWh`
                }`}
              >
                <span className="w">
                  {kwh == null ? "—" : kwh}
                  {kwh