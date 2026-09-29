from __future__ import annotations

from laya_flow.laya import LayaSettings, LayaTypedDecisionClient


def test_typed_adapter_adds_local_model_metadata_without_changing_answers() -> None:
    class RawClient:
        settings = LayaSettings(repository="fixture/repo", model="multilingual")
        resolved_revision = "fixture-revision"

        def decide(self, **_: object):
            return {"answers": {"primary": {"choice": "social", "confidence": 0.9}}}, 12.5

        def warmup(self) -> None:
            pass

    client = LayaTypedDecisionClient(RawClient())
    response, elapsed = client.decide(
        state={"question": "嗨"},
        questions={"primary": {"type": "choice"}},
        timeout_seconds=0.5,
    )

    assert elapsed == 12.5
    assert response["answers"]["primary"]["choice"] == "social"
    assert response["provider"] == "laya_local"
    assert response["model"] == "fixture/repo/multilingual"
    assert response["revision"] == "fixture-revision"
