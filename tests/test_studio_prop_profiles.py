from __future__ import annotations

from copy import deepcopy

import pytest

from alphaquest.prop.profiles import list_prop_profiles, resolve_prop_profile
from alphaquest.research.campaign_stages import _wfa_oos_monte_carlo_rules_config


def test_certified_profile_resolves_every_executable_rule_from_confirmed_balance() -> None:
    rules = resolve_prop_profile(
        "configured_local_profile",
        starting_balance=150_000.0,
        max_contracts=2,
        force_flatten_time="15:55:00",
    )

    assert rules["profile_fully_specified"] is True
    assert rules["starting_balance"] == 150_000.0
    assert rules["challenge_profit_target_amount"] == 9_000.0
    assert rules["drawdown_limit_amount"] == 6_000.0
    assert rules["funded_initial_drawdown_floor"] == 144_000.0
    assert rules["max_contracts"] == 2
    assert rules["force_flatten_time"] == "15:55:00"
    assert list_prop_profiles()[0]["profile_id"] == "configured_local_profile"


def test_studio_profile_is_the_monte_carlo_source_not_a_hardcoded_50k_default() -> None:
    rules = resolve_prop_profile(
        "configured_local_profile",
        starting_balance=150_000.0,
        max_contracts=1,
        force_flatten_time="15:55:00",
    )

    resolved = _wfa_oos_monte_carlo_rules_config({"prop_rules": rules}, {})

    assert resolved["starting_balance"] == 150_000.0
    assert resolved["challenge_profit_target_amount"] == 9_000.0
    assert resolved["drawdown_limit_amount"] == 6_000.0


def test_unknown_or_hash_drifted_studio_profiles_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown or uncertified"):
        resolve_prop_profile(
            "typed_but_not_configured",
            starting_balance=50_000.0,
            max_contracts=1,
            force_flatten_time="15:55:00",
        )

    rules = resolve_prop_profile(
        "configured_local_profile",
        starting_balance=50_000.0,
        max_contracts=1,
        force_flatten_time="15:55:00",
    )
    tampered = deepcopy(rules)
    tampered["drawdown_limit_amount"] = 1.0
    with pytest.raises(ValueError, match="hash is missing or stale"):
        _wfa_oos_monte_carlo_rules_config({"prop_rules": tampered}, {})
