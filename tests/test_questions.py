from laya_flow.questions import build_typed_questions


def test_laya_batch_is_bounded_and_policy_owned_fields_are_absent() -> None:
    questions = build_typed_questions()

    assert questions["primary"]["type"] == "choice"
    assert questions["tag_game_info"]["type"] == "noul"
    assert questions["need_web_search"]["type"] == "noul"
    assert "need_evidence_contract" not in questions
    assert "need_reference_resolution" not in questions
    assert "need_runtime_identity" not in questions
