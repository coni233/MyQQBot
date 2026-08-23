from __future__ import annotations

from collections.abc import Iterable

import regex

from .models import AtAllKind, LiveAction, ContentKind

FILTER_MATCH_TIMEOUT = 0.05


def normalize_atall_switches(current: Iterable[str], target: AtAllKind, enabled: bool) -> set[str]:
    """Keep individual content types combinable while ``all`` remains exclusive."""

    switches = {AtAllKind(item) for item in current}
    if not enabled:
        switches.discard(target)
        return {item.value for item in switches}

    if target is AtAllKind.ALL:
        return {AtAllKind.ALL.value}

    switches.discard(AtAllKind.ALL)
    switches.add(target)
    return {item.value for item in switches}


def should_at_all(
    switches: Iterable[str], kind: ContentKind, live_action: LiveAction | None = None
) -> bool:
    values = {AtAllKind(item) for item in switches}
    if live_action is LiveAction.STOP:
        return False
    if AtAllKind.ALL in values:
        return True
    if kind is ContentKind.LIVE:
        return AtAllKind.LIVE in values
    return AtAllKind(kind.value) in values if kind.value in AtAllKind._value2member_map_ else False


def validate_regex(pattern: str) -> None:
    if not pattern or len(pattern) > 256:
        raise ValueError("过滤规则长度必须在 1 到 256 个字符之间")
    try:
        regex.compile(pattern)
    except regex.error as exc:
        raise ValueError(f"无效的正则表达式：{exc}") from exc


def matches_any_filter(text: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        try:
            if regex.search(
                pattern,
                text,
                flags=regex.IGNORECASE,
                timeout=FILTER_MATCH_TIMEOUT,
            ):
                return True
        except (regex.error, TimeoutError):
            continue
    return False
