"""Role-neutral typed question batch sent to Laya."""

from __future__ import annotations

from typing import Any

from .contracts import FLAGS, MODEL_NEEDS, PRIMARY_INTENTS


def _noul(instructions: str, true_text: str) -> dict[str, Any]:
    return {
        "type": "noul",
        "instructions": instructions,
        "criteria": {"true": true_text, "false": "不需要／不符合"},
    }


def build_typed_questions() -> dict[str, dict[str, Any]]:
    """Build one bounded batch; no free-form answer generation is requested."""

    questions: dict[str, dict[str, Any]] = {
        "primary": {
            "type": "choice",
            "instructions": (
                "選出最主要的回答任務；依問題要完成的事判斷，"
                "不依角色人格或提及的專有名詞判斷。"
            ),
            "criteria": {
                "social": "寒暄或輕鬆社交",
                "live_now": "詢問當下直播狀態",
                "live_recap": "回顧剛才直播或聊天內容",
                "person_relation": "詢問觀眾身分或人際關係",
                "game_info": "詢問遊戲知識或評價",
                "session_banter": "依賴當場遊戲情境的互動",
                "howto_tech": "技術說明或操作教學",
                "world_fact": "外部世界事實或時效資訊",
                "ops_channel": "本頻道規則或營運資訊",
                "bot_meta": "機器人能力或自我介紹",
                "commerce": "價格、購買或費用查詢",
                "noise": "無效輸入或明確系統測試",
            },
        }
    }
    for intent in sorted(PRIMARY_INTENTS):
        questions[f"tag_{intent}"] = _noul(
            f"問句是否也包含「{intent}」這類回答任務？可與其他標籤並存。",
            f"需要標籤 {intent}",
        )
    for need in MODEL_NEEDS:
        questions[f"need_{need}"] = _noul(
            f"回答這個問題是否需要取用 {need} 資料？",
            f"需要讀取 {need}",
        )
    for flag in sorted(FLAGS):
        questions[f"flag_{flag}"] = _noul(
            f"問句是否符合 {flag} 特徵？",
            f"需要標記 {flag}",
        )
    return questions
