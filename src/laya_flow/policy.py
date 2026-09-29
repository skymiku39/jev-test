"""Deterministic routing and the conservative Laya merge policy.

This module is intentionally provider-free.  Laya supplies candidates; this
module decides what the request is allowed to do and which data needs survive.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from .contracts import (
    ALLOWED_NEEDS,
    FLAGS,
    NEED_ORDER,
    PRIMARY_INTENTS,
    clean_strings,
    ordered,
    probability,
)

_COMMERCE = re.compile(
    r"多少錢|賣多少|價格|價錢|售價|購買|買得到|商品|商店|折扣|付款|訂閱費|費用"
)
_PRICE_AMOUNT = re.compile(
    r"(?:Steam|eShop|商店).{0,10}多少|多少.{0,8}(?:Steam|eShop|台幣|台币|(?<!美)元)",
    re.IGNORECASE,
)
_GAME = re.compile(r"遊戲|這款|那款|DLC|好玩", re.IGNORECASE)
_GAME_TITLE = re.compile(
    r"英雄聯盟|League\s+of\s+Legends|\bLoL\b|\bARAM\b|"
    r"Potion\s*Craft|Hades\s*II|\bPEAK\b",
    re.IGNORECASE,
)
_GAME_MODE = re.compile(r"大亂鬥|\bARAM\b", re.IGNORECASE)
_WEATHER = re.compile(
    r"天氣|氣象|氣溫|溫度|幾度|降雨|下雨|天候|體感|預報|"
    r"\bweather\b|\bforecast\b|\btemperature\b|\brain(?:fall)?\b|\bdegrees?\b",
    re.IGNORECASE,
)
_STOCK = re.compile(r"股票|股價|收盤價|盤中|漲跌|成交量|股市|股票代號", re.IGNORECASE)
_STOCK_ENTITY = re.compile(r"股價|收盤|盤中|成交|漲跌|報價", re.IGNORECASE)
_COMPANY = re.compile(r"公司|企業|營收|財報|主要業務|主要做什麼|是做什麼|投資人關係|公司資料|市值")
_KNOWN_COMPANY = re.compile(
    r"台積電|臺積電|\bTSMC\b|\bNVIDIA\b|輝達|\bApple\b|蘋果公司|\bMicrosoft\b|微軟",
    re.IGNORECASE,
)
_WIKI = re.compile(r"維基百科|維基|wiki|百科", re.IGNORECASE)
_NEWS = re.compile(r"新聞|時事|最新消息|國際局勢|最近發生")
_GAME_REVIEW = re.compile(
    r"評價|評論|評測|心得|口碑|評分|好玩(?:嗎)?|值得玩|推薦嗎|怎麼樣|如何|review",
    re.IGNORECASE,
)
_GAME_GUIDE = re.compile(
    r"攻略|怎麼打|打法|怎麼躲|如何躲|躲法|BOSS|boss|任務解法|解法|怎麼玩",
    re.IGNORECASE,
)
_GAME_MECHANIC = re.compile(
    r"有什麼功能|功能是什麼|有什麼用|用途|效果|作用|能力|怎麼使用|如何使用|怎麼用|怎樣用|道具|物品",
    re.IGNORECASE,
)
_GAME_FACT_CUE = re.compile(
    r"類型|平台|玩法|玩什麼|主要在玩|發售|上市|開發商|發行商|特色|內容|是什麼|哪一種遊戲|"
    r"規則|模式|怎麼玩|如何玩|介紹|\bwhat\s+is\b|\brules\b|\bmode\b|\boverview\b",
    re.IGNORECASE,
)
_GAME_ENTITY_FACT_CUE = re.compile(
    r"類型|平台|玩法|玩什麼|主要在玩|發售|上市|開發商|發行商|特色|內容|是什麼遊戲|哪一種遊戲",
    re.IGNORECASE,
)
_TECH = re.compile(
    r"框架|物件導向|函式|NPU|Hailo|OOP|程式|前端|後端|版本|Ollama|num_ctx|設定|安裝|部署",
    re.IGNORECASE,
)
_GENERAL_FACT_CUE = re.compile(
    r"是什麼|是甚麼|是啥|是什麼意思|是啥意思|是誰|為什麼|為何|原因|原理|何時|什麼時候|哪一年|幾年|"
    r"在哪裡|哪裏|多深|多高|多大|介紹|定義|差異|比較|如何運作|歷史|統計|資料來源",
    re.IGNORECASE,
)
_NAMED_DEFINITION_QUESTION = re.compile(
    r"^\s*(?P<subject>[^，。！？?]{2,32}?)\s*(?:是甚麼|是什麼意思|是啥意思|是什麼|是啥|指的是什麼|代表什麼)[？?。！!]*\s*$",
    re.IGNORECASE,
)
_LIVE_RECAP_GAME_CUE = re.compile(r"(?:主播|台主).{0,12}(?:剛才|剛剛).{0,10}(?:說|提到|聊|講|配方)")
_LIVE_RECAP_CUE = re.compile(r"剛才|剛剛|前面(?:說|提|聊|講)|回顧|重述|(?:說|提到|聊到|講過).{0,6}(?:什麼|內容|哪件事)")
_LIVE_ACTIVITY_CUE = re.compile(
    r"(?:主播|台主).{0,10}(?:現在|目前)?.{0,8}(?:在做什麼|做什麼|在玩什麼|玩什麼|幹嘛|忙什麼)|"
    r"(?:現在|目前).{0,8}(?:主播|台主).{0,8}(?:在做|做什麼|在玩|玩什麼|幹嘛|忙什麼)|"
    r"(?:現在|目前)(?:正在)?玩的(?:遊戲)?"
)
_CURRENT_GAME_REFERENCE = re.compile(
    r"(?:這|那)(?:一)?款(?:遊戲)?|(?:這|那)(?:個)?遊戲|目前(?:正在)?玩的(?:遊戲)?|現在玩的(?:遊戲)?"
)
_GAME_SPECIFIC_SUBJECT = re.compile(
    r"道具|物品|角色|技能|招式|Boss|BOSS|關卡|遊戲模式|遊戲類型|遊戲玩法|遊戲評價|遊戲攻略",
    re.IGNORECASE,
)
_UNNAMED_GAME_REFERENT = re.compile(
    r"(?:那|這)(?:隻|個)?\s*(?:王|Boss|頭目|魔王|關卡|副本|技能|招式|道具|物品)",
    re.IGNORECASE,
)
_CONTEXTUAL_FOLLOWUP = re.compile(
    r"^(?:(?:那)?你)?(?:覺得呢|怎麼看|怎么看|認為呢|认为呢|有什麼看法|有什麼想法)[？?。！!]*$"
)
_EXPLICIT_CHANNEL_OPS = re.compile(
    r"台規|頻道規則|劇透|開播|開台|開台時間|星辰大海|連續觀看|Twitch|Discord|\bDC\b|社群|訂閱|會員|忠誠點|抽獎|點播|!\w+|指令|頻道資訊",
    re.IGNORECASE,
)
_BOT_PRESENCE_CHECK = re.compile(r"(?:你|AI|機器人)?(?:還)?活著嗎[？?。！!]*$")
_PERSONA_SELF_STYLE_QUESTION = re.compile(
    r"(?:你|天樞緹亞|天芽).{0,12}(?:講話|說話|回答|回覆|口吻|語氣).{0,20}(?:XD|表情符號|語助詞|口頭禪|一定|總是|每次|習慣|加|用|帶)",
    re.IGNORECASE,
)
_BOT_RUNTIME_QUESTION = re.compile(
    r"你.{0,16}(?:用|使用|跑|運行).{0,12}(?:Google|Gemini|OpenAI|ChatGPT|Ollama|Qwen|Cursor)|"
    r"(?:Google|Gemini|OpenAI|ChatGPT|Ollama|Qwen|Cursor).{0,12}(?:你|AI|機器人|模型|後端)|"
    r"(?:你|AI|機器人).{0,10}(?:用什麼|使用哪個|是哪個).{0,8}(?:模型|後端)|"
    r"目前.{0,8}(?:使用|用).{0,8}(?:模型|後端)",
    re.IGNORECASE,
)
_MEMORY_RECALL = re.compile(
    r"我(?:之前|以前|昨天|前天|最近)?(?:說過|提過|問過|聊過)|還記得我嗎|"
    r"我(?:剛剛|剛才|前面)(?:有沒有|是不是)?(?:說|講|打字|問|提到|聊)",
)
_VIEWER_PREFERENCE_RECALL = re.compile(
    r"(?:我|你還記得我).{0,12}(?:偏好|喜歡|希望|習慣).{0,16}(?:回答|回覆|答覆|說話|口吻|風格|方式)|"
    r"(?:我|你還記得我).{0,12}(?:回答|回覆|答覆|說話|口吻|風格|方式).{0,16}(?:偏好|喜歡|希望|習慣)"
)
_PERSONAL_UTTERANCE_RECALL = re.compile(
    r"我(?:(?:剛剛|剛才|前面)(?:有沒有|是不是)?(?:說|講|打字|問|提到|聊)(?:了|過)?|"
    r"(?:剛剛|剛才|前面)?(?:說|講|打字|問)了?(?:什麼|哪些|哪一句|哪幾句))"
)
_PERSON_RELATION_REQUEST = re.compile(r"是誰|誰是|認識嗎|關係|叫什麼|還記得我|我之前")

_INTENT_NEEDS: dict[str, frozenset[str]] = {
    "social": frozenset(),
    "live_now": frozenset({"live_state", "recent_chat"}),
    "live_recap": frozenset({"recent_chat", "transcript"}),
    "person_relation": frozenset({"viewer_memory"}),
    "game_info": frozenset({"entity_resolution", "web_search"}),
    "session_banter": frozenset({"entity_resolution", "live_state", "recent_chat", "transcript"}),
    "howto_tech": frozenset({"channel_knowledge", "web_search"}),
    "world_fact": frozenset({"web_search"}),
    "ops_channel": frozenset({"channel_knowledge"}),
    "bot_meta": frozenset({"channel_knowledge"}),
    "commerce": frozenset({"web_search"}),
    "noise": frozenset(),
}


def is_punctuation_only_question(question: str) -> bool:
    import unicodedata

    visible = [char for char in str(question or "") if not char.isspace()]
    return bool(visible) and all(unicodedata.category(char).startswith("P") for char in visible)


def is_contextual_followup(question: str) -> bool:
    return bool(_CONTEXTUAL_FOLLOWUP.search(str(question or "").strip()))


def is_runtime_identity_question(question: str) -> bool:
    return bool(_BOT_RUNTIME_QUESTION.search(str(question or "")))


def is_personal_utterance_recall(question: str) -> bool:
    return bool(_PERSONAL_UTTERANCE_RECALL.search(str(question or "")))


def is_viewer_preference_recall(question: str) -> bool:
    return bool(_VIEWER_PREFERENCE_RECALL.search(str(question or "")))


def _is_commerce_question(question: str) -> bool:
    return bool(_COMMERCE.search(question) or _PRICE_AMOUNT.search(question))


def _is_named_definition_question(question: str) -> bool:
    match = _NAMED_DEFINITION_QUESTION.search(str(question or ""))
    if not match:
        return False
    subject = match.group("subject").strip()
    return bool(subject) and not re.search(
        r"^(?:這個|那個|這款|那款|這遊戲|那遊戲|它|他|她|這|那|剛才|剛剛)$",
        subject,
    )


def _is_unclassified_named_definition(question: str, parsed: Mapping[str, Any]) -> bool:
    if not _is_named_definition_question(question):
        return False
    try:
        confidence = float(parsed.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return confidence < 0.5 and str(parsed.get("primary") or "ops_channel") == "ops_channel"


def _has_game_subject(question: str, entities: Iterable[Mapping[str, Any]] = ()) -> bool:
    entity_rows = list(entities)
    if any(str(item.get("kind") or "").casefold() == "game" for item in entity_rows):
        return True
    if _GAME_TITLE.search(question) or _GAME_MODE.search(question) or _CURRENT_GAME_REFERENCE.search(question):
        return True
    if _TECH.search(question):
        return False
    if _UNNAMED_GAME_REFERENT.search(question) and (
        _GAME_GUIDE.search(question) or _GAME_MECHANIC.search(question) or _GAME_FACT_CUE.search(question)
    ):
        return True
    return bool(
        _GAME.search(question)
        and (_GAME_SPECIFIC_SUBJECT.search(question) or _GAME_GUIDE.search(question) or _GAME_REVIEW.search(question) or _GAME_ENTITY_FACT_CUE.search(question))
    )


def is_game_fact_question(question: str, parsed: Mapping[str, Any] | None = None) -> bool:
    if _LIVE_RECAP_GAME_CUE.search(question):
        return False
    rows = (parsed or {}).get("entities") or []
    explicit = bool(_GAME_TITLE.search(question) or _GAME_MODE.search(question))
    has_context = explicit or any(str(item.get("kind") or "").casefold() == "game" for item in rows) or bool(_CURRENT_GAME_REFERENCE.search(question))
    if not has_context:
        if _TECH.search(question):
            return False
        if not (_UNNAMED_GAME_REFERENT.search(question) and (_GAME_GUIDE.search(question) or _GAME_MECHANIC.search(question) or _GAME_FACT_CUE.search(question))):
            return False
    return bool(_GAME_FACT_CUE.search(question) or _GAME_ENTITY_FACT_CUE.search(question) or _GAME_MECHANIC.search(question) or _GAME_GUIDE.search(question) or _GAME_REVIEW.search(question))


def _ambiguous_short_ops_question(question: str, parsed: Mapping[str, Any]) -> bool:
    q = str(question or "").strip()
    if len(q) > 20 or not q or is_punctuation_only_question(q) or is_contextual_followup(q):
        return False
    if str(parsed.get("primary") or "") != "ops_channel" or parsed.get("entities"):
        return False
    if any(
        pattern.search(q)
        for pattern in (
            _MEMORY_RECALL,
            _VIEWER_PREFERENCE_RECALL,
            _PERSONAL_UTTERANCE_RECALL,
            _BOT_RUNTIME_QUESTION,
            _BOT_PRESENCE_CHECK,
            _COMMERCE,
            _WEATHER,
            _STOCK,
            _COMPANY,
            _KNOWN_COMPANY,
            _WIKI,
            _NEWS,
            _TECH,
            _GAME_FACT_CUE,
            _GAME_GUIDE,
            _GAME_REVIEW,
            _GENERAL_FACT_CUE,
        )
    ):
        return False
    return not _EXPLICIT_CHANNEL_OPS.search(q)


def _tags(question: str, parsed: Mapping[str, Any], *, laya_tags: Iterable[str] = ()) -> list[str]:
    tags: set[str] = set()
    named_live_recap = bool(_LIVE_RECAP_GAME_CUE.search(question))
    game_fact = is_game_fact_question(question, parsed) and not named_live_recap
    primary = "game_info" if game_fact else str(parsed.get("primary") or "")
    try:
        confidence = float(parsed.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if primary in PRIMARY_INTENTS and confidence >= 0.5:
        tags.add(primary)
    for value in parsed.get("secondary") or []:
        if str(value) in PRIMARY_INTENTS:
            tags.add(str(value))
    tags.update(clean_strings(laya_tags, PRIMARY_INTENTS))
    if "live_recap" in tags and not (_LIVE_RECAP_CUE.search(question) or _LIVE_ACTIVITY_CUE.search(question)):
        tags.discard("live_recap")
    if game_fact:
        tags.difference_update({"ops_channel", "social", "session_banter", "noise"})
        tags.add("game_info")
    if named_live_recap:
        tags.discard("game_info")
        tags.add("live_recap")
    if any(str(item.get("kind") or "").casefold() == "game" for item in parsed.get("entities") or []) and not named_live_recap:
        tags.add("game_info")
    if _is_commerce_question(question):
        tags.add("commerce")
    if _GAME_GUIDE.search(question) and _has_game_subject(question, parsed.get("entities") or []):
        tags.add("game_info")
    if any(pattern.search(question) for pattern in (_WEATHER, _STOCK, _COMPANY, _KNOWN_COMPANY, _WIKI, _NEWS)):
        tags.add("world_fact")
    if _is_unclassified_named_definition(question, parsed):
        tags.add("world_fact")
    if _GAME_REVIEW.search(question) and _has_game_subject(question, parsed.get("entities") or []):
        tags.add("game_info")
    if _TECH.search(question):
        tags.add("howto_tech")
    if _MEMORY_RECALL.search(question):
        tags.add("viewer_recall")
    if is_viewer_preference_recall(question):
        tags.difference_update(PRIMARY_INTENTS)
        tags.update({"person_relation", "viewer_recall"})
    tags.update(clean_strings(parsed.get("flags") or [], FLAGS))
    if is_runtime_identity_question(question):
        tags.difference_update(PRIMARY_INTENTS)
        tags.add("bot_meta")
    if "social" in tags:
        tags.add("social_banter")
    if len(tags & PRIMARY_INTENTS) > 1:
        tags.add("mixed")
    return sorted(tags)


def _search_profiles(tags: set[str], question: str, entities: Iterable[Mapping[str, Any]] = (), *, primary: str = "") -> list[str]:
    if _is_commerce_question(question):
        return ["store_price_tw" if re.search(r"台灣|臺灣|台幣|新台幣|TWD|NTD|NT\$", question, re.IGNORECASE) else "store_price"]
    if _WEATHER.search(question):
        return ["weather_current"]
    rows = list(entities)
    named_entities = [item for item in rows if item.get("canonical") and str(item.get("kind") or "").casefold() in {"company", "stock", "ticker"}]
    game_entities = [item for item in rows if item.get("canonical") and str(item.get("kind") or "").casefold() == "game"]
    if _STOCK.search(question) or (named_entities and _STOCK_ENTITY.search(question)):
        return ["stock_quote_tw" if re.search(r"台灣|臺灣|台積電|2330|台股", question, re.IGNORECASE) else "stock_quote"]
    has_game = _has_game_subject(question, game_entities)
    live_recap = primary in {"live_now", "live_recap"} and bool(re.search(r"剛才|剛剛", question))
    if _TECH.search(question) and not has_game:
        return ["official_tech_docs"]
    if _GAME_REVIEW.search(question) and has_game:
        return ["game_reviews"]
    if _GAME_GUIDE.search(question) and has_game and not live_recap:
        return ["game_guide"]
    if has_game and _GAME_MECHANIC.search(question) and not live_recap:
        return ["game_guide"]
    if _WIKI.search(question):
        return ["wiki_summary"]
    if _NEWS.search(question):
        return ["news_current" if re.search(r"現在|目前|今日|今天|最新|近期|最近", question) else "news"]
    if _COMPANY.search(question) or _KNOWN_COMPANY.search(question) or named_entities:
        return ["company_profile"]
    if has_game and "game_info" in tags and primary not in {"live_now", "live_recap", "ops_channel", "bot_meta", "social", "person_relation", "session_banter", "noise"}:
        return ["game_official_info"]
    if _TECH.search(question):
        return ["official_tech_docs"]
    if "world_fact" in tags and (_GENERAL_FACT_CUE.search(question) or _is_named_definition_question(question)):
        return ["general_current_fact" if re.search(r"現在|目前|今日|今天|最新|近期|最近", question) else "general_fact"]
    return []


def _ordered_with_reference(values: set[str]) -> list[str]:
    return ordered(values) + (["reference_resolution"] if "reference_resolution" in values else [])


def build_query_plan(
    question: str,
    parsed: Mapping[str, Any],
    *,
    laya_tags: Iterable[str] = (),
    laya_needs: Iterable[str] = (),
    policy_required_needs: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a plan from explicit rule, Laya, and policy need sets."""

    q = str(question or "").strip()
    named_live_recap = bool(_LIVE_RECAP_GAME_CUE.search(q))
    punctuation_noise = is_punctuation_only_question(q)
    contextual_followup = is_contextual_followup(q)
    persona_style = bool(_PERSONA_SELF_STYLE_QUESTION.search(q))
    ambiguous_short = bool(not persona_style and _ambiguous_short_ops_question(q, parsed))
    personal_recall = is_personal_utterance_recall(q)
    preference_recall = is_viewer_preference_recall(q)
    bot_presence = bool(_BOT_PRESENCE_CHECK.search(q))
    runtime_question = is_runtime_identity_question(q)

    tags_list = _tags(q, parsed, laya_tags=laya_tags)
    if punctuation_noise:
        tags_list = ["noise"]
    elif bot_presence:
        tags_list = ["social", "social_banter"]
    elif runtime_question:
        tags = set(tags_list)
        tags.difference_update(PRIMARY_INTENTS)
        tags.update({"bot_meta"})
        tags_list = sorted(tags)
    elif persona_style:
        tags_list = ["social", "social_banter"]
    elif ambiguous_short:
        tags_list = ["session_banter"]
    elif contextual_followup:
        tags = set(tags_list)
        tags.difference_update(PRIMARY_INTENTS - {"session_banter"})
        tags.add("session_banter")
        tags_list = sorted(tags)

    tags = set(tags_list)
    if punctuation_noise:
        effective_primary = "noise"
    elif runtime_question:
        effective_primary = "bot_meta"
    elif persona_style or bot_presence:
        effective_primary = "social"
    elif preference_recall:
        effective_primary = "person_relation"
    elif named_live_recap:
        effective_primary = "live_recap"
    elif is_game_fact_question(q, parsed):
        effective_primary = "game_info"
    elif _is_unclassified_named_definition(q, parsed):
        effective_primary = "world_fact"
    elif contextual_followup or ambiguous_short:
        effective_primary = "session_banter"
    else:
        effective_primary = str(parsed.get("primary") or "ops_channel")

    laya = clean_strings(laya_needs, ALLOWED_NEEDS)
    accepted_laya_tags = clean_strings(laya_tags, PRIMARY_INTENTS)
    rules: set[str] = set()
    policy = clean_strings(policy_required_needs, ALLOWED_NEEDS)
    if named_live_recap:
        policy.difference_update({"web_search", "evidence_contract"})

    for tag in tags:
        if tag == "person_relation" and not _PERSON_RELATION_REQUEST.search(q):
            continue
        rules.update(_INTENT_NEEDS.get(tag, ()))
    if runtime_question:
        rules.discard("channel_knowledge")
        rules.add("runtime_identity")

    reference_detected = bool(_CURRENT_GAME_REFERENCE.search(q) or _UNNAMED_GAME_REFERENT.search(q) or re.search(r"那個(?=.{0,8}(?:可以|要不要|多少|怎麼|好不好|是不是|是哪|是誰|指|說|做|買|玩|好玩|如何))", q))
    if reference_detected:
        rules.update({"reference_resolution", "recent_chat"})
    if re.search(r"剛才|剛剛", q):
        rules.add("transcript")
    if _LIVE_ACTIVITY_CUE.search(q):
        rules.add("transcript")
    if _CURRENT_GAME_REFERENCE.search(q) or _UNNAMED_GAME_REFERENT.search(q):
        rules.update({"live_state", "recent_chat", "transcript", "entity_resolution", "reference_resolution"})
    if contextual_followup or ambiguous_short:
        rules.update({"recent_chat", "transcript"})
    if _MEMORY_RECALL.search(q):
        rules.update({"dialogue_memory", "viewer_memory"})
    if preference_recall or "還記得我嗎" in q:
        rules.add("viewer_memory")
    if personal_recall:
        rules.add("recent_chat")

    explicit_context = bool(reference_detected or re.search(r"剛才|剛剛", q))
    try:
        parsed_confidence = float(parsed.get("confidence", 1.0))
    except (TypeError, ValueError):
        parsed_confidence = 0.0
    explicit_memory = bool(_MEMORY_RECALL.search(q) or preference_recall or "還記得我嗎" in q)
    external_fact = bool(
        not named_live_recap
        and (
            is_game_fact_question(q, parsed)
            or _is_commerce_question(q)
            or _is_unclassified_named_definition(q, parsed)
            or any(pattern.search(q) for pattern in (_WEATHER, _STOCK, _COMPANY, _KNOWN_COMPANY, _WIKI, _NEWS, _TECH))
            or (parsed_confidence >= 0.5 and str(parsed.get("primary") or "") in {"game_info", "world_fact", "howto_tech", "commerce"})
        )
    )

    excluded: set[str] = set()
    if punctuation_noise:
        excluded.update(ALLOWED_NEEDS - policy)
    elif ambiguous_short:
        excluded.update(ALLOWED_NEEDS - policy - {"recent_chat", "transcript"})
    elif bot_presence or persona_style:
        excluded.update(ALLOWED_NEEDS - policy)
    elif runtime_question:
        excluded.update(ALLOWED_NEEDS - policy - {"runtime_identity"})
    elif contextual_followup:
        excluded.update({"live_state", "viewer_memory", "dialogue_memory", "channel_knowledge", "entity_resolution", "web_search", "runtime_identity", "evidence_contract"})
    elif preference_recall:
        excluded.update({"dialogue_memory", "channel_knowledge", "live_state", "recent_chat", "transcript", "web_search"})
    elif effective_primary == "live_now" and not explicit_memory:
        excluded.update({"viewer_memory", "dialogue_memory", "channel_knowledge"})
        if not explicit_context:
            excluded.add("recent_chat")
        if not (_LIVE_RECAP_CUE.search(q) or _LIVE_ACTIVITY_CUE.search(q) or _CURRENT_GAME_REFERENCE.search(q)):
            excluded.add("transcript")
    elif external_fact and not explicit_memory:
        excluded.update({"viewer_memory", "dialogue_memory", "channel_knowledge"})
        if not explicit_context and not contextual_followup:
            excluded.update({"live_state", "recent_chat", "transcript"})
    elif str(parsed.get("primary") or "") == "live_recap" and not explicit_memory:
        excluded.update({"viewer_memory", "dialogue_memory", "channel_knowledge"})
        if not _CURRENT_GAME_REFERENCE.search(q):
            excluded.add("live_state")

    if personal_recall:
        excluded.update({"viewer_memory", "dialogue_memory", "channel_knowledge", "live_state", "web_search"})

    profiles = _search_profiles(tags, q, parsed.get("entities") or [], primary=effective_primary)
    if punctuation_noise or ambiguous_short or named_live_recap:
        profiles = []
    if "commerce" in tags or any(profile in {"weather_current", "stock_quote", "stock_quote_tw"} for profile in profiles):
        policy.add("evidence_contract")

    candidate = laya | rules | policy
    actionable = candidate - excluded
    personality_only = tags <= {"social", "social_banter", "opinion"}
    fast_path = bool(personality_only and not actionable and not profiles and not reference_detected)

    return {
        "plan_version": "query_plan_v1",
        "primary": effective_primary,
        "tags": sorted(tags_list),
        "laya_tags": sorted(accepted_laya_tags),
        "laya_needs": ordered(laya),
        "candidate_needs": _ordered_with_reference(candidate),
        "rule_based_needs": _ordered_with_reference(rules),
        "policy_required_needs": _ordered_with_reference(policy),
        "policy_excluded_needs": _ordered_with_reference(excluded),
        "needs": _ordered_with_reference(candidate),
        "search_profiles": profiles,
        "reference_detected": reference_detected,
        "contextual_followup": contextual_followup,
        "ambiguous_short_followup": ambiguous_short,
        "punctuation_noise": punctuation_noise,
        "personal_utterance_recall": personal_recall,
        "fast_path_eligible": fast_path,
    }


def attach_query_plan(
    question: str,
    parsed: Mapping[str, Any],
    *,
    laya_tags: Iterable[str] = (),
    laya_needs: Iterable[str] = (),
    policy_required_needs: Iterable[str] = (),
) -> dict[str, Any]:
    out = dict(parsed)
    out.update(
        build_query_plan(
            question,
            parsed,
            laya_tags=laya_tags or out.get("laya_tags") or [],
            laya_needs=laya_needs or out.get("laya_needs") or [],
            policy_required_needs=policy_required_needs,
        )
    )
    return out


def merge_laya_decision(
    question: str,
    parsed: Mapping[str, Any],
    response: Mapping[str, Any] | None,
    *,
    threshold: float = 0.6,
) -> dict[str, Any]:
    """Merge one untrusted typed response without giving it policy ownership."""

    response_dict = dict(response or {})
    answers = response_dict.get("answers")
    provider = str(response_dict.get("provider") or "laya_local")
    model = str(response_dict.get("model") or "unknown")
    revision = response_dict.get("revision")
    if not isinstance(answers, Mapping):
        out = attach_query_plan(question, parsed)
        out["classifier"] = {
            "used": False,
            "provider": provider,
            "model": model,
            "reason": "invalid_typed_response",
            "threshold": threshold,
        }
        return out

    out = dict(parsed)
    primary_answer = answers.get("primary")
    choice = str(primary_answer.get("choice") or "") if isinstance(primary_answer, Mapping) else ""
    primary_confidence = probability(primary_answer, "confidence")
    try:
        rule_confidence = float(parsed.get("confidence") or 0.0)
    except (TypeError, ValueError):
        rule_confidence = 0.0
    if choice in PRIMARY_INTENTS and primary_confidence is not None and rule_confidence < 0.85 and primary_confidence >= threshold:
        out["primary"] = choice
        out["confidence"] = primary_confidence

    laya_tags: set[str] = set()
    for intent in PRIMARY_INTENTS:
        value = probability(answers.get(f"tag_{intent}"), "noul")
        if value is not None and value >= threshold:
            laya_tags.add(intent)
    laya_needs: set[str] = set()
    for need in (
        "live_state",
        "recent_chat",
        "transcript",
        "viewer_memory",
        "dialogue_memory",
        "channel_knowledge",
        "entity_resolution",
        "web_search",
    ):
        value = probability(answers.get(f"need_{need}"), "noul")
        if value is not None and value >= threshold:
            laya_needs.add(need)

    flags = list(out.get("flags") or [])
    for name in FLAGS:
        value = probability(answers.get(f"flag_{name}"), "noul")
        if value is not None and value >= threshold and name not in flags:
            flags.append(name)
    out["flags"] = flags
    out["laya_tags"] = sorted(laya_tags)
    out["laya_needs"] = sorted(laya_needs)
    out["classifier"] = {
        "used": True,
        "provider": provider,
        "model": model,
        "revision": revision,
        "threshold": threshold,
    }
    return attach_query_plan(question, out, laya_tags=laya_tags, laya_needs=laya_needs)
