"""The three-stage MRE pipeline."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from .contracts import TypedDecisionBackend
from .laya import FixtureLayaClient, LayaTypedDecisionClient
from .policy import merge_laya_decision
from .questions import build_typed_questions
from .rules import parse_rules


def run_pipeline(
    question: str,
    *,
    backend: TypedDecisionBackend | None = None,
    threshold: float = 0.6,
    timeout_seconds: float = 1.5,
) -> dict[str, Any]:
    """Run rules -> typed Laya -> policy merge and return all observables."""

    normalized_question = str(question or "").strip()
    rule_parse = parse_rules(normalized_question)
    backend = backend or FixtureLayaClient()
    state = {
        "question": normalized_question,
        "rule_parse": {
            "primary": rule_parse.get("primary"),
            "confidence": rule_parse.get("confidence"),
            "flags": rule_parse.get("flags") or [],
            "entities": rule_parse.get("entities") or [],
        },
    }
    questions = build_typed_questions()
    started = time.perf_counter()
    response: dict[str, Any] | None
    merge_response: dict[str, Any] | None
    backend_error: str | None = None
    try:
        response, client_elapsed_ms = backend.decide(
            state=state,
            questions=questions,
            timeout_seconds=timeout_seconds,
        )
        merge_response = response
    except Exception as exc:  # optional local model must never own policy
        response = None
        client_elapsed_ms = 0.0
        backend_error = type(exc).__name__
        merge_response = {
            "provider": str(getattr(backend, "provider", "laya_local")),
            "model": str(getattr(backend, "model", "unknown")),
        }

    merged = merge_laya_decision(
        normalized_question,
        rule_parse,
        merge_response,
        threshold=threshold,
    )
    if backend_error:
        merged["classifier"] = {
            **dict(merged.get("classifier") or {}),
            "used": False,
            "reason": "backend_error",
            "error_type": backend_error,
        }
    return {
        "question": normalized_question,
        "rule_parse": rule_parse,
        "typed_questions": questions,
        "laya_response": response,
        "merged": merged,
        "timing": {
            "laya_elapsed_ms": client_elapsed_ms,
            "pipeline_elapsed_ms": (time.perf_counter() - started) * 1000.0,
        },
    }


def build_real_laya_pipeline() -> LayaTypedDecisionClient:
    """Construct the optional real local Laya backend without importing it early."""

    return LayaTypedDecisionClient()
