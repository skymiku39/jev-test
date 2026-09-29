from __future__ import annotations

from typing import Any

from laya_flow.laya import ScriptedLayaClient
from laya_flow.pipeline import run_pipeline


def test_pipeline_sends_rule_context_and_the_full_typed_batch() -> None:
    backend = ScriptedLayaClient(
        {
            "answers": {
                "primary": {"choice": "howto_tech", "confidence": 0.95},
                "tag_howto_tech": {"noul": 0.95},
                "need_web_search": {"noul": 0.95},
            }
        }
    )

    result = run_pipeline("如何調整 Ollama 設定？", backend=backend)

    assert result["rule_parse"]["primary"] == "howto_tech"
    assert result["laya_response"]["provider"] == "laya_local"
    assert result["merged"]["classifier"]["used"] is True
    assert result["merged"]["classifier"]["model"] == "fixture-laya"
    assert backend.calls[0]["state"]["rule_parse"]["primary"] == "howto_tech"
    assert "need_web_search" in backend.calls[0]["questions"]


def test_pipeline_fails_safe_when_optional_laya_backend_raises() -> None:
    class BrokenBackend:
        provider = "laya_local"
        model = "broken-fixture"

        def decide(self, **_: Any):
            raise RuntimeError("backend detail must not escape")

    result = run_pipeline("這款遊戲台灣多少錢？", backend=BrokenBackend())

    assert result["laya_response"] is None
    assert result["merged"]["classifier"]["used"] is False
    assert result["merged"]["classifier"]["model"] == "broken-fixture"
    assert result["merged"]["classifier"]["reason"] == "backend_error"
    assert result["merged"]["classifier"]["error_type"] == "RuntimeError"
    assert "evidence_contract" in result["merged"]["needs"]
