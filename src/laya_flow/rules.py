"""Pure deterministic rule parser used as the first pipeline stage."""

from __future__ import annotations

import re
from typing import Any

from .policy import (
    attach_query_plan,
    is_contextual_followup,
    is_game_fact_question,
    is_punctuation_only_question,
    is_runtime_identity_question,
)

CHAOS_MARKER = "🌀"

_SYS_TEST = re.compile(r"ping|流程再確認|流程確認|ASK流程|登入測試|系統測試|用一個詞|用兩個字|只回答|ECHO", re.I)
_NOISE = re.compile(r"^[…⋯.．\s]+|�")
_SCOUT = re.compile(r"童子軍")
_PEAK = re.compile(r"peak|爬山", re.I)
_SUMMIT = re.compile(r"登頂|先登頂")
_SLACK = re.compile(r"摸魚")
_LIVE_TITLE = re.compile(
    r"(?:直播|開台).{0,8}(?:標題|遊戲名稱)|(?:現在|目前|當前).{0,8}直播.{0,6}(?:標題|遊戲)",
    re.I,
)
_LIVE_NOW = re.compile(r"(主播|你).{0,8}(在做|在幹|幹嘛|在玩)|現在在|永久下線|在不在", re.I)
_RECAP = re.compile(r"剛才|剛剛|今天.{0,6}(發生|講了|討論)|聊天.{0,4}(討論|什麼)|我剛剛說")
_WHO = re.compile(r"是誰|誰是|小甜甜|自我介紹|你是誰")
_TECH = re.compile(r"框架|物件導向|函式|NPU|Hailo|OOP|程式|前端|後端|版本|Ollama|num_ctx|設定|安裝|部署", re.I)
_BOT = re.compile(r"你能做什麼|你會做什麼|有什麼功能")
_SOCIAL = re.compile(r"^(你好|早安|午安|晚安|嗨|哈囉|安安)\b|還記得我嗎")
_OPS = re.compile(r"台規|劇透|開播|星辰大海|征途是星辰大海|twitch|連續觀看", re.I)
_WORLD_FACT = re.compile(
    r"天氣|氣象|氣溫|溫度|幾度|降雨|下雨|天候|體感|預報|幾點|日期|幾號|匯率|股票|股價|收盤價|"
    r"盤中|漲跌|成交量|股市|股票代號|公司|企業|營收|財報|主要業務|公司資料|維基百科|維基|wiki|百科|"
    r"新聞|時事|國際局勢|評價|評論|評測|心得|口碑|評分|賽果|比賽|比賽結果|賽事|賽程|球隊|棒球|籃球|足球|最新|近期|昨天|昨日|今天|活動|展覽|演唱|演出|行程|在哪裡|哪裏",
    re.I,
)
_COMMERCE = re.compile(r"多少錢|賣多少|價格|價錢|售價|購買|買得到|商品|商店|折扣|付款|訂閱費|費用", re.I)
_GAME = re.compile(r"好玩|遊戲|dlc|Potion\s*Craft|這款", re.I)
_LEAGUE_OF_LEGENDS = re.compile(r"英雄聯盟|League\s+of\s+Legends|\bLoL\b", re.I)
_FOLLOW = re.compile(r"^那|所以|我剛剛說|我的意思是|哈哈所以")
_OPINION = re.compile(r"太難|超聰明|喜歡什麼|老人味|覺得")

_ALIASES = (
    (re.compile(r"Potion\s*Craft|藥水工藝", re.I), "game.potion_craft", "game", "Potion Craft"),
    (re.compile(r"Hades\s*II|Hades 2", re.I), "game.hades_2", "game", "Hades II"),
    (re.compile(r"\bPEAK\b|童子軍", re.I), "game.peak", "game", "Peak"),
    (_LEAGUE_OF_LEGENDS, "game.league_of_legends", "game", "League of Legends"),
    (re.compile(r"台積電|臺積電|\bTSMC\b|2330", re.I), "company.tsmc", "company", "TSMC"),
    (re.compile(r"NVIDIA|輝達", re.I), "company.nvidia", "company", "NVIDIA"),
)


def _find_entities(question: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for pattern, entity_id, kind, canonical in _ALIASES:
        match = pattern.search(question)
        if not match:
            continue
        entities.append(
            {
                "mention": match.group(0),
                "id": entity_id,
                "kind": kind,
                "canonical": canonical,
                "confidence": 0.99,
            }
        )
    if any(item["id"] == "game.peak" for item in entities) and "童子軍" in question:
        entities.append(
            {
                "mention": "童子軍",
                "id": "meme.peak_scout",
                "kind": "meme",
                "canonical": "Peak scout",
                "confidence": 0.99,
            }
        )
    return entities


def parse_rules(question: str) -> dict[str, Any]:
    """Parse a question without reading any external state."""

    q = str(question or "").strip()
    primary = "ops_channel"
    secondary: list[str] = []
    flags: list[str] = []
    slots: dict[str, Any] = {}
    marker: str | None = None
    confidence = 0.55
    punctuation_noise = is_punctuation_only_question(q)
    entities = _find_entities(q)

    if punctuation_noise:
        primary, confidence = "noise", 0.9
    elif _SYS_TEST.search(q) or _NOISE.search(q) or q in {"… 即", "..."}:
        primary, confidence, marker = "noise", 0.9, CHAOS_MARKER
    elif is_game_fact_question(q, {"entities": entities}):
        primary, confidence = "game_info", 0.95
    elif _SCOUT.search(q) or _SUMMIT.search(q) or _SLACK.search(q) or _PEAK.search(q) or any(item["id"] == "meme.peak_scout" for item in entities):
        primary, confidence = "session_banter", 0.85
        if re.search(r"阿吉|豆腐|誰", q):
            secondary = ["person_relation"]
            slots["subject"] = "阿吉" if "阿吉" in q else "豆腐" if "豆腐" in q else "unknown"
    elif _LIVE_TITLE.search(q):
        primary, confidence = "live_now", 0.9
    elif _LIVE_NOW.search(q):
        primary, confidence = "live_now", 0.8
    elif _RECAP.search(q):
        primary, confidence = "live_recap", 0.88
    elif is_runtime_identity_question(q):
        primary, confidence = "bot_meta", 0.95
    elif _BOT.search(q):
        primary, confidence = "bot_meta", 0.8
    elif _WHO.search(q):
        primary, confidence = "person_relation", 0.8
        if "小甜甜" in q:
            slots["subject"] = "小甜甜"
        elif "阿吉" in q:
            slots["subject"] = "阿吉"
    elif _TECH.search(q):
        primary, confidence = "howto_tech", 0.75
    elif _WORLD_FACT.search(q):
        primary, confidence = "world_fact", 0.8
    elif _COMMERCE.search(q):
        primary, confidence = "commerce", 0.8
    elif is_contextual_followup(q):
        primary, confidence = "session_banter", 0.8
    elif _SOCIAL.search(q):
        primary, confidence = "social", 0.8
    elif _OPS.search(q):
        primary, confidence = "ops_channel", 0.7
    elif _GAME.search(q):
        primary, confidence = "game_info", 0.7
    else:
        primary, confidence = "ops_channel", 0.4

    if _FOLLOW.search(q):
        flags.append("follow_up")
    if _OPINION.search(q):
        flags.append("opinion")
    if re.search(r"吉胖胖", q):
        flags.append("sensitive")

    result: dict[str, Any] = {
        "question": q,
        "primary": primary,
        "secondary": secondary[:1],
        "flags": list(dict.fromkeys(flags)),
        "slots": slots,
        "entities": entities,
        "marker": marker,
        "parser": "rules_v1",
        "confidence": confidence,
        "punctuation_noise": punctuation_noise,
    }
    return attach_query_plan(q, result)


def format_parse_section(result: dict[str, Any]) -> str:
    lines = [
        f"- 題型：{result.get('primary')}"
        + (f"（+ {', '.join(result.get('secondary') or [])}）" if result.get("secondary") else "")
    ]
    if result.get("flags"):
        lines.append(f"- 旗標：{', '.join(result['flags'])}")
    entities = result.get("entities") or []
    if entities:
        lines.append("- 實體：" + "；".join(f"{e.get('id')}({e.get('mention')})" for e in entities[:8]))
    if result.get("marker"):
        lines.append(f"- 標記：{result['marker']}（混亂／煙測；仍請作答）")
    return "\n".join(lines)
