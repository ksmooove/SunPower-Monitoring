export type MetricPoint = {
  value: number;
  unit: string;
  time: string;
  collected_at: string;
  quality: string;
  source: string;
};

export type CurrentResponse = {
  site_id: string;
  livedata: Record<string, MetricPoint>;
  meters: Array<{
    pvs_path_id: string;
    name: string;
    model: string | null;
    last_seen_at: string;
    power_kw: number | null;
    power_time: string | null;
  }>;
  inverters: Array<{
    pvs_path_id: string;
    name: string;
    model: string | null;
    last_seen_at: string;
    power_kw: number | null;
    power_time: string | null;
    collected_at: string | null;
  }>;
  inverter_power_kw_sum: number;
};

export type HealthResponse = {
  status: string;
  database_ok: boolean;
  latest_measurement_at: string | null;
  inverter_devices: number;
  last_collector_run: {
    status: string;
    source: string;
    finished_at: string | null;
    meter_count: number | null;
    inverter_count: number | null;
    measurement_rows: number | null;
    message: string | null;
  } | null;
};

export type Device = {
  id: string;
  device_type: string;
  pvs_path_id: string;
  model: string | null;
  name: string | null;
  rated_watts: number | null;
  grid_row: number | null;
  grid_col: number | null;
  enabled: boolean;
  first_seen_at: string;
  last_seen_at: string;
};

export type HistoryResponse = {
  metric: string;
  start: string;
  end: string;
  count: number;
  points: Array<{
    time: string;
    value: number;
    unit: string;
    quality: string;
    source: string;
    device_type: string;
    pvs_path_id: string;
    name: string | null;
  }>;
};

const API_BASE = "/api";
const TOKEN_KEY = "solar_monitor_api_token";

export function getApiToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setApiToken(token: string): void {
  if (token.trim()) localStorage.setItem(TOKEN_KEY, token.trim());
  else localStorage.removeItem(TOKEN_KEY);
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = getApiToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export type DaySummary = {
  timezone: string;
  local_date: string;
  window_start: string;
  window_end: string;
  generated_kwh: number | null;
  peak_power_kw: number | null;
  generated_insufficient_samples: boolean;
  grid_kwh: number | null;
  grid_direction: "export" | "import" | "neutral" | null;
  grid_insufficient_samples: boolean;
  home_load_kwh: number | null;
  home_load_insufficient_samples: boolean;
  quality: string;
  method: string;
};

export type ProductionRange =
  | "day"
  | "week"
  | "month"
  | "year"
  | "all";

export type ProductionHistoryPoint = {
  date: string;
  generated_kwh: number | null;
  insufficient_samples?: boolean;
  sample_count?: number;
  first_at?: string | null;
  last_at?: string | null;
};

export type ProductionHistoryResponse = {
  range: ProductionRange;
  period?: string | null;
  timezone: string;
  bucket: "day" | "month" | "year";
  total_kwh: number;

  // Actual cumulative lifetime production reported by the PVS.
  // Only populated for the "all" range.
  lifetime_kwh: number | null;

  point_count: number;
  points: ProductionHistoryPoint[];
};

export type InverterSummaryResponse = {
  range: ProductionRange;
  period?: string | null;
  timezone: string;
  unit: "kWh";
  is_lifetime: boolean;
  start: string | null;
  end: string;
  values_kwh: Record<string, number | null>;
  max_kwh: number;
};

export type PlaybackResponse = {
  start: string;
  end: string;
  frame_count: number;
  max_kw: number;
  devices: Array<{
    pvs_path_id: string;
    name: string | null;
    grid_row: number | null;
    grid_col: number | null;
  }>;
  frames: Array<{ time: string; powers: Record<string, number> }>;
};

export const api = {
  health: () => apiFetch<HealthResponse>("/health"),
  current: () => apiFetch<CurrentResponse>("/v1/current"),
  devices: () => apiFetch<{ devices: Device[] }>("/v1/devices"),
  daySummary: () => apiFetch<DaySummary>("/v1/day-summary"),
  productionHistory: (range: ProductionRange, period?: string) =>
    apiFetch<ProductionHistoryResponse>(
      `/v1/production-history?range=${range}${period ? `&period=${encodeURIComponent(period)}` : ""}`,
    ),
  inverterSummary: (range: ProductionRange, period?: string) =>
    apiFetch<InverterSummaryResponse>(
      `/v1/inverter-summary?range=${range}${period ? `&period=${encodeURIComponent(period)}` : ""}`,
    ),
  playback: (hours = 24) => apiFetch<PlaybackResponse>(`/v1/playback?hours=${hours}`),
  history: (metric: string, hours = 24) =>
    apiFetch<HistoryResponse>(
      `/v1/history?metric=${encodeURIComponent(metric)}&device_type=site&pvs_path_id=livedata&hours=${hours}`,
    ),
  updateLayout: (deviceId: string, body: { grid_row?: number; grid_col?: number; name?: string }) =>
    apiFetch<{ device: Device }>(`/v1/devices/${deviceId}/layout`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  async downloadCsv(hours = 24): Promise<void> {
    const path = `/v1/export.csv?metric=pv_power_kw&device_type=site&pvs_path_id=livedata&hours=${hours}`;
    const headers = new Headers();
    const token = getApiToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API_BASE}${path}`, { headers, cache: "no-store" });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status} ${res.statusText}: ${text}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `solar-export-${hours}h.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

const CACHE_KEY = "solar_monitor_last_current";

export function cacheCurrent(data: CurrentResponse): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), data }));
  } catch {
    /* ignore quota */
  }
}

export function readCachedCurrent(): { savedAt: number; data: CurrentResponse } | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as { savedAt: number; data: CurrentResponse };
  } catch {
    return null;
  }
}
