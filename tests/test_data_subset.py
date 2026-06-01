import pandas as pd

from propstack.data.subset import apply_data_subset


def test_apply_data_subset_filters_by_session_date():
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01 08:30",
                    "2024-01-02 08:30",
                    "2024-01-03 08:30",
                ],
                utc=True,
            ),
            "session_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "close": [1.0, 2.0, 3.0],
        }
    )

    filtered = apply_data_subset(
        data,
        {
            "start_date": "2024-01-02",
            "end_date": "2024-01-03",
        },
    )

    assert filtered["session_date"].tolist() == ["2024-01-02", "2024-01-03"]
    assert filtered.index.tolist() == [0, 1]
