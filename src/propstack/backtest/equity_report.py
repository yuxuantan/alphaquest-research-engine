from __future__ import annotations

from html import escape
import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd

from propstack.utils.reports import normalize_report_timestamps, write_report_csv


def equity_curve_frame(
    trades: pd.DataFrame,
    initial_balance: float = 0.0,
    run_column: str | None = None,
    pnl_column: str = "net_pnl",
    timestamp_column: str | None = "exit_timestamp",
    sequence_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Build timestamped equity curve rows from a trade log."""
    if trades is None or trades.empty:
        run_column = None
        columns = _curve_columns(run_column)
        return pd.DataFrame([_initial_row(initial_balance, run_column, None, pd.NA)], columns=columns)
    if run_column not in trades.columns:
        run_column = None
    columns = _curve_columns(run_column)
    if pnl_column not in trades.columns:
        raise ValueError(f"Trade log is missing required PnL column: {pnl_column}.")

    groups = [(None, trades)] if run_column is None else list(trades.groupby(run_column, sort=True, dropna=False))
    rows = []
    for run_id, group in groups:
        ordered = _ordered_trades(group, timestamp_column, sequence_columns)
        valid = ordered[pd.to_numeric(ordered[pnl_column], errors="coerce").notna()].copy()
        initial_timestamp = _initial_timestamp(ordered, timestamp_column)
        rows.extend(
            _curve_rows_for_group(
                valid,
                initial_balance=initial_balance,
                run_column=run_column,
                run_id=run_id,
                pnl_column=pnl_column,
                timestamp_column=timestamp_column,
                initial_timestamp=initial_timestamp,
            )
        )
    return pd.DataFrame(rows, columns=columns)


def write_equity_report(
    trades: pd.DataFrame,
    out_dir: str | Path,
    initial_balance: float = 0.0,
    timezone: str | None = None,
    title: str = "Equity Curve",
    run_column: str | None = None,
    pnl_column: str = "net_pnl",
    timestamp_column: str | None = "exit_timestamp",
    sequence_columns: Iterable[str] | None = None,
    csv_name: str = "equity_curve.csv",
    html_name: str = "equity_curve.html",
) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    curve = equity_curve_frame(
        trades,
        initial_balance=initial_balance,
        run_column=run_column,
        pnl_column=pnl_column,
        timestamp_column=timestamp_column,
        sequence_columns=sequence_columns,
    )
    csv_path = out / csv_name
    html_path = out / html_name
    write_report_csv(curve, csv_path, timezone, index=False)
    html_curve = normalize_report_timestamps(curve, timezone)
    html_path.write_text(_equity_report_html(html_curve, title), encoding="utf-8")
    return {
        "equity_curve_csv": str(csv_path),
        "equity_curve_html": str(html_path),
        "equity_curve_points": int(len(curve)),
    }


def write_equity_report_from_trade_log(
    trade_log: str | Path,
    out_dir: str | Path | None = None,
    initial_balance: float = 0.0,
    timezone: str | None = None,
    title: str | None = None,
    run_column: str | None = None,
    pnl_column: str = "net_pnl",
    timestamp_column: str | None = "exit_timestamp",
    sequence_columns: Iterable[str] | None = None,
) -> dict:
    path = Path(trade_log)
    trades = pd.read_csv(path)
    return write_equity_report(
        trades,
        out_dir or path.parent,
        initial_balance=initial_balance,
        timezone=timezone,
        title=title or _default_title(path),
        run_column=run_column,
        pnl_column=pnl_column,
        timestamp_column=timestamp_column,
        sequence_columns=sequence_columns,
    )


def _curve_columns(run_column: str | None) -> list[str]:
    columns = [
        "point",
        "timestamp",
        "trade_id",
        "net_pnl",
        "cumulative_net_pnl",
        "equity",
        "peak_equity",
        "drawdown",
        "drawdown_pct",
    ]
    if run_column:
        columns.insert(0, run_column)
    return columns


def _curve_rows_for_group(
    trades: pd.DataFrame,
    initial_balance: float,
    run_column: str | None,
    run_id,
    pnl_column: str,
    timestamp_column: str | None,
    initial_timestamp,
) -> list[dict]:
    rows = [_initial_row(initial_balance, run_column, run_id, initial_timestamp)]
    equity = float(initial_balance)
    peak = equity
    cumulative = 0.0
    for point, (_, trade) in enumerate(trades.iterrows(), start=1):
        pnl = float(trade[pnl_column])
        cumulative += pnl
        equity += pnl
        peak = max(peak, equity)
        drawdown = peak - equity
        row = {
            "point": point,
            "timestamp": _trade_timestamp(trade, timestamp_column),
            "trade_id": _trade_identifier(trade),
            "net_pnl": pnl,
            "cumulative_net_pnl": cumulative,
            "equity": equity,
            "peak_equity": peak,
            "drawdown": drawdown,
            "drawdown_pct": drawdown / peak if peak > 0 else 0.0,
        }
        if run_column:
            row[run_column] = run_id
        rows.append(row)
    return rows


def _initial_row(initial_balance: float, run_column: str | None, run_id, timestamp) -> dict:
    row = {
        "point": 0,
        "timestamp": timestamp,
        "trade_id": pd.NA,
        "net_pnl": 0.0,
        "cumulative_net_pnl": 0.0,
        "equity": float(initial_balance),
        "peak_equity": float(initial_balance),
        "drawdown": 0.0,
        "drawdown_pct": 0.0,
    }
    if run_column:
        row[run_column] = run_id
    return row


def _ordered_trades(
    trades: pd.DataFrame,
    timestamp_column: str | None,
    sequence_columns: Iterable[str] | None,
) -> pd.DataFrame:
    out = trades.copy()
    sort_columns = []
    if timestamp_column and timestamp_column in out.columns:
        out["_timestamp_order"] = pd.to_datetime(out[timestamp_column], errors="coerce", utc=True)
        sort_columns.append("_timestamp_order")
    for column in sequence_columns or ():
        if column in out.columns and column not in sort_columns:
            sort_columns.append(column)
    for column in ["trade_id", "source_trade_id", "sample_index"]:
        if column in out.columns and column not in sort_columns:
            sort_columns.append(column)
    if sort_columns:
        out = out.sort_values(sort_columns, kind="mergesort")
    return out.drop(columns=["_timestamp_order"], errors="ignore").reset_index(drop=True)


def _initial_timestamp(trades: pd.DataFrame, timestamp_column: str | None):
    for column in ["entry_timestamp", timestamp_column]:
        if column and column in trades.columns:
            values = trades[column].dropna()
            if not values.empty:
                return values.iloc[0]
    return pd.NA


def _trade_timestamp(trade: pd.Series, timestamp_column: str | None):
    if timestamp_column and timestamp_column in trade.index:
        return trade[timestamp_column]
    return pd.NA


def _trade_identifier(trade: pd.Series):
    for column in ["trade_id", "source_trade_id", "sample_index"]:
        if column in trade.index:
            return trade[column]
    return pd.NA


def _default_title(path: Path) -> str:
    stem = path.stem.replace("_", " ").title()
    return f"{stem} Equity Curve"


def _equity_report_html(curve: pd.DataFrame, title: str) -> str:
    payload = _html_payload(curve)
    payload_json = json.dumps(payload, allow_nan=False, separators=(",", ":")).replace("</", "<\\/")
    title_text = escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_text}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #697386;
      --line: #2563eb;
      --loss: #dc2626;
      --grid: #e5e7eb;
      --border: #d5dae3;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 700;
    }}
    .control {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }}
    select {{
      min-width: 160px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 7px 10px;
      font-size: 14px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .metric strong {{
      display: block;
      font-size: 18px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .chart-panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
    }}
    canvas {{
      display: block;
      width: 100%;
      height: 460px;
    }}
    .note {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 10px;
    }}
    @media (max-width: 760px) {{
      main {{ padding: 16px; }}
      header {{ display: block; }}
      .control {{ margin-top: 12px; }}
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      canvas {{ height: 360px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title_text}</h1>
      <label class="control" id="runControl">Run <select id="runSelect"></select></label>
    </header>
    <section class="summary" aria-label="Equity summary">
      <div class="metric"><span>Trades</span><strong id="trades">0</strong></div>
      <div class="metric"><span>Start</span><strong id="start">$0</strong></div>
      <div class="metric"><span>End</span><strong id="end">$0</strong></div>
      <div class="metric"><span>Net PnL</span><strong id="net">$0</strong></div>
      <div class="metric"><span>Max Drawdown</span><strong id="drawdown">$0</strong></div>
    </section>
    <section class="chart-panel">
      <canvas id="chart" aria-label="Equity curve chart"></canvas>
      <div class="note" id="note"></div>
    </section>
  </main>
  <script id="equity-data" type="application/json">{payload_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById("equity-data").textContent);
    const runs = payload.runs;
    const select = document.getElementById("runSelect");
    const control = document.getElementById("runControl");
    const chart = document.getElementById("chart");
    const ctx = chart.getContext("2d");
    const ids = runs.map((run) => run.id);

    for (const run of runs) {{
      const option = document.createElement("option");
      option.value = run.id;
      option.textContent = run.label;
      select.appendChild(option);
    }}
    if (runs.length <= 1) {{
      control.style.display = "none";
    }}

    const money = new Intl.NumberFormat("en-US", {{
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0
    }});
    const percent = new Intl.NumberFormat("en-US", {{
      style: "percent",
      maximumFractionDigits: 2
    }});

    function resizeCanvas() {{
      const rect = chart.getBoundingClientRect();
      const scale = window.devicePixelRatio || 1;
      chart.width = Math.max(1, Math.floor(rect.width * scale));
      chart.height = Math.max(1, Math.floor(rect.height * scale));
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
    }}

    function draw() {{
      const run = runs.find((item) => item.id === select.value) || runs[0];
      if (!run) return;
      resizeCanvas();
      const rect = chart.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);

      document.getElementById("trades").textContent = run.summary.trades.toLocaleString("en-US");
      document.getElementById("start").textContent = money.format(run.summary.start);
      document.getElementById("end").textContent = money.format(run.summary.end);
      document.getElementById("net").textContent = money.format(run.summary.net);
      document.getElementById("drawdown").textContent =
        `${{money.format(run.summary.maxDrawdown)}} (${{percent.format(run.summary.maxDrawdownPct)}})`;
      document.getElementById("note").textContent = run.summary.note;

      const data = run.points;
      if (!data.length) return;
      const margin = {{ left: 72, right: 20, top: 22, bottom: 42 }};
      const plotW = Math.max(1, width - margin.left - margin.right);
      const plotH = Math.max(1, height - margin.top - margin.bottom);
      const values = data.map((point) => point.equity);
      let minY = Math.min(...values);
      let maxY = Math.max(...values);
      if (minY === maxY) {{
        minY -= Math.max(100, Math.abs(minY) * 0.01);
        maxY += Math.max(100, Math.abs(maxY) * 0.01);
      }}
      const pad = (maxY - minY) * 0.08;
      minY -= pad;
      maxY += pad;

      function xAt(index) {{
        return margin.left + (data.length === 1 ? 0 : (index / (data.length - 1)) * plotW);
      }}
      function yAt(value) {{
        return margin.top + ((maxY - value) / (maxY - minY)) * plotH;
      }}

      ctx.lineWidth = 1;
      ctx.strokeStyle = "#e5e7eb";
      ctx.fillStyle = "#697386";
      ctx.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      for (let i = 0; i <= 4; i++) {{
        const value = minY + ((maxY - minY) * i) / 4;
        const y = yAt(value);
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(width - margin.right, y);
        ctx.stroke();
        ctx.fillText(money.format(value), margin.left - 10, y);
      }}

      const startY = yAt(run.summary.start);
      ctx.strokeStyle = "#94a3b8";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(margin.left, startY);
      ctx.lineTo(width - margin.right, startY);
      ctx.stroke();
      ctx.setLineDash([]);

      const gradient = ctx.createLinearGradient(0, margin.top, 0, height - margin.bottom);
      gradient.addColorStop(0, "rgba(37, 99, 235, 0.16)");
      gradient.addColorStop(1, "rgba(37, 99, 235, 0.00)");
      ctx.beginPath();
      data.forEach((point, index) => {{
        const x = xAt(index);
        const y = yAt(point.equity);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }});
      ctx.lineTo(xAt(data.length - 1), height - margin.bottom);
      ctx.lineTo(xAt(0), height - margin.bottom);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.beginPath();
      data.forEach((point, index) => {{
        const x = xAt(index);
        const y = yAt(point.equity);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }});
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 2.4;
      ctx.stroke();

      const end = data[data.length - 1];
      ctx.fillStyle = end.equity >= run.summary.start ? "#16a34a" : "#dc2626";
      ctx.beginPath();
      ctx.arc(xAt(data.length - 1), yAt(end.equity), 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#697386";
      ctx.textBaseline = "top";
      ctx.textAlign = "left";
      ctx.fillText(data[0].timestamp || "start", margin.left, height - margin.bottom + 14);
      ctx.textAlign = "right";
      ctx.fillText(end.timestamp || `trade ${{end.point}}`, width - margin.right, height - margin.bottom + 14);
    }}

    select.addEventListener("change", draw);
    window.addEventListener("resize", draw);
    select.value = ids[0] || "";
    draw();
  </script>
</body>
</html>
"""


def _html_payload(curve: pd.DataFrame) -> dict:
    run_column = "run_id" if "run_id" in curve.columns else None
    groups = [(None, curve)] if run_column is None else list(curve.groupby(run_column, sort=True, dropna=False))
    runs = []
    for run_id, group in groups:
        group = group.sort_values("point", kind="mergesort").reset_index(drop=True)
        points = [_html_point(row) for _, row in group.iterrows()]
        start = float(group.iloc[0]["equity"]) if len(group) else 0.0
        end = float(group.iloc[-1]["equity"]) if len(group) else start
        max_drawdown = float(group["drawdown"].max()) if len(group) else 0.0
        max_drawdown_pct = float(group["drawdown_pct"].max()) if len(group) else 0.0
        label = "All trades" if run_column is None else f"Run {run_id}"
        runs.append(
            {
                "id": "__all__" if run_column is None else str(run_id),
                "label": label,
                "points": points,
                "summary": {
                    "trades": max(len(group) - 1, 0),
                    "start": start,
                    "end": end,
                    "net": end - start,
                    "maxDrawdown": max_drawdown,
                    "maxDrawdownPct": max_drawdown_pct,
                    "note": _summary_note(group),
                },
            }
        )
    return {"runs": runs}


def _html_point(row: pd.Series) -> dict:
    return {
        "point": int(row["point"]),
        "timestamp": _json_string(row.get("timestamp")),
        "equity": _json_float(row["equity"]),
        "drawdown": _json_float(row["drawdown"]),
    }


def _summary_note(group: pd.DataFrame) -> str:
    if len(group) <= 1:
        return "No closed trades. The chart shows the configured starting balance."
    start_time = _json_string(group.iloc[0].get("timestamp"))
    end_time = _json_string(group.iloc[-1].get("timestamp"))
    if start_time and end_time:
        return f"{len(group) - 1:,} closed trades from {start_time} to {end_time}."
    return f"{len(group) - 1:,} closed trades in trade exit order."


def _json_string(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _json_float(value) -> float:
    out = float(value)
    return out if math.isfinite(out) else 0.0
