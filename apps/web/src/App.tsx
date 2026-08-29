import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  cacheCurrent,
  getApiToken,
  readCachedCurrent,
  setApiToken,
  type CurrentResponse,
  type DaySummary,
  type Device,
  type HealthResponse,
  type InverterSummaryResponse,
  type PlaybackResponse,
  type ProductionHistoryResponse,
  type ProductionRange,
} from "./api";
import { DayChart, Overview, TodayEnergy } from "./components/Overview";
import { PowerFlow } from "./components/PowerFlow";
import { Heatmap } from "./components/Heatmap";
import { ProductionHistory } from "./components/ProductionHistory";
import "./styles.css";

type Theme = "light" | "dark";

function ageLabel(iso: string | null | undefined): string {
  if (!iso) return "unknown age";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms)) return "unknown age";
  const sec = Math.max(0, Math.round(ms / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  return `${hr}h ago`;
}

function metricValue(current: CurrentResponse | null, key: string): number | null {
  const point = current?.livedata?.[key];
  return point ? point.value : null;
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem("solar_monitor_theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [current, setCurrent] = useState<CurrentResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [daySummary, setDaySummary] = useState<DaySummary | null>(null);
  const [productionRange, setProductionRange] = useState<ProductionRange>("week");
  const [productionPeriod, setProductionPeriod] = useState<string | undefined>();
  const [panelRange, setPanelRange] = useState<ProductionRange>("week");
  const [productionHistory, setProductionHistory] = useState<ProductionHistoryResponse | null>(null);
  const [inverterSummary, setInverterSummary] = useState<InverterSummaryResponse | null>(null);
  const [playback, setPlayback] = useState<PlaybackResponse | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [history, setHistory] = useState<Array<{ time: string; value: number }>>([]);
  const [hours, setHours] = useState(24);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [csvBusy, setCsvBusy] = useState(false);
  const [tokenInput, setTokenInput] = useState(getApiToken());

  function changeProductionRange(range: ProductionRange) {
    setProductionRange(range);
    setProductionPeriod(undefined);
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("solar_monitor_theme", theme);
  }, [theme]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [h, c, d, hist, day, play, production, panels] = await Promise.all([
        api.health(),
        api.current(),
        api.devices(),
        api.history("pv_power_kw", hours),
        api.daySummary(),
        api.playback(24),
        api.productionHistory(productionRange, productionPeriod),
        api.inverterSummary(panelRange),
      ]);
      setHealth(h);
      setCurrent(c);
      cacheCurrent(c);
      setDevices(d.devices);
      setHistory(hist.points.map((p) => ({ time: p.time, value: p.value })));
      setDaySummary(day);
      setProductionHistory(production);
      setInverterSummary(panels);
      setPlayback(play);
      setError(null);
      setOffline(false);
    } catch (err) {
      const cached = readCachedCurrent();
      if (cached) {
        setCurrent(cached.data);
        setOffline(true);
      }
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setRefreshing(false);
    }
  }, [hours, panelRange, productionPeriod, productionRange]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const freshness = useMemo(() => {
    const latest =
      health?.latest_measurement_at ??
      current?.livedata?.pv_power_kw?.collected_at ??
      null;
    return ageLabel(latest);
  }, [health, current]);

  const healthTone =
    !health?.database_ok || health?.last_collector_run?.status === "error"
      ? "bad"
      : offline
        ? "warn"
        : "ok";

  async function onDownloadCsv() {
    setCsvBusy(true);
    setError(null);
    try {
      await api.downloadCsv(hours);
    } catch (err) {
      setError(err instanceof Error ? err.message : "CSV download failed");
    } finally {
      setCsvBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1 className="brand">Solar Monitor</h1>
          <p className="tagline">Local PVS6 · no cloud required</p>
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </header>

      {(error || offline) && (
        <div className={`banner${error && !offline ? " error" : ""}`}>
          {offline
            ? `Showing last known data (${freshness}). ${error ?? ""}`
            : error}
        </div>
      )}

      <section className="section">
        <div className="panel health-row">
          <span className="pill">
            <span className={`dot ${healthTone}`} />
            {health?.last_collector_run
              ? `Collector ${health.last_collector_run.status} (${health.last_collector_run.source})`
              : "Collector unknown"}
          </span>
          <span className="pill">Data {freshness}</span>
          <span className="pill">{health?.inverter_devices ?? "—"} inverters tracked</span>
          <button
            type="button"
            className="icon-btn"
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </section>

      <Overview
        pv={metricValue(current, "pv_power_kw")}
        load={metricValue(current, "site_load_power_kw")}
        net={metricValue(current, "net_power_kw")}
      />

      <TodayEnergy summary={daySummary} />

      <ProductionHistory
      data={productionHistory}
      range={productionRange}
      onRangeChange={changeProductionRange}
      period={productionPeriod}
      onPeriodChange={setProductionPeriod}
      />

      <PowerFlow
        pv={metricValue(current, "pv_power_kw")}
        load={metricValue(current, "site_load_power_kw")}
        net={metricValue(current, "net_power_kw")}
      />

      <section className="section">
        <div className="toolbar">
          {[24, 48, 168].map((h) => (
            <button
              key={h}
              type="button"
              className={hours === h ? "active" : undefined}
              onClick={() => setHours(h)}
            >
              {h === 168 ? "7d" : `${h}h`}
            </button>
          ))}
          <button type="button" className="button" disabled={csvBusy} onClick={() => void onDownloadCsv()}>
            {csvBusy ? "Downloading…" : "Download CSV"}
          </button>
        </div>
      </section>

      <DayChart points={history} hours={hours} />

      {current && (
        <Heatmap
          current={current}
          summary={inverterSummary}
          range={panelRange}
          onRangeChange={setPanelRange}
          devices={devices}
          onDevicesChange={setDevices}
        />
      )}

      <section className="settings">
        <h2>API token (optional)</h2>
        <p className="muted">
          Only needed if <code>API_AUTH_TOKEN</code> is set on the server. Stored in this browser only.
        </p>
        <input
          type="password"
          value={tokenInput}
          placeholder="Bearer token"
          onChange={(e) => setTokenInput(e.target.value)}
        />
        <button
          type="button"
          className="icon-btn"
          onClick={() => {
            setApiToken(tokenInput);
            void refresh();
          }}
        >
          Save token
        </button>
      </section>
    </div>
  );
}
