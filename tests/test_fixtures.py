from __future__ import annotations

import json
from pathlib import Path

from laya_flow.pipeline import run_pipeline


def test_golden_cases_cover_the_three_stage_flow() -> None:
    cases = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "cases.json").read_text(encoding="utf-8")
    )

    for case in cases:
        merged = run_pipeline(case["question"])["merged"]
        if "expected_primary" in case:
            assert merged["primary"] == case["expected_primary"], case["id"]
        if "expected_tag" in case:
            assert case["expected_tag"] in merged["tags"], case["id"]
        if "expected_profile" in case:
            assert case["expected_profile"] in merged["search_profiles"], case["id"]
        if "expected_need" in case:
            assert case["expected_need"] in merged["needs"], case["id"]
