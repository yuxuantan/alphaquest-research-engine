from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trades",
    "mes_volume",
    "mes_trades",
}


def build_es_mes_participation_features(
    df: pd.DataFrame,
    *,
    windows: tuple[int, ...] = (15, 30, 60),
    rank_window: int = 252,
    rank_min_periods: int = 60,
    tick_size: float = 0.25,
    mes_contract_ratio: float = 10.0,
) -> pd.DataFrame:
    """Build point-in-time MES participation features on aligned ES/MES bars."""
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"ES/MES participation source missing required columns: {missing}.")
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    if mes_contract_ratio <= 0:
        raise ValueError("mes_contract_ratio must be greater than 0.")
    if rank_window <= 0:
        raise ValueError("rank_window must be greater than 0.")
    if rank_min_periods <= 0:
        raise ValueError("rank_min_periods must be greater than 0.")
    if any(window <= 0 for window in windows):
        raise ValueError("windows must contain positive integers.")

    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"])
    out = out.sort_values("timestamp").reset_index(drop=True)
    for column in ["open", "high", "low", "close", "volume", "trades", "mes_volume", "mes_trades"]:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["session_date"] = out["timestamp"].dt.date
    out["mes_notional_equiv_volume"] = out["mes_volume"] / float(mes_contract_ratio)
    out["mes_participation_share"] = _safe_divide(
        out["mes_notional_equiv_volume"],
        out["volume"] + out["mes_notional_equiv_volume"],
    )
    out["mes_trade_share"] = _safe_divide(out["mes_trades"], out["trades"] + out["mes_trades"])

    grouped = out.groupby("session_date", sort=False)
    for window in tuple(int(w) for w in windows):
        mes_equiv = (
            grouped["mes_notional_equiv_volume"]
            .rolling(window, min_periods=window)
            .sum()
            .reset_index(level=0, drop=True)
        )
        es_volume = (
            grouped["volume"].rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        )
        mes_trades = (
            grouped["mes_trades"].rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        )
        es_trades = (
            grouped["trades"].rolling(window, min_periods=window).sum().reset_index(level=0, drop=True)
        )

        share_col = f"mes_participation_share_{window}"
        trade_share_col = f"mes_trade_share_{window}"
        out[share_col] = _safe_divide(mes_equiv, es_volume + mes_equiv)
        out[trade_share_col] = _safe_divide(mes_trades, es_trades + mes_trades)
        out[f"es_return_ticks_{window}"] = (
            out["close"] - grouped["close"].shift(window)
        ) / float(tick_size)
        out[f"{share_col}_rank{rank_window}"] = same_clock_prior_rank(
            out, share_col, rank_window, rank_min_periods
        )
        out[f"{trade_share_col}_rank{rank_window}"] = same_clock_prior_rank(
            out, trade_share_col, rank_window, rank_min_periods
        )

    if "symbol" not in out.columns:
        out["symbol"] = "ES"
    return out.replace([np.inf, -np.inf], np.nan)


def same_clock_prior_rank(
    df: pd.DataFrame,
    column: str,
    window: int,
    min_periods: int,
) -> pd.Series:
    ordered = df.sort_values("timestamp")
    time_key = pd.to_datetime(ordered["timestamp"]).dt.strftime("%H:%M:%S")
    values = pd.to_numeric(ordered[column], errors="coerce")
    ranked = values.groupby(time_key, sort=False).transform(
        lambda series: _rank_current_against_prior_window(series, window, min_periods)
    )
    out = pd.Series(np.nan, index=df.index, dtype=float)
    out.loc[ordered.index] = ranked.to_numpy(dtype=float)
    return out


def _rank_current_against_prior_window(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    raw = series.to_numpy(dtype=float)
    out = np.full(len(raw), np.nan, dtype=float)
    for idx, value in enumerate(raw):
        history = raw[max(0, idx - window) : idx]
        history = history[np.isfinite(history)]
        if len(history) < min_periods or not np.isfinite(value):
            continue
        out[idx] = float((history <= value).mean())
    return pd.Series(out, index=series.index, dtype=float)


def _safe_divide(numerator, denominator) -> pd.Series:
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    return num / den.replace(0.0, np.nan)
