from laya_flow.rules import parse_rules


def test_rules_are_deterministic_and_resolve_known_game_aliases() -> None:
    first = parse_rules("英雄聯盟的大亂鬥是什麼？")
    second = parse_rules("英雄聯盟的大亂鬥是什麼？")

    assert first == second
    assert first["primary"] == "game_info"
    assert first["entities"][0]["id"] == "game.league_of_legends"
    assert first["search_profiles"] == ["game_official_info"]
    assert "web_search" in first["rule_based_needs"]


def test_rules_keep_live_title_separate_from_transcript_activity() -> None:
    title = parse_rules("現在直播標題是什麼？")
    activity = parse_rules("主播現在在做什麼？")

    assert title["primary"] == "live_now"
    assert "live_state" in title["rule_based_needs"]
    assert "transcript" in title["policy_excluded_needs"]
    assert activity["primary"] == "live_now"
    assert "transcript" in activity["needs"]
    assert "transcript" not in activity["policy_excluded_needs"]


def test_unknown_named_definition_uses_general_fact_route() -> None:
    result = parse_rules("花田回音是啥？")

    assert result["primary"] == "world_fact"
    assert result["search_profiles"] == ["general_fact"]
    assert "web_search" in result["needs"]
