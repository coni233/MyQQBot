from __future__ import annotations

from nonebot import get_driver, get_plugin_config, logger, on_request
from nonebot.adapters.onebot.v11 import (
    Bot,
    FriendRequestEvent,
    GroupRequestEvent,
)
from nonebot.plugin import PluginMetadata
from pydantic import BaseModel


class Config(BaseModel):
    """自动批准配置（对应 .env 中的 AUTO_APPROVE_* 变量）"""

    auto_approve_friend: bool = False           # 自动同意好友申请
    auto_approve_group_invite: bool = False     # 自动同意群邀请
    auto_approve_notify_superuser: bool = False  # 处理后私聊通知超级用户


plugin_config = get_plugin_config(Config)
superusers = get_driver().config.superusers

__plugin_meta__ = PluginMetadata(
    name="自动批准",
    description="自动同意加好友请求与群邀请",
    usage="无需指令；收到好友申请或群邀请时按配置自动同意",
    type="application",
    supported_adapters={"~onebot.v11"},
)

request_handler = on_request(priority=1, block=False)


async def _notify_superusers(bot: Bot, message: str) -> None:
    if not plugin_config.auto_approve_notify_superuser:
        return
    for su in superusers:
        try:
            await bot.send_private_msg(user_id=int(su), message=message)
        except Exception as exc:
            logger.warning("通知超级用户 {} 失败：{}", su, exc)


@request_handler.handle()
async def _auto_approve(bot: Bot, event: FriendRequestEvent | GroupRequestEvent):
    try:
        if isinstance(event, FriendRequestEvent):
            if not plugin_config.auto_approve_friend:
                return
            await event.approve(bot)
            logger.info(
                "已自动同意好友申请：QQ {}（备注：{}）", event.user_id, event.comment or "无"
            )
            await _notify_superusers(
                bot,
                f"✅ 已自动同意好友申请：QQ {event.user_id}（备注：{event.comment or '无'}）",
            )
        elif isinstance(event, GroupRequestEvent) and event.sub_type == "invite":
            if not plugin_config.auto_approve_group_invite:
                return
            await event.approve(bot)
            logger.info(
                "已自动同意群邀请：群 {}（邀请人 QQ {}，备注：{}）",
                event.group_id,
                event.user_id,
                event.comment or "无",
            )
            await _notify_superusers(
                bot,
                f"✅ 已自动同意群邀请：群 {event.group_id}"
                f"（邀请人 QQ {event.user_id}，备注：{event.comment or '无'}）",
            )
        # sub_type == "add"（申请加群）不自动处理
    except Exception as exc:
        logger.warning("自动批准请求失败：{}", exc)
