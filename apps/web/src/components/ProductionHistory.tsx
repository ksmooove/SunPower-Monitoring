import { useMemo } from "react";
import type {
  ProductionHistoryResponse,
  ProductionRange,
} from "../api";

const RANGE_LABELS: Record<ProductionRange, string> = {
  day: "Day",
  week: "Week",
  month: "Month",
  year: "Year",
  all: "All",
};

function formatKwh(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)} MWh`;
  }

  return `${value.toFixed(2)} kWh`;
}

function formatPointLabel(
  value: string,
  bucket: "day" | "month" | "year",
): string {
  if (bucket === "year") {
    return value;
  }

  if (bucket === "month") {
    const [year, month] = value.split("-");
    const date = new Date(
      Number(year),
      Number(month) - 1,
      1,
    );

    return date.toLocaleDateString([], {
      month: "short",
    });
  }

  const [year, month, day] = value.split("-");
  const date = new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
  );

  return date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

export function ProductionHistory({
  data,
  range,
  onRangeChange,
}: {
  data: ProductionHistoryResponse | null;
  range: ProductionRange;
  onRangeChange: (range: ProductionRange) => void;
}) {
  const maxKwh = useMemo(() => {
    if (!data?.points.length) return 1;

    return Math.max(
      ...data.points.map(
        (point) => point.generated_kwh ?? 0,
      ),
      0.1,
    );
  }, [data]);

  const title =
    range === "day"
      ? "Today's production"
      : range === "week"
        ? "Daily production — last 7 days"
        : range === "month"
          ? "Daily production — this month"
          : range === "year"
            ? "Monthly production — this year"
            : "Lifetime production";

  return (
    <section className="section">
      <div className="production-header">
        <div>
          <h2>Production</h2>
          <p className="muted production-subtitle">
            {title}
          </p>
        </div>

        <div className="production-tabs">
          {(Object.keys(RANGE_LABELS) as ProductionRange[]).map(
            (key) => (
              <button
                key={key}
                type="button"
                className={
                  range === key
                    ? "production-tab active"
                    : "production-tab"
                }
                onClick={() => onRangeChange(key)}
              >
                {RANGE_LABELS[key]}
              </button>
            ),
          )}
        </div>
      </div>

      <div className="panel production-history-panel">
        <div className="production-total">
          <span className="production-total-label">
            {range === "all"
              ? "Lifetime generated"
              : range === "year"
                ? "Generated this year"
                : range === "month"
                  ? "Generated this month"
                  : range === "week"
                    ? "Generated in this period"
                    : "Generated today"}
          </span>

          <strong>
           {!data
            ? "—"
            : range === "all" && data.lifetime_kwh != null
            ? formatKwh(data.lifetime_kwh)
            : formatKwh(data.total_kwh)}
          </strong>
        </div>

        {!data ? (
          <p className="muted">
            Loading production history…
          </p>
        ) : data.points.length === 0 ? (
          <p className="muted">
            No production history has been collected yet.
          </p>
        ) : (
          <>
            <div className="production-bars">
              {data.points.map((point) => {
                const value =
                  point.generated_kwh ?? 0;

                const height =
                  value > 0
                    ? Math.max(
                        3,
                        (value / maxKwh) * 100,
                      )
                    : 0;

                const label = formatPointLabel(
                  point.date,
                  data.bucket,
                );

                return (
                  <div
                    key={point.date}
                    className="production-bar-column"
                    title={`${label}: ${
                      point.generated_kwh == null
                        ? "Not enough samples"
                        : formatKwh(
                            point.generated_kwh,
                          )
                    }`}
                  >
                    <div className="production-bar-value">
                      {point.generated_kwh == null
                        ? "—"
                        : point.generated_kwh >= 100
                          ? point.generated_kwh.toFixed(0)
                          : point.generated_kwh.toFixed(1)}
                    </div>

                    <div className="production-bar-track">
                      <div
                        className="production-bar"
                        style={{
                          height: `${height}%`,
                        }}
                      />
                    </div>

                    <div className="production-bar-label">
                      {label}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="production-unit">
              Values are kWh
              {data.timezone
                ? ` · ${data.timezone}`
                : ""}
            </div>
          </>
        )}
      </div>
    </section>
  );
}