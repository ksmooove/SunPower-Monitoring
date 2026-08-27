import { useMemo } from "react";

function formatKw(n: number): string {
  if (n < 0.005) return "0 kW";
  if (n < 1) return `${(n * 1000).toFixed(0)} W`;
  return `${n.toFixed(2)} kW`;
}

const SOLAR_COLOR = "#e08a1a";
const SOLAR_CORE = "#ffc14d";
/** Vibrant grass green — same for export and import; direction is arrow + dash motion. */
const GRID_COLOR = "#3cb043";
const GRID_CORE = "#7dff7a";

type FlowEdge = {
  id: string;
  d: string;
  kw: number;
  color: string;
  core: string;
  durationSec: number;
  /** Arrow tip in viewBox coords + rotation (deg) along flow direction. */
  tip: { x: number; y: number; rotate: number };
};

function TechArrowhead({
  x,
  y,
  rotate,
  color,
  core,
}: {
  x: number;
  y: number;
  rotate: number;
  color: string;
  core: string;
}) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${rotate})`} filter="url(#flow-glow)">
      {/* Soft bloom behind tip */}
      <ellipse cx={-4} cy={0} rx={32} ry={22} fill={color} opacity={0.22} />
      {/* Outer chevron wing */}
      <path
        d="M -28 -24 L 32 0 L -28 24 L -14 0 Z"
        fill={color}
        opacity={0.95}
      />
      {/* Inner core dart */}
      <path d="M -18 -12 L 22 0 L -18 12 L -8 0 Z" fill={core} />
      {/* Tech notch / energy bar */}
      <path
        d="M -36 -7 H -20 M -36 0 H -16 M -36 7 H -20"
        fill="none"
        stroke={core}
        strokeWidth={3.5}
        strokeLinecap="round"
        opacity={0.9}
      />
    </g>
  );
}

/**
 * Live power flow over the landscape house scene (web).
 * Portrait scene kept at /images/power-flow-scene-portrait.jpg for a future mobile app.
 * Sign convention: net < 0 ≈ export to grid.
 */
export function PowerFlow({
  pv,
  load,
  net,
}: {
  pv: number | null;
  load: number | null;
  net: number | null;
}) {
  const model = useMemo(() => {
    if (pv == null && load == null && net == null) return null;
    const solar = Math.max(0, pv ?? 0);
    const home = Math.max(0, load ?? 0);
    const gridAbs = Math.abs(net ?? 0);
    const exporting = (net ?? 0) < -0.005;
    const importing = (net ?? 0) > 0.005;

    let solarToHome = 0;
    let solarToGrid = 0;
    let gridToHome = 0;

    if (exporting) {
      solarToHome = Math.min(solar, home);
      solarToGrid = Math.max(gridAbs, Math.max(0, solar - solarToHome));
    } else if (importing) {
      solarToHome = Math.min(solar, home);
      gridToHome = Math.max(gridAbs, Math.max(0, home - solarToHome));
    } else {
      solarToHome = Math.min(solar, home);
    }

    const maxKw = Math.max(solar, home, gridAbs, 0.05);
    const durationFor = (kw: number) =>
      Math.max(0.45, Math.min(1.8, 1.35 / Math.sqrt(kw + 0.08)));

    // Circular pair: upper sun→roof, lower house↔pole.
    // Solar starts clear of the sun disc + rays (not touching); roof ≈ (705, 350); pole ≈ (1175, 640).
    const solarArc = "M 1125 175 Q 880 45, 705 350";
    const exportArc = "M 790 545 Q 1010 800, 1175 640";
    const importArc = "M 1175 640 Q 1010 800, 790 545";

    const edges: FlowEdge[] = [];
    if (solar > 0.005) {
      edges.push({
        id: "solar-home",
        d: solarArc,
        kw: Math.max(solarToHome, solar),
        color: SOLAR_COLOR,
        core: SOLAR_CORE,
        durationSec: durationFor(solar),
        // Tangent into roof from control (880,45)→(705,350)
        tip: { x: 705, y: 350, rotate: Math.atan2(305, -175) * (180 / Math.PI) },
      });
    }
    if (solarToGrid > 0.005) {
      edges.push({
        id: "home-grid",
        d: exportArc,
        kw: solarToGrid,
        color: GRID_COLOR,
        core: GRID_CORE,
        durationSec: durationFor(solarToGrid),
        tip: { x: 1175, y: 640, rotate: Math.atan2(-160, 165) * (180 / Math.PI) },
      });
    }
    if (gridToHome > 0.005) {
      edges.push({
        id: "grid-home",
        d: importArc,
        kw: gridToHome,
        color: GRID_COLOR,
        core: GRID_CORE,
        durationSec: durationFor(gridToHome),
        tip: { x: 790, y: 545, rotate: Math.atan2(-255, -220) * (180 / Math.PI) },
      });
    }

    return {
      solar,
      home,
      gridAbs,
      exporting,
      importing,
      edges,
      maxKw,
    };
  }, [pv, load, net]);

  return (
    <section className="section">
      <h2>Live energy flow</h2>
      <div className="panel power-flow-panel">
        <p className="muted" style={{ marginTop: 0 }}>
          Instantaneous power between solar, home, and grid. Dashes and arrows move with the flow.
        </p>
        {!model ? (
          <p className="muted">Waiting for live power readings…</p>
        ) : (
          <div className="power-flow-stage">
            <img
              className="power-flow-scene"
              src="/images/power-flow-scene-landscape.jpg"
              alt="Home energy flow scene"
              draggable={false}
            />
            <svg
              className="power-flow-overlay"
              viewBox="0 0 1350 900"
              role="img"
              aria-label="Animated live power flow between solar, home, and grid"
            >
              <defs>
                <filter id="flow-glow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="2.2" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter id="flow-line-glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3.5" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                {/* Hide dash animation under the larger arrow tip */}
                <mask id="mask-solar-home" maskUnits="userSpaceOnUse">
                  <rect x="0" y="0" width="1350" height="900" fill="white" />
                  <circle cx="705" cy="350" r="52" fill="black" />
                </mask>
                <mask id="mask-home-grid" maskUnits="userSpaceOnUse">
                  <rect x="0" y="0" width="1350" height="900" fill="white" />
                  <circle cx="1175" cy="640" r="52" fill="black" />
                </mask>
                <mask id="mask-grid-home" maskUnits="userSpaceOnUse">
                  <rect x="0" y="0" width="1350" height="900" fill="white" />
                  <circle cx="790" cy="545" r="52" fill="black" />
                </mask>
              </defs>

              {model.edges.map((e) => {
                const width = 13 + (e.kw / model.maxKw) * 22;
                const maskId = `mask-${e.id}`;
                return (
                  <g key={e.id}>
                    {/* Soft outer glow ribbon */}
                    <path
                      d={e.d}
                      fill="none"
                      stroke={e.color}
                      strokeLinecap="round"
                      opacity={0.28}
                      strokeWidth={width + 10}
                      filter="url(#flow-line-glow)"
                    />
                    {/* Mid body */}
                    <path
                      d={e.d}
                      fill="none"
                      stroke={e.color}
                      strokeLinecap="round"
                      opacity={0.35}
                      strokeWidth={width}
                    />
                    {/* Animated tech dashes (masked clear of the tip) */}
                    <path
                      className="flow-dash"
                      d={e.d}
                      fill="none"
                      stroke={e.core}
                      strokeLinecap="butt"
                      strokeLinejoin="round"
                      strokeWidth={width * 0.55}
                      mask={`url(#${maskId})`}
                      style={{ animationDuration: `${e.durationSec}s` }}
                    >
                      <animate
                        attributeName="stroke-dashoffset"
                        from="0"
                        to="-72"
                        dur={`${e.durationSec}s`}
                        repeatCount="indefinite"
                      />
                    </path>
                    {/* Secondary slower outer dash for depth */}
                    <path
                      className="flow-dash flow-dash-outer"
                      d={e.d}
                      fill="none"
                      stroke={e.color}
                      strokeLinecap="butt"
                      strokeWidth={width * 0.9}
                      opacity={0.55}
                      mask={`url(#${maskId})`}
                      style={{ animationDuration: `${e.durationSec * 1.35}s` }}
                    />
                    <TechArrowhead
                      x={e.tip.x}
                      y={e.tip.y}
                      rotate={e.tip.rotate}
                      color={e.color}
                      core={e.core}
                    />
                    <title>
                      {e.id.replace("-", " → ")}: {formatKw(e.kw)}
                    </title>
                  </g>
                );
              })}
            </svg>

            <div className="flow-badge flow-badge-solar">
              <span className="flow-badge-title">Solar production</span>
              <span className="flow-badge-value solar">{formatKw(model.solar)}</span>
            </div>
            <div className="flow-badge flow-badge-home">
              <span className="flow-badge-title">Home usage</span>
              <span className="flow-badge-value home">{formatKw(model.home)}</span>
            </div>
            <div
              className={`flow-badge flow-badge-grid${
                model.exporting ? " export" : model.importing ? " import" : ""
              }`}
            >
              <span className="flow-badge-title">
                {model.exporting
                  ? "Grid export"
                  : model.importing
                    ? "Grid import"
                    : "Grid"}
              </span>
              <span className="flow-badge-value">{formatKw(model.gridAbs)}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
