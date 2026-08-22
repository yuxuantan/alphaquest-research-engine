import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
} from "react";

import { api } from "../api";
import { Icon } from "../components/Icons";
import {
  Button,
  Card,
  Notice,
  PageHeader,
  Skeleton,
  StatusBadge,
  formatDate,
  humanize,
} from "../components/UI";
import type { DatasetSummary } from "../types";

type Drawing = {
  type: "horizontal" | "trend";
  points: Array<{ index: number; price: number }>;
};

export function AnalysisPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [comparisonId, setComparisonId] = useState("");
  const [resolution, setResolution] = useState("native");
  const [chartType, setChartType] = useState("candlestick");
  const [chart, setChart] = useState<Record<string, any> | null>(null);
  const [scanner, setScanner] = useState<Record<string, any> | null>(null);
  const [capabilities, setCapabilities] = useState<Array<Record<string, string>>>([]);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError] = useState("");
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(250);
  const [indicators, setIndicators] = useState({
    sma20: true,
    ema20: false,
    vwap: true,
  });
  const [tool, setTool] = useState<"none" | "horizontal" | "trend">("none");
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const pendingTrend = useRef<Drawing | null>(null);

  useEffect(() => {
    Promise.all([
      api.libraries(),
      api.analysisCapabilities(),
      api.analysisScanner(),
    ])
      .then(([library, parity, scan]) => {
        setDatasets(library.datasets);
        const firstAvailable = scan.rows.find(
          (item) => item.status === "available",
        )?.dataset_id;
        setDatasetId(
          (old) =>
            old || firstAvailable || library.datasets[0]?.dataset_id || "",
        );
        setCapabilities(parity.capabilities);
        setScanner(scan);
      })
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : "Analysis workbench unavailable"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    setChartLoading(true);
    setError("");
    api
      .analysisChart(datasetId, {
        resolution,
        chart_type: chartType,
        limit: 800,
        compare_dataset_id: comparisonId || undefined,
      })
      .then((value) => {
        setChart(value);
        setPlayhead(Math.max(0, (value.bars || []).length - 1));
        setDrawings([]);
        pendingTrend.current = null;
      })
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : "Chart evidence unavailable"),
      )
      .finally(() => setChartLoading(false));
  }, [datasetId, comparisonId, resolution, chartType]);

  const bars = chart?.bars || [];
  useEffect(() => {
    if (!playing || !bars.length) return;
    const timer = window.setInterval(() => {
      setPlayhead((old) => {
        if (old >= bars.length - 1) {
          setPlaying(false);
          return old;
        }
        return old + 1;
      });
    }, speed);
    return () => window.clearInterval(timer);
  }, [playing, speed, bars.length]);

  const comparable = datasets.filter(
    (item) =>
      item.dataset_id !== datasetId &&
      item.symbol === datasets.find((candidate) => candidate.dataset_id === datasetId)?.symbol,
  );
  const activeBar = bars[Math.min(playhead, bars.length - 1)];
  return (
    <div className="page analysis-page">
      <PageHeader
        eyebrow="Governed market analysis"
        title="Analysis workbench"
        description="Inspect hash-verified datasets across resolutions, replay market history, compare sources, draw levels, and scan latest states. Nothing here can bypass campaign certification."
      />
      {error && <Notice tone="danger">{error}</Notice>}
      {loading ? (
        <Skeleton lines={10} />
      ) : (
        <>
          <Card className="analysis-controls">
            <label>
              <span>Dataset</span>
              <select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>
                {datasets.map((item) => (
                  <option value={item.dataset_id} key={item.dataset_id}>
                    {item.display_name || item.dataset_id} · {item.quality_verdict}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Resolution</span>
              <select value={resolution} onChange={(event) => setResolution(event.target.value)}>
                <option value="native">Native</option>
                <option value="5m">5 minutes</option>
                <option value="15m">15 minutes</option>
                <option value="30m">30 minutes</option>
                <option value="60m">60 minutes</option>
                <option value="1d">Daily</option>
              </select>
            </label>
            <label>
              <span>Chart type</span>
              <select value={chartType} onChange={(event) => setChartType(event.target.value)}>
                <option value="candlestick">Candlestick</option>
                <option value="hollow_candlestick">Hollow candlestick</option>
                <option value="ohlc">OHLC bars</option>
                <option value="line">Line on close</option>
                <option value="heikin_ashi">Heikin-Ashi</option>
                <option value="cumulative_delta">Cumulative delta</option>
              </select>
            </label>
            <label>
              <span>Compare source</span>
              <select value={comparisonId} onChange={(event) => setComparisonId(event.target.value)}>
                <option value="">No overlay</option>
                {comparable.map((item) => (
                  <option value={item.dataset_id} key={item.dataset_id}>
                    {item.display_name || item.dataset_id}
                  </option>
                ))}
              </select>
            </label>
          </Card>

          {chartLoading || !chart ? (
            <Card><Skeleton lines={8} /></Card>
          ) : (
            <>
              <div className="analysis-identity">
                <div>
                  <StatusBadge value={chart.dataset.quality_verdict} kind="scientific" />
                  <strong>
                    {chart.dataset.symbol} · {chart.view.resolution === "native" ? chart.dataset.native_timeframe : chart.view.resolution}
                  </strong>
                  <span>{chart.view.rows} loaded bars</span>
                </div>
                <code title={chart.dataset.canonical_sha256}>
                  SHA {String(chart.dataset.canonical_sha256).slice(0, 12)}
                </code>
              </div>
              <Notice tone="info" title="Inspection-only derivations">
                {chart.view.warning}
              </Notice>
              <Card className="market-chart-card">
                <div className="market-chart-toolbar">
                  <div>
                    <p className="eyebrow">Hash-verified chart</p>
                    <h2>{humanize(chartType)}</h2>
                  </div>
                  <div className="indicator-switches" aria-label="Chart indicators">
                    {Object.entries(indicators).map(([name, checked]) => (
                      <label key={name}>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(event) =>
                            setIndicators((old) => ({ ...old, [name]: event.target.checked }))
                          }
                        />
                        {name.toUpperCase()}
                      </label>
                    ))}
                  </div>
                  <div className="drawing-tools" aria-label="Drawing tools">
                    {(["none", "horizontal", "trend"] as const).map((name) => (
                      <button
                        type="button"
                        className={tool === name ? "selected" : ""}
                        onClick={() => {
                          setTool(name);
                          pendingTrend.current = null;
                        }}
                        key={name}
                      >
                        {name === "none" ? "Cursor" : humanize(name)}
                      </button>
                    ))}
                    <button type="button" onClick={() => setDrawings([])}>Clear</button>
                  </div>
                </div>
                <MarketChart
                  bars={bars}
                  comparison={chart.comparison?.rows || []}
                  playhead={playhead}
                  chartType={chartType}
                  indicators={indicators}
                  drawings={drawings}
                  onPoint={(point) => {
                    if (tool === "horizontal") {
                      setDrawings((old) => [...old, { type: "horizontal", points: [point] }]);
                    } else if (tool === "trend") {
                      if (!pendingTrend.current) {
                        pendingTrend.current = { type: "trend", points: [point] };
                      } else {
                        setDrawings((old) => [
                          ...old,
                          { type: "trend", points: [...pendingTrend.current!.points, point] },
                        ]);
                        pendingTrend.current = null;
                      }
                    }
                  }}
                />
                <div className="chart-data-window" aria-live="polite">
                  {activeBar ? (
                    <>
                      <strong>{formatDate(activeBar.timestamp)}</strong>
                      {["open", "high", "low", "close", "volume", "delta"].map((name) => (
                        <span key={name}>
                          {name.toUpperCase()} <b>{formatNumber(activeBar[name])}</b>
                        </span>
                      ))}
                    </>
                  ) : <span>No active bar</span>}
                </div>
                <Playback
                  length={bars.length}
                  value={playhead}
                  playing={playing}
                  speed={speed}
                  onChange={setPlayhead}
                  onPlaying={setPlaying}
                  onSpeed={setSpeed}
                />
              </Card>
            </>
          )}

          <ScannerTable scanner={scanner} onOpen={setDatasetId} />
          <ParityMatrix capabilities={capabilities} />
        </>
      )}
    </div>
  );
}

function MarketChart({
  bars,
  comparison,
  playhead,
  chartType,
  indicators,
  drawings,
  onPoint,
}: {
  bars: any[];
  comparison: any[];
  playhead: number;
  chartType: string;
  indicators: Record<string, boolean>;
  drawings: Drawing[];
  onPoint: (point: { index: number; price: number }) => void;
}) {
  const width = 1120;
  const height = 510;
  const pad = { left: 58, right: 20, top: 20, bottom: 92 };
  const visibleEnd = Math.min(playhead + 1, bars.length);
  const visibleStart = Math.max(0, visibleEnd - 160);
  const rows = bars.slice(visibleStart, visibleEnd);
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const deltaMode = chartType === "cumulative_delta";
  const keys = deltaMode
    ? ["cumulative_delta"]
    : ["low", "high", ...Object.keys(indicators).filter((name) => indicators[name])];
  const values = rows.flatMap((row) =>
    keys.map((key) => Number(row[key])).filter(Number.isFinite),
  );
  const low = values.length ? Math.min(...values) : 0;
  const high = values.length ? Math.max(...values) : 1;
  const spread = Math.max(high - low, 1e-9);
  const x = (index: number) =>
    pad.left + ((index - visibleStart + 0.5) * plotWidth) / Math.max(rows.length, 1);
  const y = (value: number) => pad.top + ((high - value) * plotHeight) / spread;
  const candleWidth = Math.max(2, Math.min(8, plotWidth / Math.max(rows.length, 1) - 2));
  const maxVolume = Math.max(...rows.map((row) => Number(row.volume) || 0), 1);
  const line = (key: string) =>
    rows
      .map((row, index) => {
        const value = Number(row[key]);
        return Number.isFinite(value) ? `${x(visibleStart + index)},${y(value)}` : null;
      })
      .filter(Boolean)
      .join(" ");
  const click = (event: MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const localX = ((event.clientX - rect.left) / rect.width) * width;
    const localY = ((event.clientY - rect.top) / rect.height) * height;
    if (
      localX < pad.left ||
      localX > width - pad.right ||
      localY < pad.top ||
      localY > height - pad.bottom
    ) return;
    const index = Math.max(
      visibleStart,
      Math.min(
        visibleEnd - 1,
        visibleStart + Math.floor(((localX - pad.left) / plotWidth) * rows.length),
      ),
    );
    const price = high - ((localY - pad.top) / plotHeight) * spread;
    onPoint({ index, price });
  };
  return (
    <svg
      className="market-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`${humanize(chartType)} market chart`}
      onClick={click}
    >
      <rect x={pad.left} y={pad.top} width={plotWidth} height={plotHeight} className="chart-plot" />
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const value = high - ratio * spread;
        return (
          <g key={ratio}>
            <line x1={pad.left} x2={width - pad.right} y1={y(value)} y2={y(value)} className="chart-gridline" />
            <text x={pad.left - 8} y={y(value) + 4} textAnchor="end">{formatNumber(value)}</text>
          </g>
        );
      })}
      {deltaMode ? (
        <polyline points={line("cumulative_delta")} className="chart-line chart-delta" />
      ) : chartType === "line" ? (
        <polyline points={line("close")} className="chart-line chart-close" />
      ) : (
        rows.map((row, offset) => {
          const index = visibleStart + offset;
          const open = Number(row.open);
          const close = Number(row.close);
          const rising = close >= open;
          if (chartType === "ohlc") {
            return (
              <g key={index} className={rising ? "candle-up" : "candle-down"}>
                <line x1={x(index)} x2={x(index)} y1={y(Number(row.high))} y2={y(Number(row.low))} />
                <line x1={x(index) - candleWidth / 2} x2={x(index)} y1={y(open)} y2={y(open)} />
                <line x1={x(index)} x2={x(index) + candleWidth / 2} y1={y(close)} y2={y(close)} />
              </g>
            );
          }
          return (
            <g key={index} className={rising ? "candle-up" : "candle-down"}>
              <line x1={x(index)} x2={x(index)} y1={y(Number(row.high))} y2={y(Number(row.low))} />
              <rect
                x={x(index) - candleWidth / 2}
                y={Math.min(y(open), y(close))}
                width={candleWidth}
                height={Math.max(1, Math.abs(y(open) - y(close)))}
                className={chartType === "hollow_candlestick" && rising ? "hollow" : ""}
              />
            </g>
          );
        })
      )}
      {!deltaMode && indicators.sma20 && <polyline points={line("sma20")} className="chart-line chart-sma" />}
      {!deltaMode && indicators.ema20 && <polyline points={line("ema20")} className="chart-line chart-ema" />}
      {!deltaMode && indicators.vwap && <polyline points={line("vwap")} className="chart-line chart-vwap" />}
      {!deltaMode && comparison.length > 0 && (
        <polyline
          points={rows
            .map((_, offset) => {
              const value = Number(comparison[visibleStart + offset]?.comparison_close);
              return Number.isFinite(value)
                ? `${x(visibleStart + offset)},${y(value)}`
                : null;
            })
            .filter(Boolean)
            .join(" ")}
          className="chart-line chart-comparison"
        />
      )}
      {drawings.map((drawing, index) => {
        const first = drawing.points[0];
        if (!first || first.index < visibleStart || first.index >= visibleEnd) return null;
        if (drawing.type === "horizontal")
          return (
            <g key={index} className="chart-drawing">
              <line x1={pad.left} x2={width - pad.right} y1={y(first.price)} y2={y(first.price)} />
              <text x={width - pad.right - 4} y={y(first.price) - 5} textAnchor="end">
                {formatNumber(first.price)}
              </text>
            </g>
          );
        const second = drawing.points[1];
        if (!second) return null;
        return (
          <g key={index} className="chart-drawing">
            <line x1={x(first.index)} x2={x(second.index)} y1={y(first.price)} y2={y(second.price)} />
            <text x={x(second.index)} y={y(second.price) - 7} textAnchor="end">
              Δ {formatNumber(second.price - first.price)}
            </text>
          </g>
        );
      })}
      {rows.map((row, offset) => {
        const index = visibleStart + offset;
        const volumeHeight = ((Number(row.volume) || 0) / maxVolume) * 58;
        return (
          <rect
            key={`volume-${index}`}
            x={x(index) - candleWidth / 2}
            y={height - 18 - volumeHeight}
            width={candleWidth}
            height={volumeHeight}
            className="chart-volume"
          />
        );
      })}
      <line x1={x(playhead)} x2={x(playhead)} y1={pad.top} y2={height - 18} className="chart-playhead" />
    </svg>
  );
}

function Playback({
  length,
  value,
  playing,
  speed,
  onChange,
  onPlaying,
  onSpeed,
}: {
  length: number;
  value: number;
  playing: boolean;
  speed: number;
  onChange: (value: number) => void;
  onPlaying: (value: boolean) => void;
  onSpeed: (value: number) => void;
}) {
  return (
    <div className="market-playback">
      <div>
        <Button variant="secondary" onClick={() => onChange(0)} disabled={!length || value === 0}>First</Button>
        <Button variant="secondary" onClick={() => onChange(Math.max(0, value - 1))} disabled={!length || value === 0}>Previous</Button>
        <Button onClick={() => onPlaying(!playing)} disabled={!length}>{playing ? "Pause" : "Play"}</Button>
        <Button variant="secondary" onClick={() => onChange(Math.min(length - 1, value + 1))} disabled={!length || value >= length - 1}>Next</Button>
      </div>
      <input
        aria-label="Market playback position"
        type="range"
        min="0"
        max={Math.max(0, length - 1)}
        value={Math.min(value, Math.max(0, length - 1))}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <label>
        <span>Speed</span>
        <select value={speed} onChange={(event) => onSpeed(Number(event.target.value))}>
          <option value="1000">1×</option>
          <option value="500">2×</option>
          <option value="250">4×</option>
          <option value="100">10×</option>
        </select>
      </label>
      <strong>{length ? `${value + 1} / ${length}` : "0 / 0"}</strong>
    </div>
  );
}

function ScannerTable({
  scanner,
  onOpen,
}: {
  scanner: Record<string, any> | null;
  onOpen: (datasetId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [quality, setQuality] = useState("all");
  const rows = useMemo(
    () =>
      (scanner?.rows || []).filter(
        (row: any) =>
          `${row.dataset_id} ${row.symbol} ${row.trend}`.toLowerCase().includes(query.toLowerCase()) &&
          (quality === "all" || String(row.quality_verdict).toLowerCase() === quality),
      ),
    [scanner, query, quality],
  );
  return (
    <Card className="research-scanner">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">On-demand governed scanner</p>
          <h2>Latest dataset states</h2>
        </div>
        <StatusBadge value={`${rows.length} resources`} />
      </div>
      <div className="scanner-controls">
        <label className="search-box">
          <Icon name="search" />
          <span className="sr-only">Search scanner</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search symbol, dataset, or state…" />
        </label>
        <select aria-label="Scanner quality filter" value={quality} onChange={(event) => setQuality(event.target.value)}>
          <option value="all">All quality verdicts</option>
          <option value="pass">PASS</option>
          <option value="needs manual review">Needs manual review</option>
        </select>
      </div>
      <div className="scanner-table" role="region" aria-label="Governed research scanner" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>Resource</th><th>Quality</th><th>Last timestamp</th><th>Close</th>
              <th>1-bar return</th><th>Trend</th><th>Volume</th><th>Delta</th><th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row: any) => (
              <tr key={row.dataset_id}>
                <td><strong>{row.symbol} · {row.timeframe}</strong><small>{row.dataset_id}</small></td>
                <td><StatusBadge value={row.quality_verdict || row.status} kind="scientific" /></td>
                <td>{formatDate(row.timestamp)}</td>
                <td>{formatNumber(row.close)}</td>
                <td>{row.one_bar_return == null ? "—" : `${(row.one_bar_return * 100).toFixed(3)}%`}</td>
                <td>{humanize(row.trend || row.status)}</td>
                <td>{formatNumber(row.volume)}</td>
                <td>{formatNumber(row.delta)}</td>
                <td><Button variant="secondary" onClick={() => onOpen(row.dataset_id)}>Chart</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small>{scanner?.note}</small>
    </Card>
  );
}

function ParityMatrix({ capabilities }: { capabilities: Array<Record<string, string>> }) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="parity-matrix">
      <button type="button" className="parity-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>
          <p className="eyebrow">Research/backtesting parity</p>
          <h2>Capability contract</h2>
        </span>
        <span>{open ? "Hide matrix" : `Inspect ${capabilities.length} capabilities`}</span>
      </button>
      {open && (
        <div className="parity-grid">
          {capabilities.map((item) => (
            <div key={item.capability}>
              <strong>{item.capability}</strong>
              <StatusBadge value={humanize(item.status)} />
              <p>{item.evidence}</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function formatNumber(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(number);
}
