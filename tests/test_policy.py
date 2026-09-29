from laya_flow.policy import build_query_plan, merge_laya_decision
from laya_flow.rules import parse_rules


def test_laya_cannot_remove_rule_or_policy_needs() -> None:
    question = "這款遊戲台灣多少錢？"
    parsed = parse_rules(question)
    result = merge_laya_decision(
        question,
        parsed,
        {
            "provider": "laya_local",
            "model": "fixture-laya",
            "answers": {
                "primary": {"choice": "social", "confidence": 0.99},
                "tag_social": {"noul": 0.99},
                "need_web_search": {"noul": 0.0},
                "need_evidence_contract": {"noul": 0.0}
            },
        },
    )

    assert "web_search" in result["needs"]
    assert "evidence_contract" in result["policy_required_needs"]
    assert "evidence_contract" in result["needs"]
    assert "commerce" in result["tags"]
    assert result["search_profiles"] == ["store_price_tw"]


def test_three_way_union_filters_unknown_laya_values() -> None:
    question = "你好"
    parsed = parse_rules(question)
    result = build_query_plan(
        question,
        parsed,
        laya_tags=["social", "not_an_intent"],
        laya_needs=["live_state", "not_a_need"],
        policy_required_needs=["channel_knowledge"],
    )

    assert result["laya_tags"] == ["social"]
    assert result["laya_needs"] == ["live_state"]
    assert result["policy_required_needs"] == ["channel_knowledge"]
    assert set(result["needs"]) == {"live_state", "channel_knowledge"}


def test_high_confidence_rule_owns_named_game_fact() -> None:
    question = "英雄聯盟的大亂鬥是什麼？"
    result = merge_laya_decision(
        question,
        parse_rules(question),
        {
            "answers": {
                "primary": {"choice": "social", "confidence": 0.99},
                "tag_social": {"noul": 0.99},
                "need_recent_chat": {"noul": 0.99},
            }
        },
    )

    assert result["primary"] == "game_info"
    assert result["search_profiles"] == ["game_official_info"]
    assert "recent_chat" in result["needs"]
    assert "recent_chat" in result["policy_excluded_needs"]


def test_broad_laya_live_recap_does_not_open_transcript_for_title() -> None:
    question = "現在直播標題是什麼？"
    result = merge_laya_decision(
        question,
        parse_rules(question),
        {
            "answers": {
                "primary": {"choice": "live_recap", "confidence": 0.99},
                "tag_live_recap": {"noul": 0.99},
                "need_transcript": {"noul": 0.99},
            }
        },
    )

    assert "transcript" in result["needs"]
    assert "transcript" in result["policy_excluded_needs"]
    assert result["search_profiles"] == []


def test_contextual_followup_only_keeps_scene_context_actionable() -> None:
    question = "你覺得呢？"
    result = merge_laya_decision(
        question,
        parse_rules(question),
        {
            "answers": {
                "primary": {"choice": "ops_channel", "confidence": 0.99},
                "tag_ops_channel": {"noul": 0.99},
                "need_web_search": {"noul": 0.99},
                "need_channel_knowledge": {"noul": 0.99},
            }
        },
    )

    assert result["primary"] == "session_banter"
    assert "recent_chat" in result["needs"]
    assert "transcript" in result["needs"]
    assert "web_search" in result["policy_excluded_needs"]
    assert "channel_knowledge" in result["policy_excluded_needs"]
    assert result["search_profiles"] == []


def test_invalid_typed_response_degrades_to_rules_without_policy_loss() -> None:
    question = "這款遊戲台灣多少錢？"
    result = merge_laya_decision(question, parse_rules(question), {"answers": []})

    assert result["classifier"]["used"] is False
    assert result["classifier"]["reason"] == "invalid_typed_response"
    assert "evidence_contract" in result["needs"]
