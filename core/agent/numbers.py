"""Check that every number in an agent answer comes from tool results (or the question).

A number in the answer is supported when some number in the tool results equals it
at the answer's own precision. Fractions in [0, 1] (probabilities, shares) also
support their percentage form. Integers up to SMALL_INT_ALLOWANCE ("top 3",
"next 7 days") are allowed as wording.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

SMALL_INT_ALLOWANCE = 10
_NUM = re.compile(
    r"(?<![\w.])[-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[-−]?\d+(?:\.\d+)?"
)


def _parse(token: str) -> tuple[float, int]:
    clean = token.replace(",", "").replace("−", "-")
    decimals = len(clean.split(".")[1]) if "." in clean else 0
    return float(clean), decimals


def numbers_in_text(text: str) -> list[str]:
    return _NUM.findall(text or "")


def _walk(value: Any) -> Iterable[float]:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, str):
        for tok in numbers_in_text(value):
            yield _parse(tok)[0]
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk(v)


def supported_values(tool_results: list[Any], extra_text: str = "") -> list[float]:
    values: list[float] = []
    for v in _walk(tool_results):
        values.append(v)
        if 0 <= v <= 1:
            values.append(v * 100)
    values.extend(_parse(t)[0] for t in numbers_in_text(extra_text))
    return values


def unsupported_numbers(
    answer: str, tool_results: list[Any], question: str = ""
) -> list[str]:
    """Numbers in `answer` that no tool result (or the question) supports."""
    values = supported_values(tool_results, question)
    missing = []
    for token in numbers_in_text(answer):
        number, decimals = _parse(token)
        if decimals == 0 and abs(number) <= SMALL_INT_ALLOWANCE:
            continue
        if not any(round(v, decimals) == round(number, decimals) for v in values):
            missing.append(token)
    return missing
