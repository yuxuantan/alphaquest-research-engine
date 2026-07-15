import pandas as pd

from alphaquest.data.subset import apply_data_subset


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


def test_apply_data_subset_filters_by_session_label_and_rth_only():
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02 08:30",
                    "2024-01-02 09:30",
                    "2024-01-02 17:00",
                ],
                utc=True,
            ),
            "session_date": ["2024-01-02", "2024-01-02", "2024-01-03"],
            "session_label": ["closed", "RTH", "ETH"],
            "is_rth": [False, True, False],
            "close": [1.0, 2.0, 3.0],
        }
    )

    by_label = apply_data_subset(data, {"session_labels": ["RTH"]})
    by_flag = apply_data_subset(data, {"rth_only": True})

    assert by_label["close"].tolist() == [2.0]
    assert by_flag["close"].tolist() == [2.0]
