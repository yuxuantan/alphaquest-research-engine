from tools.check_docs_links import DEFAULT_PATHS, _target_available_in_clean_checkout, validate_links


def test_docs_link_validator_detects_missing_local_target(tmp_path):
    document = tmp_path / "README.md"
    document.write_text("[missing](not-there.md)\n", encoding="utf-8")

    assert validate_links([str(document)]) == [f"{document}: missing local target not-there.md"]


def test_curated_repository_documentation_links_are_valid():
    assert validate_links(DEFAULT_PATHS) == []


def test_clean_checkout_validation_rejects_existing_untracked_targets(tmp_path):
    target = tmp_path / "generated" / "report.md"
    target.parent.mkdir()
    target.write_text("local only\n", encoding="utf-8")

    assert not _target_available_in_clean_checkout(
        target,
        repository_root=tmp_path,
        tracked_paths=frozenset(),
    )
    assert _target_available_in_clean_checkout(
        target,
        repository_root=tmp_path,
        tracked_paths=frozenset({target}),
    )
