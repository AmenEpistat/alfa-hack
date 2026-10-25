"""Exclude clearly identified service/error fragments, without rewriting source evidence."""
import re


def is_substantive_fragment(text):
    normalized = " ".join(text.split())
    if not normalized:
        return False
    if re.match(r"^(?:контакты\s*[/|]\s*дисклеймер|контакты\s+и\s+дисклеймер|contacts\s*[/|]\s*disclaimer)", normalized, re.I):
        return False
    if re.fullmatch(r"(?:you don.t have permission to access .+ on this server\.?|"
                    r"access denied[.!]?(?:\s+reference\s*#.+)?|403\s+forbidden|"
                    r"the requested url .+ was not found on this server\.?)", normalized, re.I):
        return False
    return True
