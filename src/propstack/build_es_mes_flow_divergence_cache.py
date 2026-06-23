from __future__ import annotations

import argparse

from propstack.data.es_mes_flow_divergence import build_es_mes_flow_divergence_cache


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an ES trading cache with completed MES-vs-ES flow-divergence features."
    )
    parser.add_argument("--es-csv", required=True, help="ES 1-minute trade-orderflow cache CSV or Parquet.")
    parser.add_argument("--mes-csv", required=True, help="MES 1-minute trade-orderflow cache CSV or Parquet.")
    parser.add_argument("--out-csv", required=True, help="Output ES trading cache CSV.")
    parser.add_argument("--windows", default="3,5,15,30,60", help="Comma-separated completed-bar windows.")
    parser.add_argument("--large-trade-sizes", default="10,20", help="Comma-separated large-trade thresholds.")
    parser.add_argument("--price-cap-ticks", default="8,16,24", help="Comma-separated market return caps.")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--min-period-fraction", type=float, default=1.0)
    parser.add_argument("--market-symbol", default="ES", help="Tradable market symbol to write into the output cache.")
    parser.add_argument("--market-prefix", default="es", help="Feature prefix for the tradable market, e.g. es or nq.")
    args = parser.parse_args()

    build_es_mes_flow_divergence_cache(
        es_csv=args.es_csv,
        mes_csv=args.mes_csv,
        output_csv=args.out_csv,
        windows=_csv_ints(args.windows),
        large_trade_sizes=_csv_ints(args.large_trade_sizes),
        price_cap_ticks=_csv_ints(args.price_cap_ticks),
        tick_size=args.tick_size,
        min_period_fraction=args.min_period_fraction,
        market_symbol=args.market_symbol,
        market_prefix=args.market_prefix,
        status_callback=print,
    )


def _csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    main()
