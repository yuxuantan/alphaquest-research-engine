from __future__ import annotations

from types import MappingProxyType

import pytest

from alphaquest.research.edge_backlog import EdgeBacklogStore
from alphaquest.research.edge_backlog_taxonomy import (
    bundled_taxonomy_root,
    load_taxonomy_catalog,
)


_TEST_TAXONOMY_CATALOG = MappingProxyType(load_taxonomy_catalog(bundled_taxonomy_root()))


@pytest.fixture(autouse=True)
def _isolated_edge_backlog_taxonomy_injection(request, monkeypatch):
    """Keep ephemeral test repositories independent of production taxonomy paths."""

    if not request.node.path.name.startswith("test_edge_backlog"):
        yield
        return
    if request.node.get_closest_marker("production_taxonomy") is None:
        monkeypatch.setattr(
            EdgeBacklogStore,
            "_read_taxonomy_catalog_snapshot",
            lambda _self: _TEST_TAXONOMY_CATALOG,
        )
    yield
