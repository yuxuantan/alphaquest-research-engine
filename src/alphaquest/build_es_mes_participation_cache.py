from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from alphaquest.data.es_mes_participation import build_es_mes_participation_features


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ES/MES participation crowding feature cache.")
    parser.add_argument("--input-csv", required=True, help="Aligned ES/MES 1-minute feature CSV.")
    parser.add_argument("--out-csv", required=True, help="Output CSV path.")
    parser.add_argument("--windows", nargs="+", type=int, default=[15, 30, 60])
    parser.add_argument("--rank-window", type=int, default=252)
    parser.add_argument("--rank-min-periods", type=int, default=60)
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--mes-contract-ratio", type=float, default=10.0)
    args = parser.parse_args()

    source = pd.read_csv(args.input_csv)
    features = build_es_mes_participation_features(
        source,
        windows=tuple(args.windows),
        rank_window=args.rank_window,
        rank_min_periods=args.rank_min_periods,
        tick_size=args.tick_size,
        mes_contract_ratio=args.mes_contract_ratio,
    )
    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(out, index=False)
    print(out)
    print(f"rows={len(features)}")
    print(f"first_timestamp={features['timestamp'].min() if len(features) else None}")
    print(f"last_timestamp={features['timestamp'].max() if len(features) else None}")


if __name__ == "__main__":
    main()
