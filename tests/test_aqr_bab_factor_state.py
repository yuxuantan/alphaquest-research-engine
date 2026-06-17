from __future__ import annotations

from zipfile import ZipFile

import pandas as pd

from propstack.strategy_modules.entry.aqr_bab_factor_state import AqrBabFactorStateEntry
from tools.build_es_aqr_bab_features import build_features


def test_aqr_bab_low_rank_signal_uses_completed_bar(tmp_path):
    feature_csv = tmp_path / "bab.csv"
    feature_csv.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,observation_age_days,"
        "bab_usa_return_1d,bab_usa_return_rank_252\n"
        "2026-01-05,2025-11-20,2025-11-21,45,46,-0.01,0.12\n",
        encoding="utf-8",
    )
    entry = AqrBabFactorStateEntry(
        {
            "feature_csv": str(feature_csv),
            "setup_mode": "low_bab_rebound_long",
            "rank_column": "bab_usa_return_rank_252",
            "value_column": "bab_usa_return_1d",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "bab_rank_threshold": 0.2,
        }
    )
    signal = entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00"), 0)
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["bab_observation_date"] == "2025-11-20"
    assert signal.report_fields["publication_lag_calendar_days"] == 45.0


def test_aqr_bab_two_sided_and_duplicate_day_signal(tmp_path):
    feature_csv = tmp_path / "bab.csv"
    feature_csv.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,observation_age_days,"
        "bab_usa_return_1d,bab_usa_return_rank_252\n"
        "2026-01-05,2025-11-20,2025-11-21,45,46,0.01,0.90\n"
        "2026-01-06,2025-11-21,2025-11-22,45,46,0.00,0.50\n",
        encoding="utf-8",
    )
    entry = AqrBabFactorStateEntry(
        {
            "feature_csv": str(feature_csv),
            "setup_mode": "two_sided_bab_state",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "bab_rank_threshold": 0.2,
        }
    )
    signal = entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00"), 0)
    assert signal is not None
    assert signal.direction == "short"
    assert entry.on_bar_close(_bar("2026-01-05 10:00:00-05:00"), 0) is None
    assert entry.on_bar_close(_bar("2026-01-06 09:59:00-05:00"), 0) is None


def test_aqr_bab_ignores_non_rth_and_missing_feature(tmp_path):
    feature_csv = tmp_path / "bab.csv"
    feature_csv.write_text(
        "session_date,observation_date,availability_cutoff,publication_lag_calendar_days,observation_age_days,"
        "bab_usa_return_1d,bab_usa_return_rank_252\n"
        "2026-01-05,2025-11-20,2025-11-21,45,46,-0.01,0.12\n",
        encoding="utf-8",
    )
    entry = AqrBabFactorStateEntry(
        {
            "feature_csv": str(feature_csv),
            "setup_mode": "low_bab_rebound_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "bab_rank_threshold": 0.2,
        }
    )
    assert entry.on_bar_close(_bar("2026-01-05 09:59:00-05:00", is_rth=False), 0) is None
    assert entry.on_bar_close(_bar("2026-01-06 09:59:00-05:00"), 0) is None


def test_aqr_bab_feature_builder_uses_publication_lag(tmp_path):
    es_path = tmp_path / "bars.parquet"
    aqr_path = tmp_path / "bab.xlsx"
    output = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2026-01-05 09:30:00"), "close": 5000.0},
            {"timestamp": pd.Timestamp("2026-01-06 09:30:00"), "close": 5001.0},
        ]
    ).to_parquet(es_path)
    _write_minimal_aqr_workbook(aqr_path)
    features = build_features(es_path, aqr_path, output, publication_lag_calendar_days=45)
    first = features.iloc[0]
    second = features.iloc[1]
    assert first["observation_date"] == "2025-11-21"
    assert second["observation_date"] == "2025-11-21"
    assert first["observation_age_days"] == 45
    assert second["observation_age_days"] == 46


def _bar(timestamp: str, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": 5000.0,
            "high": 5001.0,
            "low": 4999.0,
            "close": 5000.5,
        }
    )


def _write_minimal_aqr_workbook(path):
    rows = [
        {"A": "AQR Capital Management"},
        {"A": "DATE", "Y": "USA"},
        {"A": "11/20/2025", "Y": "-0.01"},
        {"A": "11/21/2025", "Y": "0.02"},
    ]
    shared = []
    for row in rows:
        for value in row.values():
            if value not in shared:
                shared.append(value)
    shared_index = {value: idx for idx, value in enumerate(shared)}
    with ZipFile(path, "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="BAB Factors" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + "".join(f"<si><t>{value}</t></si>" for value in shared)
            + "</sst>",
        )
        sheet_rows = []
        for idx, row in enumerate(rows, start=1):
            cells = []
            for col, value in row.items():
                cells.append(f'<c r="{col}{idx}" t="s"><v>{shared_index[value]}</v></c>')
            sheet_rows.append(f'<row r="{idx}">' + "".join(cells) + "</row>")
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            + "".join(sheet_rows)
            + "</sheetData></worksheet>",
        )
