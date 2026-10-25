"""Bounded JSON generation through the configured organizer gateway."""
from copy import deepcopy
import json
from typing import Any

from alpha_parser.config import Settings
from alpha_parser.model_profiles import apply_thinking_profile
from alpha_parser.llm import LLMGateway, ProviderError, budget_day
from alpha_parser.storage import Store


class JsonLLMClient:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        gateway: Any = None,
        max_output_tokens: int = 4096,
        max_calls: int | None = None,
    ):
        if not 512 <= max_output_tokens <= 4096:
            raise ValueError("max_output_tokens must be between 512 and 4096")
        self._automatic_call_limit = max_calls is None
        if max_calls is None:
            max_calls = 8  # Standalone calls; generate_insights replaces this with its finite plan.
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 1:
            raise ValueError("max_calls must be a positive integer")
        self.s, self.store = settings, store
        self.gateway = gateway if gateway is not None else LLMGateway(settings)
        self.max_output_tokens, self.max_calls = max_output_tokens, max_calls
        self._known_prices = (
            settings.input_rub_per_million is not None
            and settings.output_rub_per_million is not None
        )
        self._usage = {
            "model": settings.llm_model,
            "input_tokens": 0,
            "output_tokens": 0,
            "calls": 0,
            "submitted_calls": 0,
            "cost_rub": 0.0 if self._known_prices else None,
            "scope": "insides calls only; other users of the team key are not accounted for",
            "cost_note": None if self._known_prices else "Tariffs not supplied; cost is unknown, not zero",
            "usage_estimated": False,
            "gateway_attempts": [],
            "unconfirmed_calls": [],
        }

    def configure_generation_plan(self, planned_insights: int, max_repairs: int) -> None:
        """Derive the call allowance from a finite plan; honor explicit limits."""
        if self._automatic_call_limit:
            self.max_calls = self._usage["submitted_calls"] + max(1, planned_insights * (1 + max_repairs))

    @property
    def usage(self) -> dict:
        """A JSON-safe snapshot without request text, keys or private reasoning."""
        return deepcopy(self._usage)

    def _reserve(self, input_bound: int) -> tuple[str, float]:
        if not self._known_prices and not self.s.allow_unknown_cost:
            raise ProviderError("configuration", "Model tariffs are unknown; explicitly allow unknown cost or configure tariffs")
        reserve = (
            (
                input_bound * self.s.input_rub_per_million
                + self.max_output_tokens * self.s.output_rub_per_million
            )
            / 1_000_000
            if self._known_prices else 0.0
        )
        day = budget_day()
        try:
            self.store.budget_reserve(day, reserve, self._known_prices, self.s.daily_budget_rub)
        except ValueError as exc:
            raise ProviderError("local_budget", str(exc)) from None
        return day, reserve

    def _release_unsubmitted(self, day: str, reserve: float) -> None:
        # A connection failure or explicit refusal has no ambiguous completion.
        self.store.budget_settle(day, reserve, release_unknown=int(not self._known_prices))

    @staticmethod
    def _token_count(usage: dict, name: str, fallback: int) -> tuple[int, bool]:
        value = usage.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value, False
        return fallback, True

    def _record_attempts(self, call: int) -> None:
        allowed = {"endpoint", "method", "http_status", "category", "error"}
        for attempt in getattr(self.gateway, "attempts", []) or []:
            if not isinstance(attempt, dict):
                continue
            clean = {key: value for key, value in attempt.items() if key in allowed}
            self._usage["gateway_attempts"].append(
                {"call": call, "stage": "insight_generation", **clean}
            )
        self._usage["endpoint"] = getattr(self.gateway, "active_endpoint", None)

    def complete(self, messages: list[dict]) -> str:
        if not self.s.llm_base_url or not self.s.llm_api_key or not self.s.llm_model:
            raise ProviderError("configuration", "Configured LLM endpoint, key and model ID are required")
        if self._usage["submitted_calls"] >= self.max_calls:
            raise ProviderError("call_limit", "Insight generation call limit reached")
        if not messages or any(
            not isinstance(message, dict)
            or message.get("role") not in {"system", "user", "assistant"}
            or not isinstance(message.get("content"), str)
            for message in messages
        ):
            raise ValueError("messages must contain text system/user/assistant messages")
        forbidden = {
            "model", "messages", "max_tokens", "max_completion_tokens",
            "stream", "reasoning_effort",
        } & self.s.llm_extra_body.keys()
        if forbidden:
            raise ValueError("llm_extra_body cannot override model, messages or token/stream controls")
        # UTF-8 bytes conservatively bound tokenization, with message framing.
        input_bound = len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 256
        body = {
            "model": self.s.llm_model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_output_tokens,
            "reasoning_effort": self.s.llm_reasoning_effort,
            **self.s.llm_extra_body,
        }
        body = apply_thinking_profile(self.s, body)
        day, reserve = self._reserve(input_bound)
        self._usage["submitted_calls"] += 1
        call = self._usage["submitted_calls"]
        try:
            data = self.gateway.complete(body)
        except ProviderError as error:
            if error.as_dict()["billing_uncertain"]:
                self._usage["unconfirmed_calls"].append({
                    "call": call,
                    "endpoint": error.endpoint,
                    "http_status": error.status_code,
                    "category": error.category,
                    "input_upper_bound": input_bound,
                    "output_limit": self.max_output_tokens,
                    "note": "Provider returned no usage; possible charge is absent from confirmed token counters",
                })
            else:
                self._release_unsubmitted(day, reserve)
            raise
        except Exception:
            # Unknown gateway failures may follow submission. Keep the reservation,
            # and never expose exception reprs which could contain request secrets.
            self._usage["unconfirmed_calls"].append({
                "call": call,
                "endpoint": getattr(self.gateway, "active_endpoint", None),
                "http_status": None,
                "category": "unexpected_gateway_failure",
                "input_upper_bound": input_bound,
                "output_limit": self.max_output_tokens,
                "note": "Gateway failed without usage; possible charge is absent from confirmed counters",
            })
            raise ProviderError("transport", "Gateway failed without a confirmed completion; request was not replayed") from None
        finally:
            self._record_attempts(call)

        if not isinstance(data, dict):
            data = {}
        usage = data.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        inp, estimated_input = self._token_count(usage, "prompt_tokens", input_bound)
        out, estimated_output = self._token_count(usage, "completion_tokens", self.max_output_tokens)
        self._usage["input_tokens"] += inp
        self._usage["output_tokens"] += out
        self._usage["calls"] += 1
        self._usage["usage_estimated"] |= estimated_input or estimated_output
        if self._known_prices:
            actual = (
                inp * self.s.input_rub_per_million + out * self.s.output_rub_per_million
            ) / 1_000_000
            self._usage["cost_rub"] += actual
            self.store.budget_settle(day, reserve, actual)
        choices = data.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = choice.get("message")
        message = message if isinstance(message, dict) else {}
        content = message.get("content")
        finish_reason = choice.get("finish_reason")
        # Keep only protocol metadata, never a reasoning/reasoning_content field.
        self._usage["last_response"] = {
            "finish_reason": finish_reason if isinstance(finish_reason, str) else None,
            "content_chars": len(content) if isinstance(content, str) else 0,
            "output_limit": self.max_output_tokens,
            "requested_thinking_mode": self.s.llm_thinking_mode,
            "requested_reasoning": body.get("reasoning"),
        }
        if finish_reason == "length":
            raise ProviderError("output_truncated", "Model output was truncated at its output-token limit")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("empty_model_response", "Model returned no visible JSON content")
        return content.strip()
