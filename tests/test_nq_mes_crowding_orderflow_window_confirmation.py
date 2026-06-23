from pathlib import Path

import pandas as pd

from propstack.strategy_modules.entry.nq_mes_crowding_orderflow_window_confirmation import (
    NqMesCrowdingOrderflowWindowConfirmationEntry,
)


def test_nq_mes_crowding_orderflow_uses_completed_window_pressure(tmp_path):
    entry = NqMesCrowdingOrderflowWindowConfirmationEntry(_params(tmp_path))
    entry.on_bar_close(_bar("2024-01-03 09:44", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14", close=102.0, signed_volume=800))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29",
            open_=101.5,
            close=101.0,
            signed_volume=-200,
            volume=1000,
            mes_trade_share_15_rank252=0.72,
            nq_return_ticks_15=-16,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["volatility_gate_value"] == 0.50
    assert signal.report_fields["nq_orderflow_window_bar_count"] == 1
    assert signal.report_fields["primary_orderflow_imbalance"] == -0.2
    assert signal.report_fields["signed_pressure_orderflow_imbalance"] == 0.2
    assert signal.report_fields["nq_orderflow_window_start"] == pd.Timestamp("2024-01-03 10:15")
    assert signal.report_fields["nq_orderflow_window_end"] == pd.Timestamp("2024-01-03 10:30")


def test_nq_mes_crowding_orderflow_rejects_wrong_signed_flow(tmp_path):
    entry = NqMesCrowdingOrderflowWindowConfirmationEntry(_params(tmp_path))
    entry.on_bar_close(_bar("2024-01-03 09:44", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14", close=102.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29",
            open_=101.5,
            close=101.0,
            signed_volume=200,
            volume=1000,
            mes_trade_share_15_rank252=0.72,
            nq_return_ticks_15=-16,
        )
    )

    assert signal is None


def test_nq_mes_crowding_orderflow_rejects_extreme_lagged_volatility(tmp_path):
    entry = NqMesCrowdingOrderflowWindowConfirmationEntry(
        _params(tmp_path, feature_value=0.99, volatility_gate_max=0.95)
    )
    entry.on_bar_close(_bar("2024-01-03 09:44", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14", close=102.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29",
            open_=101.5,
            close=101.0,
            signed_volume=-200,
            volume=1000,
            mes_trade_share_15_rank252=0.72,
            nq_return_ticks_15=-16,
        )
    )

    assert signal is None


def test_nq_mes_crowding_vwap_pressure_requires_completed_extension(tmp_path):
    entry = NqMesCrowdingOrderflowWindowConfirmationEntry(
        _params(
            tmp_path,
            confirmation_mode="vwap_pressure",
            min_vwap_extension_ticks=4,
        )
    )
    entry.on_bar_close(_bar("2024-01-03 09:44", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14", close=102.0))

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29",
            open_=101.0,
            close=101.0,
            signed_volume=-200,
            volume=1000,
            mes_trade_share_15_rank252=0.72,
            nq_return_ticks_15=-16,
        )
    )

    assert signal is None


def _params(tmp_path: Path, **overrides) -> dict:
    feature_value = overrides.pop("feature_value", 0.50)
    feature_csv = _feature_csv(tmp_path, "2024-01-03", absret5_rank_252=feature_value)
    params = {
        "setup_mode": "unit_absret5_1030_signed_window15_pressure_reversal",
        "entry_time": "10:30:00",
        "flatten_time": "12:00:00",
        "bar_interval_minutes": 1,
        "lookback_minutes": 15,
        "trend_lookback_minutes": 30,
        "rank_window": 252,
        "share_mode": "trade",
        "direction": "both",
        "share_rank_min": 0.55,
        "min_abs_return_ticks": 12,
        "min_trend_return_ticks": 8,
        "max_trades_per_day": 1,
        "stop_pct": 0.004,
        "target_r_multiple": 2.0,
        "tick_size": 0.25,
        "return_column_prefix": "nq",
        "feature_csv": str(feature_csv),
        "volatility_gate_column": "absret5_rank_252",
        "volatility_gate_max": 0.95,
        "orderflow_window_minutes": 15,
        "flow_mode": "signed_imbalance",
        "confirmation_mode": "pressure_extension",
        "min_orderflow_imbalance": 0.05,
    }
    params.update(overrides)
    return params


def _feature_csv(tmp_path: Path, session_date: str, **overrides) -> Path:
    row = {
        "session_date": session_date,
        "absret5_rank_252": 0.50,
        "range10_rank_252": 0.50,
        "downside20_rank_252": 0.50,
        "vol20_rank_252": 0.50,
        "vol5_over_vol20": 1.00,
    }
    row.update(overrides)
    path = tmp_path / "nq_vol_features.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def _bar(timestamp: str, **overrides) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    close = overrides.get("close", 100.0)
    open_ = overrides.get("open_", close)
    row = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "open": open_,
        "high": max(open_, close) + 0.25,
        "low": min(open_, close) - 0.25,
        "close": close,
        "volume": overrides.get("volume", 1000),
        "signed_volume": overrides.get("signed_volume", -100),
        "large10_volume": overrides.get("large10_volume", 100),
        "large10_signed_volume": overrides.get("large10_signed_volume", -20),
        "large20_volume": overrides.get("large20_volume", 50),
        "large20_signed_volume": overrides.get("large20_signed_volume", -10),
        "mes_trade_share_15": overrides.get("mes_trade_share_15", 0.10),
        "mes_trade_share_15_rank252": overrides.get("mes_trade_share_15_rank252", 0.0),
        "mes_participation_share_15": overrides.get("mes_participation_share_15", 0.10),
        "mes_participation_share_15_rank252": overrides.get(
            "mes_participation_share_15_rank252", 0.0
        ),
        "nq_return_ticks_15": overrides.get("nq_return_ticks_15", 0.0),
    }
    return pd.Series(row)
