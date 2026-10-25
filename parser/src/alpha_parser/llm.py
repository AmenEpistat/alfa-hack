"""Organizer gateway transport, with safe connection-only completion failover."""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import httpx
from .config import Settings


def budget_day(now: datetime | None = None) -> str:
    """The team key budget resets at 03:00 Moscow, not at midnight."""
    moment = now or datetime.now(ZoneInfo("Europe/Moscow"))
    if moment.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return (moment.astimezone(ZoneInfo("Europe/Moscow")) - timedelta(hours=3)).date().isoformat()


class ProviderError(RuntimeError):
    def __init__(self, category: str, message: str, *, endpoint=None, status_code=None):
        super().__init__(message)
        self.category, self.endpoint, self.status_code = category, endpoint, status_code

    def as_dict(self):
        retryable = (self.category in {"connection", "response_timeout", "transport", "rate_limit"} or self.status_code in {408, 500, 502, 503, 504}) and self.category not in {"budget_exceeded", "authentication", "access_denied"}
        uncertain = self.category in {"response_timeout", "transport", "invalid_response"} or self.status_code in {408, 500, 502, 503, 504}
        return {"category": self.category, "message": str(self), "endpoint": self.endpoint, "http_status": self.status_code,
                "retryable": retryable, "billing_uncertain": uncertain}


class ProviderBudgetExceeded(ProviderError):
    pass


class ModelOutputTruncated(ProviderError):
    """A received, accounted-for response hit its output cap before an action."""
    pass


def response_error(response: httpx.Response, endpoint: str, key: str) -> ProviderError:
    message = ""
    code = ""
    try:
        body = response.json()
        error = body.get("error", body.get("detail", {})) if isinstance(body, dict) else {}
        if isinstance(error, dict):
            message, code = str(error.get("message", "")), str(error.get("code", ""))
        elif isinstance(error, str):
            message = error
        if not message and isinstance(body, dict):
            message = str(body.get("message", ""))
    except ValueError:
        pass
    # Keep only the provider's short error, never a whole HTML page/request echo.
    if key:
        message = message.replace(key, "[REDACTED]")
    message = re.sub(r"\bsk-[\w-]+", "[REDACTED]", message)[:300]
    lower = (message + " " + code).casefold()
    if "budget" in lower and any(word in lower for word in ("exceed", "exhaust", "insufficient")):
        return ProviderBudgetExceeded("budget_exceeded", "Team key budget has been exceeded. Wait until the reset at 03:00 Moscow; switching endpoints does not reset the shared budget.", endpoint=endpoint, status_code=response.status_code)
    category = {401: "authentication", 403: "access_denied", 404: "endpoint_or_model", 429: "rate_limit"}.get(response.status_code, "provider_http")
    return ProviderError(category, message or f"Provider returned HTTP {response.status_code}", endpoint=endpoint, status_code=response.status_code)


class LLMGateway:
    def __init__(self, settings: Settings):
        self.s = settings
        self.active_endpoint = settings.llm_base_url.rstrip("/")
        self.attempts = []

    @property
    def endpoints(self):
        values = [self.active_endpoint, self.s.llm_base_url, self.s.llm_fallback_base_url]
        return list(dict.fromkeys(x.rstrip("/") for x in values if x))

    def request(self, method: str, path: str, *, body=None):
        self.attempts = []
        endpoints = self.endpoints
        if not endpoints:
            raise ProviderError("configuration", "LLM base URL is not configured")
        timeout = httpx.Timeout(self.s.llm_timeout, connect=min(self.s.llm_connect_timeout, self.s.llm_timeout))
        for index, endpoint in enumerate(endpoints):
            attempt = {"endpoint": endpoint, "method": method}
            self.attempts.append(attempt)
            try:
                with httpx.Client(timeout=timeout, trust_env=False) as client:
                    headers = {"Authorization": "Bearer " + self.s.llm_api_key}
                    if method == "GET":
                        response = client.get(endpoint + path, headers=headers)
                    else:
                        response = client.post(endpoint + path, headers=headers, json=body)
            except (httpx.ConnectTimeout, httpx.ConnectError) as exc:
                attempt["error"] = type(exc).__name__
                if index + 1 < len(endpoints):
                    continue  # Connection not established; completion was not submitted.
                raise ProviderError("connection", "Could not establish a connection to the configured model gateway(s)", endpoint=endpoint) from None
            except httpx.TimeoutException as exc:
                attempt["error"] = type(exc).__name__
                # A read timeout can occur after billable processing: never replay a POST.
                if method == "GET" and index + 1 < len(endpoints):
                    continue
                raise ProviderError("response_timeout", "Provider response timed out; completion was not replayed to avoid a possible duplicate charge", endpoint=endpoint) from None
            except httpx.TransportError as exc:
                attempt["error"] = type(exc).__name__
                raise ProviderError("transport", "Transport failed; completion was not replayed", endpoint=endpoint) from None
            attempt["http_status"] = response.status_code
            if not response.is_success:
                error = response_error(response, endpoint, self.s.llm_api_key)
                attempt["category"] = error.category
                # Same key, same budget: no fallback on budget/auth/rate-limit errors.
                if method == "GET" and response.status_code >= 500 and error.category != "budget_exceeded" and index + 1 < len(endpoints):
                    continue
                raise error
            self.active_endpoint = endpoint
            try:
                data = response.json()
            except ValueError:
                raise ProviderError("invalid_response", "Provider returned a non-JSON success response", endpoint=endpoint) from None
            if not isinstance(data, dict):
                raise ProviderError("invalid_response", "Provider JSON response must be an object", endpoint=endpoint)
            if data.get("error"):
                raise response_error(response, endpoint, self.s.llm_api_key)
            return data
        raise ProviderError("connection", "No configured model gateway is available")

    def models(self):
        return self.request("GET", "/models")

    def complete(self, body):
        return self.request("POST", "/chat/completions", body=body)
