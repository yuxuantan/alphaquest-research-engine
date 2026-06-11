from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


SCID_HEADER_SIZE = 56
SCID_RECORD_SIZE = 40
SCID_EPOCH = "1899-12-30T00:00:00"

SCID_RECORD_DTYPE = np.dtype(
    [
        ("scid_datetime_us", "<i8"),
        ("open", "<f4"),
        ("high", "<f4"),
        ("low", "<f4"),
        ("close", "<f4"),
        ("num_trades", "<u4"),
        ("volume", "<u4"),
        ("bid_volume", "<u4"),
        ("ask_volume", "<u4"),
    ]
)

SCID_ARROW_SCHEMA = pa.schema(
    [
        ("scid_datetime_us", pa.int64()),
        ("open", pa.float32()),
        ("high", pa.float32()),
        ("low", pa.float32()),
        ("close", pa.float32()),
        ("num_trades", pa.uint32()),
        ("volume", pa.uint32()),
        ("bid_volume", pa.uint32()),
        ("ask_volume", pa.uint32()),
    ]
)


def main() -> None:
    args = parse_args()
    source = args.source
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(source.glob("*.scid")) if source.is_dir() else [source]
    if not files:
        raise SystemExit(f"No .scid files found in {source}")

    for index, path in enumerate(files, start=1):
        out_path = output_dir / f"{path.stem}.parquet"
        if out_path.exists() and not args.force:
            print(f"[{index}/{len(files)}] skip existing {out_path}", flush=True)
            continue
        print(f"[{index}/{len(files)}] convert {path} -> {out_path}", flush=True)
        convert_file(
            path,
            out_path,
            rows_per_group=args.rows_per_group,
            compression=args.compression,
            compression_level=args.compression_level,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Sierra Chart .scid intraday files to compressed Parquet."
    )
    parser.add_argument("source", type=Path, help="A .scid file or directory of .scid files.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for one Parquet file per input contract.",
    )
    parser.add_argument(
        "--rows-per-group",
        type=int,
        default=1_000_000,
        help="Parquet row group size. Default: 1,000,000.",
    )
    parser.add_argument(
        "--compression",
        default="zstd",
        help="Parquet compression codec. Default: zstd.",
    )
    parser.add_argument(
        "--compression-level",
        type=int,
        default=3,
        help="Parquet compression level when supported. Default: 3.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Parquet files.",
    )
    return parser.parse_args()


def convert_file(
    path: Path,
    out_path: Path,
    *,
    rows_per_group: int,
    compression: str,
    compression_level: int | None,
) -> None:
    header = read_scid_header(path)
    row_count = header["row_count"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = SCID_ARROW_SCHEMA.with_metadata(
        {
            "source_format": "sierra_scid",
            "source_file": path.name,
            "source_size_bytes": str(path.stat().st_size),
            "source_header_size": str(header["header_size"]),
            "source_record_size": str(header["record_size"]),
            "source_version": str(header["version"]),
            "scid_datetime_epoch": SCID_EPOCH,
            "converted_at_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    records = np.memmap(
        path,
        dtype=SCID_RECORD_DTYPE,
        mode="r",
        offset=SCID_HEADER_SIZE,
        shape=(row_count,),
    )

    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    writer = pq.ParquetWriter(
        tmp_path,
        schema=schema,
        compression=compression,
        compression_level=compression_level,
        use_dictionary=False,
    )
    try:
        for start in range(0, row_count, rows_per_group):
            stop = min(start + rows_per_group, row_count)
            table = records_to_table(records[start:stop], schema)
            writer.write_table(table, row_group_size=rows_per_group)
    finally:
        writer.close()

    tmp_path.replace(out_path)
    print(
        f"    rows={row_count:,} parquet={out_path.stat().st_size / (1024 ** 3):.3f} GiB",
        flush=True,
    )


def read_scid_header(path: Path) -> dict[str, int]:
    size = path.stat().st_size
    with path.open("rb") as handle:
        header = handle.read(SCID_HEADER_SIZE)
    if len(header) != SCID_HEADER_SIZE:
        raise ValueError(f"{path} is too small to be a Sierra .scid file")
    if header[:4] != b"SCID":
        raise ValueError(f"{path} does not start with SCID magic bytes")

    header_size = int.from_bytes(header[4:8], "little")
    record_size = int.from_bytes(header[8:12], "little")
    version = int.from_bytes(header[12:16], "little")
    if header_size != SCID_HEADER_SIZE:
        raise ValueError(f"{path} has unsupported header size {header_size}")
    if record_size != SCID_RECORD_SIZE:
        raise ValueError(f"{path} has unsupported record size {record_size}")
    body_size = size - header_size
    if body_size < 0 or body_size % record_size:
        raise ValueError(f"{path} size is not aligned to {record_size}-byte records")
    return {
        "header_size": header_size,
        "record_size": record_size,
        "version": version,
        "row_count": body_size // record_size,
    }


def records_to_table(records: np.ndarray, schema: pa.Schema) -> pa.Table:
    return pa.Table.from_arrays(
        [pa.array(records[name], type=schema.field(name).type) for name in SCID_RECORD_DTYPE.names],
        schema=schema,
    )


if __name__ == "__main__":
    main()
