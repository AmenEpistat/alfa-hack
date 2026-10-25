"""Explicit transport-specific reasoning controls; never read reasoning text."""
from copy import deepcopy


def apply_thinking_profile(settings, body: dict) -> dict:
    result = deepcopy(body)
    mode = settings.llm_thinking_mode
    if mode == "default":
        return result
    if settings.llm_thinking_protocol != "openrouter":
        raise ValueError("Explicit thinking mode requires llm_thinking_protocol=openrouter")
    if mode not in {"instant", "minimal"}:
        raise ValueError("Unsupported thinking mode")
    conflicts = {"reasoning", "thinking", "enable_thinking", "chat_template_kwargs"} & settings.llm_extra_body.keys()
    if conflicts:
        raise ValueError("Explicit thinking profile conflicts with llm_extra_body thinking controls")
    result.pop("reasoning_effort", None)
    # Excluding the reasoning text does not disable generation or billing.
    # Use the provider's actual disable signal and inspect usage metadata.
    if mode == "instant":
        result["reasoning"] = {"enabled": False, "effort": "none"}
    else:
        result["reasoning"] = {"enabled": True, "effort": "minimal"}
    return result
