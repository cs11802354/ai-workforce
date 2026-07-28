import { useEffect, useRef, useState } from "react";

export type Point = { label: string; value: number };

type Props = {
  data: Point[];
  /** Series name — used by the tooltip and the table caption. */
  series: string;
  /** Formats a value for display (axis ticks, tooltip, table). */
  format?: (v: number) => string;
  height?: number;
};

const PAD = { top: 16, right: 18, bottom: 28, left: 46 };

/** Clean, human y-axis ceiling: 1/2/5 x 10^n at or above the data max. */
function niceCeiling(max: number): number {
  if (max <= 0) return 1;
  const exp = Math.floor(Math.log10(max));
  const pow = Math.pow(10, exp);
  const norm = max / pow;
  const step = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
  return step * pow;
}

export function AreaChart({ data, series, format = (v) => String(v), height = 260 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  const [active, setActive] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const innerW = Math.max(width - PAD.left - PAD.right, 10);
  const innerH = height - PAD.top - PAD.bottom;
  const maxValue = niceCeiling(Math.max(...data.map((d) => d.value), 0));
  const stepX = data.length > 1 ? innerW / (data.length - 1) : 0;

  const x = (i: number) => PAD.left + i * stepX;
  const y = (v: number) => PAD.top + innerH - (v / maxValue) * innerH;

  const linePath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.value)}`).join(" ");
  const areaPath =
    data.length > 0
      ? `${linePath} L${x(data.length - 1)},${PAD.top + innerH} L${x(0)},${PAD.top + innerH} Z`
      : "";

  const ticks = [0, 0.5, 1].map((f) => Math.round(maxValue * f * 100) / 100);
  const last = data.length - 1;

  function handleMove(e: React.PointerEvent<SVGSVGElement>) {
    if (data.length === 0 || stepX === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = e.clientX - rect.left - PAD.left;
    const i = Math.round(rel / stepX);
    setActive(Math.min(Math.max(i, 0), data.length - 1));
  }

  const activePoint = active !== null ? data[active] : null;

  return (
    <div className="chart" ref={wrapRef}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`${series} over time`}
        onPointerMove={handleMove}
        onPointerLeave={() => setActive(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={PAD.left} x2={PAD.left + innerW} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={PAD.left - 10} y={y(t)} textAnchor="end" dominantBaseline="middle">
              {format(t)}
            </text>
          </g>
        ))}

        {data.map((d, i) =>
          i % Math.ceil(data.length / 7) === 0 || i === last ? (
            <text key={d.label} className="chart-axis" x={x(i)} y={height - 8} textAnchor="middle">
              {d.label}
            </text>
          ) : null
        )}

        {areaPath && <path className="chart-area" d={areaPath} />}
        {linePath && <path className="chart-line" d={linePath} />}

        {active !== null && (
          <line className="chart-crosshair" x1={x(active)} x2={x(active)} y1={PAD.top} y2={PAD.top + innerH} />
        )}

        {last >= 0 && (
          <circle className="chart-dot" cx={x(last)} cy={y(data[last].value)} r={4.5} />
        )}
        {active !== null && active !== last && (
          <circle className="chart-dot" cx={x(active)} cy={y(data[active].value)} r={4.5} />
        )}
      </svg>

      {activePoint && (
        <div
          className="chart-tooltip"
          style={{
            left: Math.min(Math.max(x(active!), 70), width - 70),
            top: y(activePoint.value) - 8,
          }}
        >
          <span className="chart-tooltip-value">{format(activePoint.value)}</span>
          <span className="chart-tooltip-meta">
            <span className="chart-key" />
            {series} · {activePoint.label}
          </span>
        </div>
      )}

      <button className="chart-table-toggle" onClick={() => setShowTable((s) => !s)}>
        {showTable ? "Hide data table" : "View as table"}
      </button>

      {showTable && (
        <table className="chart-table">
          <caption>{series} by day</caption>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">{series}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.label}>
                <th scope="row">{d.label}</th>
                <td>{format(d.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
