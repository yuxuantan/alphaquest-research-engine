from propstack.utils.progress import progress_bar


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
