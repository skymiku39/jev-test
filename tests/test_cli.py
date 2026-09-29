from __future__ import annotations

import json

from laya_flow.cli import main


def test_laya_only_outputs_only_the_laya_response(capsys) -> None:
    assert main(["英雄聯盟的大亂鬥是什麼？", "--laya-only"]) == 0

    output = json.loads(capsys.readouterr().out)

    assert set(output) == {"answers", "model", "provider"}
    assert output["provider"] == "fixture_laya"
