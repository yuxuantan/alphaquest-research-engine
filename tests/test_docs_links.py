from tools.check_docs_links import DEFAULT_PATHS, validate_links


def test_docs_link_validator_detects_missing_local_target(tmp_path):
    document = tmp_path / "README.md"
    document.write_text("[missing](not-there.md)\n", encoding="utf-8")

    assert validate_links([str(document)]) == [f"{document}: missing local target not-there.md"]


def test_curated_repository_documentation_links_are_valid():
    assert validate_links(DEFAULT_PATHS) == []
