from __future__ import annotations

import pandas as pd
import pytest

from propstack.data.es_mes_flow_divergence import build_es_mes_flow_divergence_cache


def _write_cache(path, symbol: str, signed: list[int], large20_signed: list[int]) -> None:
    rows = []
    for index, (signed_volume, large_signed) in enumerate(zip(signed, large20_signed, strict=True)):
        timestamp = pd.Timestamp("2025-06-10 09:30:00") + pd.Timedelta(minutes=index)
        rows.append(
            {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "contract_symbol": f"{symbol}M5",
                "open": 6000.0 + index,
                "high": 6001.0 + index,
                "low": 5999.0 + index,
                "close": 6000.5 + index,
                "volume": 10,
                "signed_volume": signed_volume,
                "buy_volume": 5 + max(signed_volume, 0),
                "sell_volume": 5 + max(-signed_volume, 0),
                "large20_signed_volume": large_signed,
                "large20_volume": 5,
                "trades": 4,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_build_es_mes_flow_divergence_cache_uses_completed_aligned_windows(tmp_path):
    es_csv = tmp_path / "es.csv"
    mes_csv = tmp_path / "mes.csv"
    out_csv = tmp_path / "out.csv"
    _write_cache(es_csv, "ES", [4, -2, 6], [1, 1, 3])
    _write_cache(mes_csv, "MES", [-2, -4, 2], [-1, -3, 1])

    out = build_es_mes_flow_divergence_cache(
        es_csv=es_csv,
        mes_csv=mes_csv,
        output_csv=out_csv,
        windows=[2],
        large_trade_sizes=[20],
        price_cap_ticks=[16],
        tick_size=0.25,
        min_period_fraction=1.0,
    )

    assert out_csv.exists()
    assert out["symbol"].unique().tolist() == ["ES"]
    assert pd.isna(out.loc[0, "es_minus_mes_imbalance_2"])
    assert out.loc[1, "es_trade_orderflow_imbalance_2"] == pytest.approx(0.1)
    assert out.loc[1, "mes_trade_orderflow_imbalance_2"] == pytest.approx(-0.3)
    assert out.loc[1, "es_minus_mes_imbalance_2"] == pytest.approx(0.4)
    assert out.loc[2, "es_minus_mes_imbalance_2"] == pytest.approx(0.3)
    assert out.loc[1, "es_minus_mes_return_ticks_2"] == pytest.approx(0.0)
    assert out.loc[1, "mes_minus_es_return_ticks_2"] == pytest.approx(0.0)
    assert out.loc[1, "mes_trade_orderflow_large20_imbalance_2"] == pytest.approx(-0.4)
    assert out.loc[1, "mes_large20_imbalance_es_return_lte_16_2"] == pytest.approx(-0.4)
