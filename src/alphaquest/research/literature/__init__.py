"""Offline canonical pre-hypothesis literature research layer."""

from alphaquest.research.literature.contracts import *  # noqa: F403
from alphaquest.research.literature.emission import emit_prepared, prepare_emission, reconcile_emission
from alphaquest.research.literature.store import LiteratureStore

__all__ = ["LiteratureStore", "emit_prepared", "prepare_emission", "reconcile_emission"]
