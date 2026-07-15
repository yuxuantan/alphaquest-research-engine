from alphaquest.maintenance.code_catalog import generate_code_views


def test_code_catalog_groups_tools_and_tests_without_moving_them(tmp_path):
    tools = tmp_path / "tools"
    tests = tmp_path / "tests"
    tools.mkdir()
    tests.mkdir()
    (tools / "build_cache.py").write_text('"""Build a cache."""\n', encoding="utf-8")
    (tests / "test_backtest_engine.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    counts = generate_code_views(project_root=tmp_path)

    assert counts == {"tools": 1, "tests": 1}
    assert "data_build" in (tmp_path / "views" / "code" / "tools" / "index.csv").read_text(encoding="utf-8")
    assert "backtest" in (tmp_path / "views" / "code" / "tests" / "index.csv").read_text(encoding="utf-8")
