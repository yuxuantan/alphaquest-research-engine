from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


CAMPAIGN_ID = "nq_chartfanatics_london_trident_fvg_continuation"
DATA_PATH = Path("data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet")
ARTIFACT_ROOT = Path("research_artifacts")
AUDIT_DATE = "2026-06-30"
ARTIFACT_STAMP = "20260630"
START_DATE = pd.Timestamp("2011-01-03").date()
END_DATE = pd.Timestamp("2026-05-29").date()
LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50
TICK_SIZE = 0.25


VARIANTS = [
    {
        "variant_id": "london_long_trident_ema13_0630",
        "directions": {"long"},
        "mid_ema_period": 13,
        "confirmation_buffer_ticks": 0,
        "require_200_ema_bias": True,
    },
    {
        "variant_id": "london_short_trident_ema13_0630",
        "directions": {"short"},
        "mid_ema_period": 13,
        "confirmation_buffer_ticks": 0,
        "require_200_ema_bias": True,
    },
    {
        "variant_id": "london_two_sided_trident_ema13_0630",
        "directions": {"long", "short"},
        "mid_ema_period": 13,
        "confirmation_buffer_ticks": 0,
        "require_200_ema_bias": True,
    },
    {
        "variant_id": "london_long_trident_ema15_0630",
        "directions": {"long"},
        "mid_ema_period": 15,
        "confirmation_buffer_ticks": 0,
        "require_200_ema_bias": True,
    },
    {
        "variant_id": "london_two_sided_trident_ema15_strict_confirm_0630",
        "directions": {"long", "short"},
        "mid_ema_period": 15,
        "confirmation_buffer_ticks": 1,
        "require_200_ema_bias": True,
    },
]

ENTRY_GRID = {
    "min_gap_ticks": [1, 2, 4],
    "max_doji_body_ratio": [0.25, 0.35, 0.45],
}
STOP_GRID = {"stop_offset_ticks": [0, 4, 8]}
TARGET_GRID = {"target_r_multiple": [2.0, 3.0]}


def main() -> None:
    bars = _load_30m_bars(DATA_PATH)
    sessions = sorted(bars["session_date"].dropna().unique())
    sessions = [day for day in sessions if START_DATE <= day <= END_DATE]
    if len(sessions) < 252:
        raise SystemExit(f"Expected at least 252 sessions, found {len(sessions)}.")
    latest_sessions = set(sessions[-252:])

    rows = []
    for variant in VARIANTS:
        for min_gap_ticks in ENTRY_GRID["min_gap_ticks"]:
            for max_doji_body_ratio in ENTRY_GRID["max_doji_body_ratio"]:
                signal_dates = _signal_dates(
                    bars=bars,
                    variant=variant,
                    min_gap_ticks=min_gap_ticks,
                    max_doji_body_ratio=max_doji_body_ratio,
                )
                full_count = len(signal_dates)
                limited_count = sum(LIMITED_START <= day <= LIMITED_END for day in signal_dates)
                latest_count = sum(day in latest_sessions for day in signal_dates)
                full_per_year = _per_year(full_count, sessions[0], sessions[-1])
                limited_per_year = _per_year(limited_count, LIMITED_START, LIMITED_END)
                pass_gate = (
                    full_per_year >= MIN_FULL_SIGNALS_PER_YEAR
                    and limited_per_year >= MIN_LIMITED_SIGNALS_PER_YEAR
                    and latest_count >= MIN_LATEST_252_SIGNALS
                )
                rows.append(
                    {
                        "campaign_id": CAMPAIGN_ID,
                        "variant_id": variant["variant_id"],
                        "directions": ",".join(sorted(variant["directions"])),
                        "mid_ema_period": variant["mid_ema_period"],
                        "confirmation_buffer_ticks": variant["confirmation_buffer_ticks"],
                        "require_200_ema_bias": variant["require_200_ema_bias"],
                        "min_gap_ticks": min_gap_ticks,
                        "max_doji_body_ratio": max_doji_body_ratio,
                        "fvg_window": "02:30:00-04:00:00",
                        "entry_window": "03:00:00-06:30:00",
                        "timeframe": "30m",
                        "full_start_date": str(sessions[0]),
                        "full_end_date": str(sessions[-1]),
                        "full_signals": full_count,
                        "full_signals_per_year": full_per_year,
                        "limited_start_date": str(LIMITED_START),
                        "limited_end_date": str(LIMITED_END),
                        "limited_signals": limited_count,
                        "limited_signals_per_year": limited_per_year,
                        "latest_252_start_date": str(sessions[-252]),
                        "latest_252_end_date": str(sessions[-1]),
                        "latest_252_signals": latest_count,
                        "density_gate_pass": pass_gate,
                    }
                )

    detail = pd.DataFrame(rows)
    summary = _summary(detail)
    machine_summary = _machine_summary(detail, summary, sessions, bars)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    detail_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
    summary_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
    markdown_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    markdown_path.write_text(_markdown(summary, machine_summary, detail_path, summary_path), encoding="utf-8")
    print(json.dumps(machine_summary, indent=2, sort_keys=True))


def _load_30m_bars(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"NQ Databento cache not found: {path}")
    raw = pd.read_parquet(path)
    raw = raw.sort_values("timestamp")
    raw["timestamp"] = pd.to_datetime(raw["timestamp"])
    raw["session_date"] = raw["timestamp"].dt.date
    raw = raw[(raw["session_date"] >= START_DATE) & (raw["session_date"] <= END_DATE)].copy()
    raw = raw.set_index("timestamp")
    bars = raw.resample("30min", origin="start_day", label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    bars = bars.dropna(subset=["open", "high", "low", "close"]).reset_index()
    bars = bars[bars["volume"] > 0].copy()
    bars["session_date"] = bars["timestamp"].dt.date
    bars["bar_end"] = bars["timestamp"] + pd.Timedelta(minutes=30)
    bars["bar_start_seconds"] = _bar_seconds(bars["timestamp"])
    bars["bar_end_seconds"] = _bar_seconds(bars["bar_end"])
    close = pd.to_numeric(bars["close"], errors="coerce")
    for period in [5, 9, 13, 15, 21, 200]:
        bars[f"ema_{period}"] = close.ewm(span=period, adjust=False, min_periods=period).mean()
    return bars.reset_index(drop=True)


def _signal_dates(
    bars: pd.DataFrame,
    variant: dict,
    min_gap_ticks: int,
    max_doji_body_ratio: float,
) -> list:
    min_gap = float(min_gap_ticks) * TICK_SIZE
    confirmation_buffer = float(variant["confirmation_buffer_ticks"]) * TICK_SIZE
    signaled_days: set = set()
    signal_dates: list = []

    # FVG third candle starts inside 02:30-04:00 ET; the setup is known only
    # after the third, doji, and confirmation candles have closed.
    fvg_start = _time_seconds("02:30:00")
    fvg_end = _time_seconds("04:00:00")
    entry_start = _time_seconds("03:00:00")
    entry_end = _time_seconds("06:30:00")

    candidate_indices = bars.index[
        (bars["bar_start_seconds"] >= fvg_start)
        & (bars["bar_start_seconds"] <= fvg_end)
        & (bars["session_date"] >= START_DATE)
        & (bars["session_date"] <= END_DATE)
    ]
    for idx in candidate_indices:
        if idx < 2 or idx > len(bars) - 3:
            continue
        third = bars.iloc[idx]
        session_date = third["session_date"]
        if session_date in signaled_days:
            continue
        if not START_DATE <= session_date <= END_DATE:
            continue
        if not (fvg_start <= int(third["bar_start_seconds"]) <= fvg_end):
            continue

        first = bars.iloc[idx - 2]
        doji = bars.iloc[idx + 1]
        confirm = bars.iloc[idx + 2]
        if doji["session_date"] != session_date or confirm["session_date"] != session_date:
            continue

        entry_time = int(confirm["bar_end_seconds"])
        if not (entry_start <= entry_time <= entry_end):
            continue
        if not _small_body(doji, max_doji_body_ratio):
            continue

        long_gap = float(third["low"]) - float(first["high"])
        short_gap = float(first["low"]) - float(third["high"])
        direction = None
        midpoint = None
        gap_bottom = None
        gap_top = None

        if "long" in variant["directions"] and long_gap >= min_gap and _ema_stack_ok(confirm, "long", variant):
            gap_bottom = float(first["high"])
            gap_top = float(third["low"])
            midpoint = (gap_bottom + gap_top) / 2.0
            if _long_trident(doji, confirm, midpoint, confirmation_buffer):
                direction = "long"

        if direction is None and "short" in variant["directions"] and short_gap >= min_gap and _ema_stack_ok(
            confirm, "short", variant
        ):
            gap_bottom = float(third["high"])
            gap_top = float(first["low"])
            midpoint = (gap_bottom + gap_top) / 2.0
            if _short_trident(doji, confirm, midpoint, confirmation_buffer):
                direction = "short"

        if direction is None:
            continue
        signaled_days.add(session_date)
        signal_dates.append(session_date)
    return signal_dates


def _small_body(bar: pd.Series, max_ratio: float) -> bool:
    high = float(bar["high"])
    low = float(bar["low"])
    candle_range = high - low
    if candle_range <= 0:
        return False
    body = abs(float(bar["close"]) - float(bar["open"]))
    return body / candle_range <= float(max_ratio)


def _long_trident(doji: pd.Series, confirm: pd.Series, midpoint: float, confirmation_buffer: float) -> bool:
    body_low = min(float(doji["open"]), float(doji["close"]))
    return (
        float(doji["low"]) <= midpoint
        and body_low >= midpoint
        and float(confirm["close"]) >= float(doji["high"]) + confirmation_buffer
    )


def _short_trident(doji: pd.Series, confirm: pd.Series, midpoint: float, confirmation_buffer: float) -> bool:
    body_high = max(float(doji["open"]), float(doji["close"]))
    return (
        float(doji["high"]) >= midpoint
        and body_high <= midpoint
        and float(confirm["close"]) <= float(doji["low"]) - confirmation_buffer
    )


def _ema_stack_ok(bar: pd.Series, direction: str, variant: dict) -> bool:
    mid = int(variant["mid_ema_period"])
    required = [f"ema_{period}" for period in [5, 9, mid, 21]]
    if bool(variant["require_200_ema_bias"]):
        required.append("ema_200")
    if any(pd.isna(bar[column]) for column in required):
        return False
    close = float(bar["close"])
    ema5 = float(bar["ema_5"])
    ema9 = float(bar["ema_9"])
    ema_mid = float(bar[f"ema_{mid}"])
    ema21 = float(bar["ema_21"])
    ema200 = float(bar["ema_200"])
    if direction == "long":
        stacked = ema5 > ema9 > ema_mid > ema21
        return stacked and (not variant["require_200_ema_bias"] or close > ema200)
    stacked = ema5 < ema9 < ema_mid < ema21
    return stacked and (not variant["require_200_ema_bias"] or close < ema200)


def _bar_seconds(timestamp: pd.Series) -> pd.Series:
    return timestamp.dt.hour * 3600 + timestamp.dt.minute * 60 + timestamp.dt.second


def _time_seconds(value: str) -> int:
    parsed = pd.Timestamp(f"2000-01-01 {value}").time()
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second


def _per_year(count: int, start_date, end_date) -> float:
    years = max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25, 1 / 365.25)
    return float(count) / years


def _summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant_id, group in detail.groupby("variant_id", sort=True):
        rows.append(
            {
                "variant_id": variant_id,
                "entry_rows": int(len(group)),
                "pass_rows": int(group["density_gate_pass"].sum()),
                "min_full_signals_per_year": float(group["full_signals_per_year"].min()),
                "median_full_signals_per_year": float(group["full_signals_per_year"].median()),
                "max_full_signals_per_year": float(group["full_signals_per_year"].max()),
                "min_limited_signals_per_year": float(group["limited_signals_per_year"].min()),
                "median_limited_signals_per_year": float(group["limited_signals_per_year"].median()),
                "max_limited_signals_per_year": float(group["limited_signals_per_year"].max()),
                "min_latest_252_signals": int(group["latest_252_signals"].min()),
                "median_latest_252_signals": float(group["latest_252_signals"].median()),
                "max_latest_252_signals": int(group["latest_252_signals"].max()),
                "verdict": "PASS" if bool(group["density_gate_pass"].all()) else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def _machine_summary(detail: pd.DataFrame, summary: pd.DataFrame, sessions: list, bars: pd.DataFrame) -> dict:
    return {
        "all_rows_density_pass": bool(detail["density_gate_pass"].all()),
        "audit_date": AUDIT_DATE,
        "campaign_id": CAMPAIGN_ID,
        "declared_entry_rows": int(len(detail)),
        "density_pass_rows": int(detail["density_gate_pass"].sum()),
        "density_fail_rows": int((~detail["density_gate_pass"]).sum()),
        "full_start_date": str(sessions[0]),
        "full_end_date": str(sessions[-1]),
        "full_sessions": int(len(sessions)),
        "latest_252_start_date": str(sessions[-252]),
        "latest_252_end_date": str(sessions[-1]),
        "limited_start_date": str(LIMITED_START),
        "limited_end_date": str(LIMITED_END),
        "min_full_signals_per_year": float(detail["full_signals_per_year"].min()),
        "min_limited_signals_per_year": float(detail["limited_signals_per_year"].min()),
        "min_latest_252_signals": int(detail["latest_252_signals"].min()),
        "prepared_30m_bars": int(len(bars)),
        "timeframe": "30m",
        "variant_summary": summary.to_dict(orient="records"),
    }


def _markdown(summary: pd.DataFrame, machine_summary: dict, detail_path: Path, summary_path: Path) -> str:
    verdict = "PASS" if machine_summary["all_rows_density_pass"] else "FAIL"
    lines = [
        "# NQ ChartFanatics London Trident FVG Continuation Density Audit",
        "",
        f"Audit date: {AUDIT_DATE}",
        "",
        f"Verdict: {verdict}",
        "",
        "Source: ChartFanatics Unique High RR, TG Capital, https://www.chartfanatics.com/strategies/unique-high-rr",
        "",
        "No PnL was inspected. This audit counts only predeclared completed-bar signals from local NQ Databento ETH/RTH OHLCV.",
        "",
        "Density rule: every declared entry-grid row must exceed 50 signals/year on full history and the limited-core proxy window, and must have at least 50 raw signals in the latest 252 sessions.",
        "",
        f"Detail CSV: `{detail_path}`",
        f"Summary CSV: `{summary_path}`",
        "",
        "## Machine Summary",
        "",
        "```json",
        json.dumps(machine_summary, indent=2, sort_keys=True),
        "```",
        "",
        "## Variant Summary",
        "",
        _markdown_table(summary),
        "",
        "## Predeclared Mechanics",
        "",
        "- Instrument: NQ futures.",
        "- Data: local Databento one-minute ETH/RTH explicit-roll OHLCV cache, resampled to 30-minute bars.",
        "- Setup window: the third candle of a three-candle FVG starts between 02:30 and 04:00 ET.",
        "- Entry window: confirmation completes between 03:00 and 06:30 ET; staged testing, if approved, would enter next 30-minute open.",
        "- Long setup: bullish FVG, stacked 5/9/13-or-15/21 EMAs, close above 200 EMA, doji wick into FVG midpoint with body above midpoint, confirmation close above doji high.",
        "- Short setup: bearish FVG, reverse EMA stack, close below 200 EMA, doji wick into FVG midpoint with body below midpoint, confirmation close below doji low.",
        "- Entry tunables: min_gap_ticks in [1, 2, 4] and max_doji_body_ratio in [0.25, 0.35, 0.45].",
        "- Stop tunable for campaign definition: stop_offset_ticks in [0, 4, 8].",
        "- Take-profit tunable for campaign definition: target_r_multiple in [2.0, 3.0].",
        "",
        "## Lookahead Controls",
        "",
        "- FVGs are known only after the third 30-minute candle closes.",
        "- The doji and confirmation candle are both completed before any signal is counted.",
        "- EMA state uses only completed 30-minute closes through the confirmation candle.",
        "- No future high, low, session range, VWAP, orderflow, or post-entry path is used.",
    ]
    return "\n".join(lines) + "\n"


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in frame.iterrows():
        values = [str(row[column]) for column in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
