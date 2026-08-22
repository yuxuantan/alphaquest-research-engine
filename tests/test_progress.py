from alphaquest.utils.progress import listen_for_progress, progress_bar


def test_progress_bar_force_outputs_repeated_same_percent_updates(capsys):
    progress = progress_bar(200, "walk-forward windows")

    progress.update(0, force=True)
    progress.update(1, force=True)
    progress.update(2, force=True)

    out = capsys.readouterr().out
    assert "0/200" in out
    assert "1/200" in out
    assert "2/200" in out


def test_progress_bar_can_show_elapsed_and_remaining_time(capsys):
    times = iter([0.0, 0.0, 10.0])
    progress = progress_bar(10, "walk-forward windows", show_timing=True, clock=lambda: next(times))

    progress.update(0, force=True)
    progress.update(5, force=True)

    out = capsys.readouterr().out
    assert "0/10" in out
    assert "elapsed 00:00 | remaining --" in out
    assert "5/10" in out
    assert "elapsed 00:10 | remaining 00:10" in out


def test_progress_bar_can_show_detail_text(capsys):
    progress = progress_bar(2, "walk-forward windows")

    progress.update(1, force=True, detail="last OOS MAR=2.00 CAGR=4.00% DD=2.00% NP=100.00")

    out = capsys.readouterr().out
    assert "1/2" in out
    assert "last OOS MAR=2.00 CAGR=4.00% DD=2.00% NP=100.00" in out


def test_progress_bar_can_forward_real_counters_to_structured_listener(capsys):
    updates = []

    with listen_for_progress(updates.append):
        progress = progress_bar(4, "core grid")
        progress.update(1, detail="configuration 1")

    assert updates == [
        {
            "label": "core grid",
            "completed": 1,
            "total": 4,
            "percent": 25.0,
            "detail": "configuration 1",
        }
    ]


def test_progress_bar_forwards_worker_counts_to_structured_listener(capsys):
    updates = []

    with listen_for_progress(updates.append):
        progress = progress_bar(100, "core grid")
        progress.update(
            17,
            force=True,
            detail="configuration 17/100 · 3 active workers",
            active_workers=3,
            expected_workers=3,
        )

    assert updates[0]["completed"] == 17
    assert updates[0]["total"] == 100
    assert updates[0]["active_workers"] == 3
    assert updates[0]["expected_workers"] == 3
