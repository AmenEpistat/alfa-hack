"""Bounded model planner for evidence-backed company discovery."""
import re
from .config import Settings
from .llm import LLMGateway, ProviderError, ModelOutputTruncated, budget_day
from .model_profiles import apply_thinking_profile
from .planning import prepare_call, PromptTooLarge
from .schemas import Action, StrictModel
from .storage import Store
from pydantic import Field


class QueryArgs(StrictModel):
    query: str = Field(min_length=2, max_length=600)


class FetchArgs(StrictModel):
    url: str


class FinishArgs(StrictModel):
    sufficient: bool = False
    gaps: list[str] = Field(default_factory=list, max_length=20)


class BudgetError(RuntimeError):
    pass


class GLMPlanner:
    """Plain chat JSON action protocol; no native tool calling required."""
    name = "GLM-5.3-Flash"

    def __init__(self, settings: Settings, store: Store):
        self.s, self.store = settings, store
        if settings.llm_family != self.name:
            raise ValueError("this planner only permits GLM-5.3-Flash family")
        self.gateway = LLMGateway(settings)
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_rub": 0.0,
                      "scope": "this module only; other users of the team key are not accounted for"}
        if settings.input_rub_per_million is None or settings.output_rub_per_million is None:
            self.usage["cost_rub"] = None

    def choose(self, state, tools):
        target = self.s.llm_max_output_tokens
        minimum = min(512, target)
        for attempt in range(self.s.llm_length_retries + 1):
            try:
                return self._choose_once(state, tools, target, minimum)
            except ModelOutputTruncated:
                actual_limit = self.usage["last_response"]["output_limit"]
                if attempt >= self.s.llm_length_retries or actual_limit >= 4096:
                    raise
                next_target = min(4096, actual_limit * 2)
                if next_target <= actual_limit:
                    raise
                self.usage.setdefault("retry_events", []).append({"reason": "output_truncated", "previous_output_limit": actual_limit,
                                                                 "next_output_limit": next_target})
                target, minimum = next_target, next_target

    def _choose_once(self, state, tools, output_target, minimum_output):
        if not self.s.llm_base_url or not self.s.llm_api_key or not self.s.llm_model:
            raise ValueError("LLM endpoint, key and actual deployment model ID are required")
        remaining = self.s.max_tokens - self.usage["input_tokens"] - self.usage["output_tokens"]
        if remaining < minimum_output:
            raise BudgetError("token budget exhausted before next planning call")
        try:
            system, prompt, input_bound, prompt_info, output_limit = prepare_call(state, tools, remaining, output_target, minimum_output)
        except PromptTooLarge:
            raise BudgetError("remaining token budget cannot fit a planning prompt and useful answer") from None
        self.usage.update(prompt_info)
        known = self.usage["cost_rub"] is not None
        if not known and not self.s.allow_unknown_cost:
            raise BudgetError("model prices are unknown; set tariffs or explicitly allow unknown cost")
        forbidden = {"model", "messages", "max_tokens", "max_completion_tokens", "stream", "reasoning_effort"} & self.s.llm_extra_body.keys()
        if forbidden:
            raise ValueError("llm_extra_body cannot override model, messages or token/stream controls")
        reserve = ((input_bound * self.s.input_rub_per_million + output_limit * self.s.output_rub_per_million) / 1_000_000) if known else 0
        body = {"model": self.s.llm_model, "messages": [
                    {"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "temperature": .1, "max_tokens": output_limit, "reasoning_effort": self.s.llm_reasoning_effort}
        body.update(self.s.llm_extra_body)
        body = apply_thinking_profile(self.s, body)
        day = budget_day()
        try:
            self.store.budget_reserve(day, reserve, known, self.s.daily_budget_rub)
        except ValueError as exc:
            raise BudgetError(str(exc)) from None
        # On ambiguous transport/provider failure, keep reservation: a billable call may have happened.
        try:
            data = self.gateway.complete(body)
        except ProviderError as exc:
            if exc.as_dict()["billing_uncertain"]:
                self.usage.setdefault("unconfirmed_calls", []).append({
                    "endpoint": exc.endpoint, "http_status": exc.status_code, "category": exc.category,
                    "input_upper_bound": input_bound, "output_limit": output_limit,
                    "note": "Provider did not return usage; possible charge is not included in confirmed token counters"})
            raise
        finally:
            self.usage["gateway_attempts"] = self.gateway.attempts
            self.usage["endpoint"] = self.gateway.active_endpoint
        usage = data.get("usage") or {}
        # Missing usage is not zero: use upper-bound accounting and label it.
        estimated = "prompt_tokens" not in usage or "completion_tokens" not in usage
        inp = int(usage.get("prompt_tokens", input_bound))
        out = int(usage.get("completion_tokens", output_limit))
        self.usage["input_tokens"] += inp
        self.usage["output_tokens"] += out
        self.usage["calls"] += 1
        self.usage["usage_estimated"] = self.usage.get("usage_estimated", False) or estimated
        if known:
            actual = (inp * self.s.input_rub_per_million + out * self.s.output_rub_per_million) / 1_000_000
            self.usage["cost_rub"] += actual
            self.store.budget_settle(day, reserve, actual)
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        raw = message.get("content")
        details = usage.get("completion_tokens_details") or {}
        reasoning_tokens = details.get("reasoning_tokens")
        if not isinstance(reasoning_tokens, int) or reasoning_tokens < 0:
            reasoning_tokens = None
        self.usage["last_response"] = {"finish_reason": choice.get("finish_reason"), "content_chars": len(raw) if isinstance(raw, str) else 0,
                                       "reasoning_tokens": reasoning_tokens,
                                       "visible_output_tokens": max(0, out - reasoning_tokens) if reasoning_tokens is not None else None,
                                       "reasoning_field_present": bool(message.get("reasoning") or message.get("reasoning_content") or message.get("reasoning_details")),
                                       "output_limit": output_limit, "requested_reasoning_effort": body.get("reasoning_effort"),
                                       "requested_thinking_mode": self.s.llm_thinking_mode,
                                       "requested_reasoning": body.get("reasoning")}
        # Never parse or log private reasoning as an action; count only reported token metadata.
        if choice.get("finish_reason") == "length":
            raise ModelOutputTruncated("output_truncated", f"Model reached the {output_limit}-token output limit before returning a complete action; reasoning_tokens={reasoning_tokens}", endpoint=self.gateway.active_endpoint)
        if not isinstance(raw, str) or not raw.strip():
            finish = choice.get("finish_reason")
            raise ProviderError("empty_model_response", f"Model returned no action text (finish_reason={finish}); check model output-token limit", endpoint=self.gateway.active_endpoint)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
        return Action.model_validate_json(raw)

