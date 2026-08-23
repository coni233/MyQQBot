from __future__ import annotations

import re
from dataclasses import dataclass

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent

GROUP_SUFFIX = re.compile(r"^-(\d+)$")


@dataclass(slots=True)
class CommandContext:
    tokens: list[str]
    group_id: int | None
    is_superuser: bool
    is_group_admin: bool

    @property
    def can_manage(self) -> bool:
        return self.group_id is not None and (self.is_superuser or self.is_group_admin)


def is_superuser(event: MessageEvent) -> bool:
    return event.get_user_id() in {str(item) for item in get_driver().config.superusers}


def parse_context(event: MessageEvent, tokens: list[str]) -> CommandContext:
    superuser = is_superuser(event)
    own_group = event.group_id if isinstance(event, GroupMessageEvent) else None
    target_group: int | None = own_group
    remaining = list(tokens)

    if remaining:
        match = GROUP_SUFFIX.fullmatch(remaining[-1])
        if match:
            requested_group = int(match.group(1))
            remaining.pop()
            if not superuser and requested_group != own_group:
                raise PermissionError("群管理员不能跨群操作")
            target_group = requested_group

    if own_group is None and not superuser:
        raise PermissionError("私聊管理仅限超级用户")

    admin = isinstance(event, GroupMessageEvent) and event.sender.role in {"owner", "admin"}
    return CommandContext(remaining, target_group, superuser, admin)
