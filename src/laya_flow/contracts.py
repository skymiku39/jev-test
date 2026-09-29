"""Small, dependency-free contracts shared by the three MRE stages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, TypeAlias

PRIMARY_INTENTS = frozenset(
    {
        "social",
        "live_now",
        "live_recap",
        "person_relation",
        "game_info",
        "session_banter",
        "howto_tech",
        "world_fact",
        "ops_channel",
        "bot_meta",
        "commerce",
        "noise",
    }
)

FLAGS = frozenset({"follow_up", "opinion", "sensitive"})

# These are the only data-source candidates Laya may propose. Policy-only and
# program-controlled actions deliberately do not appear in the Laya question
# batch.
MODEL_NEEDS = (
    "live_state",
    "recent_chat",
    "transcript",
    "viewer_memory",
    "dialogue_memory",
    "channel_knowledge",
    "entity_resolution",
    "web_search",
)

ALLOWED_NEEDS = frozenset(
    {
        *MODEL_NEEDS,
        "reference_resolution",
        "evidence_contract",
        "runtime_identity",
    }
)

NEED_ORDER = (
    "live_state",
    "recent_chat",
    "transcript",
    "viewer_memory",
    "dialogue_memory",
    "channel_knowledge",
    "runtime_identity",
    "entity_resolution",
    "web_search",
    "evidence_contract",
)

JsonObject: TypeAlias = dict[str, Any]
QuestionSpec: TypeAlias = dict[str, Any]


class TypedDecisionBackend(Protocol):
    """The only interface the pipeline needs from a typed classifier."""

    provider: str
    model: str

    def decide(
        self,
        *,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, QuestionSpec],
        timeout_seconds: float | None = None,
    ) -> tuple[JsonObject, float]: ...


def clean_strings(values: Any, allowed: frozenset[str]) -> set[str]:
    """Keep only allow-listed string values from untrusted model output."""

    if not isinstance(values, (list, tuple, set, frozenset)):
        return set()
    return {str(value) for value in values if str(value) in allowed}


def probability(answer: Any, key: str) -> float | None:
    if not isinstance(answer, Mapping):
        return None
    try:
        value = float(answer.get(key))
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, value))


def ordered(values: set[str] | frozenset[str]) -> list[str]:
    """Return stable output order without exposing set iteration order."""

    return [value for value in NEED_ORDER if value in values]
