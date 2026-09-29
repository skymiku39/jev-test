"""Laya adapter plus a deterministic fixture backend for offline reproduction."""

from __future__ import annotations

import importlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import JsonObject, QuestionSpec

DEFAULT_REPOSITORY = "convaiinnovations/laya"
DEFAULT_MODEL = "multilingual"
DEFAULT_DEVICE = "auto"


class LayaError(RuntimeError):
    """Safe, short error type for optional local-model failures."""


@dataclass(frozen=True)
class LayaSettings:
    repository: str = DEFAULT_REPOSITORY
    model: str = DEFAULT_MODEL
    device: str = DEFAULT_DEVICE
    timeout_seconds: float = 1.5

    @classmethod
    def from_env(
        cls,
        *,
        repository: str | None = None,
        model: str | None = None,
        device: str | None = None,
    ) -> "LayaSettings":
        return cls(
            repository=(repository or os.environ.get("LAYA_REPOSITORY") or DEFAULT_REPOSITORY).strip(),
            model=(model or os.environ.get("LAYA_MODEL") or DEFAULT_MODEL).strip(),
            device=(device or os.environ.get("LAYA_DEVICE") or DEFAULT_DEVICE).strip(),
            timeout_seconds=max(0.1, float(os.environ.get("LAYA_TIMEOUT", "1.5"))),
        )


class LayaClient:
    """Thin lazy wrapper around the optional ``laya`` Python package.

    Weight loading is explicit through ``warmup``.  The MRE never downloads a
    checkpoint: Hugging Face resolution is restricted to the local cache.
    """

    def __init__(self, settings: LayaSettings | None = None) -> None:
        self.settings = settings or LayaSettings.from_env()
        self._agent: Any | None = None
        self._torch: Any | None = None
        self.load_elapsed_ms: float | None = None
        self.resolved_device: str | None = None
        self.resolved_revision: str | None = None

    def _load(self) -> Any:
        if self._agent is not None:
            return self._agent
        try:
            module = importlib.import_module("laya")
        except ModuleNotFoundError as exc:
            raise LayaError("Laya is not installed; install the optional model dependency") from exc

        device = self.settings.device.casefold()
        if device == "auto":
            try:
                self._torch = importlib.import_module("torch")
                device = "cuda" if self._torch.cuda.is_available() else "cpu"
            except (ImportError, AttributeError):
                device = "cpu"
        elif device == "cuda":
            try:
                self._torch = importlib.import_module("torch")
            except ImportError as exc:
                raise LayaError("Laya cuda device requires PyTorch") from exc
            if not self._torch.cuda.is_available():
                raise LayaError("Laya cuda device is unavailable")
        if device not in {"cpu", "cuda"}:
            raise LayaError("Laya device must be auto, cpu, or cuda")

        started = time.perf_counter()
        try:
            known_subfolders = {"multilingual", "typed-decisions", "english"}
            if self.settings.model in known_subfolders:
                repository = self.settings.repository
                if not Path(repository).exists():
                    try:
                        from huggingface_hub import snapshot_download
                    except ImportError as exc:
                        raise LayaError("huggingface-hub is required for a named local-cache model") from exc
                    prefix = f"{self.settings.model}/"
                    repository = snapshot_download(
                        repo_id=repository,
                        allow_patterns=[
                            prefix + name
                            for name in (
                                "rl_agent_config.json",
                                "model.safetensors",
                                "tokenizer/*",
                                "encoder/*",
                            )
                        ],
                        local_files_only=True,
                    )
                    self.resolved_revision = Path(repository).name
                self._agent = module.load(repository, subfolder=self.settings.model, device=device)
            else:
                selected = self.settings.model
                if not Path(selected).exists():
                    raise LayaError("Laya model must be a local path or a named subfolder")
                self._agent = module.load(selected, device=device)
        except LayaError:
            raise
        except Exception as exc:  # model/device errors are backend-specific
            raise LayaError(f"Laya checkpoint failed to load: {type(exc).__name__}") from exc
        self.load_elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.resolved_device = str(getattr(getattr(self._agent, "device", None), "type", device))
        return self._agent

    def warmup(self) -> None:
        self._load()
        self.decide(
            state="warmup",
            questions={"_warmup": {"type": "noul", "instructions": "Warmup only."}},
        )

    def decide(
        self,
        *,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, QuestionSpec],
        timeout_seconds: float | None = None,
    ) -> tuple[JsonObject, float]:
        _ = timeout_seconds
        agent = self._load()
        if self.resolved_device == "cuda" and self._torch is not None:
            self._torch.cuda.synchronize()
        started = time.perf_counter()
        try:
            value = agent.predict(state, dict(questions))
        except Exception as exc:
            raise LayaError(f"Laya prediction failed: {type(exc).__name__}") from exc
        if self.resolved_device == "cuda" and self._torch is not None:
            self._torch.cuda.synchronize()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if not isinstance(value, dict) or not isinstance(value.get("answers"), dict):
            raise LayaError("Laya response is missing answers")
        return value, elapsed_ms

    def status(self) -> dict[str, Any]:
        return {
            "provider": "laya_local",
            "repository": self.settings.repository,
            "model": self.settings.model,
            "revision": self.resolved_revision,
            "device": self.resolved_device,
            "load_elapsed_ms": self.load_elapsed_ms,
        }


class LayaTypedDecisionClient:
    """Add stable provider metadata to the raw Laya typed response."""

    provider = "laya_local"

    def __init__(self, client: LayaClient | None = None) -> None:
        self.client = client or LayaClient()
        self.settings = self.client.settings
        self.model = f"{self.settings.repository}/{self.settings.model}"

    def warmup(self) -> None:
        self.client.warmup()

    def decide(
        self,
        *,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, QuestionSpec],
        timeout_seconds: float | None = None,
    ) -> tuple[JsonObject, float]:
        value, elapsed_ms = self.client.decide(
            state=state,
            questions=questions,
            timeout_seconds=timeout_seconds,
        )
        response = dict(value)
        response["provider"] = self.provider
        response["model"] = self.model
        if self.client.resolved_revision:
            response["revision"] = self.client.resolved_revision
        return response, elapsed_ms


@dataclass
class ScriptedLayaClient:
    """Test double that still exercises the exact typed response boundary."""

    response: JsonObject | Callable[[Mapping[str, Any], Mapping[str, QuestionSpec]], JsonObject]
    provider: str = "laya_local"
    model: str = "fixture-laya"
    calls: list[dict[str, Any]] = field(default_factory=list)

    def decide(
        self,
        *,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, QuestionSpec],
        timeout_seconds: float | None = None,
    ) -> tuple[JsonObject, float]:
        self.calls.append({"state": state, "questions": dict(questions), "timeout_seconds": timeout_seconds})
        value = self.response(state, questions) if callable(self.response) else dict(self.response)
        value.setdefault("provider", self.provider)
        value.setdefault("model", self.model)
        return value, 0.0


class FixtureLayaClient:
    """Small deterministic classifier for a no-model command-line smoke run."""

    provider = "fixture_laya"
    model = "fixture-rules-v1"

    def decide(
        self,
        *,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, QuestionSpec],
        timeout_seconds: float | None = None,
    ) -> tuple[JsonObject, float]:
        _ = timeout_seconds
        question = str(state.get("question") if isinstance(state, Mapping) else state).casefold()
        if any(token in question for token in ("多少錢", "價格", "售價", "購買")):
            primary = "commerce"
        elif any(token in question for token in ("如何", "怎麼", "設定", "安裝", "ollama")):
            primary = "howto_tech"
        elif any(token in question for token in ("遊戲", "大亂鬥", "game", "hades", "potion")):
            primary = "game_info"
        elif "直播標題" in question:
            primary = "live_recap"
        else:
            primary = "social"

        answers: JsonObject = {
            "primary": {"choice": primary, "confidence": 0.9},
        }
        for key in questions:
            if key.startswith("tag_"):
                answers[key] = {"noul": 0.9 if key == f"tag_{primary}" else 0.1}
            elif key.startswith("need_"):
                need = key.removeprefix("need_")
                wants = (
                    need == "web_search"
                    and primary in {"commerce", "game_info", "howto_tech"}
                ) or (need == "transcript" and "剛才" in question)
                answers[key] = {"noul": 0.9 if wants else 0.1}
            elif key.startswith("flag_"):
                answers[key] = {"noul": 0.9 if key == "flag_opinion" and "覺得" in question else 0.1}
        return {"answers": answers, "provider": self.provider, "model": self.model}, 0.0
