from __future__ import annotations

import sys

from alphaquest import run_campaign_stages


def test_legacy_stage_runner_prints_explicit_research_verdict(monkeypatch, capsys):
    monkeypatch.setattr(
        run_campaign_stages,
        "run_campaign_stage_tests",
        lambda *args, **kwargs: {
            "output_dir": "research/evidence/runs/demo/v01/ES/run1",
            "passed": False,
            "research_verdict": "NEEDS MANUAL REVIEW",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["alphaquest.run_campaign_stages", "--config", "config.yaml", "--no-acceptance"],
    )

    run_campaign_stages.main()

    assert capsys.readouterr().out.splitlines() == [
        "research/evidence/runs/demo/v01/ES/run1",
        "NEEDS MANUAL REVIEW",
    ]
