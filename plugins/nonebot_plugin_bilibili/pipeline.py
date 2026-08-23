from __future__ import annotations

from enum import Enum

from nonebot import logger, get_bots
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment

from .renderer import renderer
from .database import repository
from .selectors import select_render_assets
from .rules import should_at_all, matches_any_filter
from .models import LiveAction, ContentKind, PushContent, Subscription


class DeliveryResult(str, Enum):
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


def _delivery_identity(content: PushContent) -> tuple[str, str]:
    namespace = "live" if content.kind is ContentKind.LIVE else "dynamic"
    action = content.live_action.value if content.live_action else "publish"
    return namespace, f"{content.kind.value}:{action}:{content.id}"


def _is_self_echo_timeout(error: ActionFailed) -> bool:
    info = error.info
    detail = " ".join(str(info.get(key) or "") for key in ("message", "wording"))
    return int(info.get("retcode") or 0) == 1200 and "waitforselfecho timeout" in detail.lower()


def content_as_text(content: PushContent) -> str:
    if content.kind is ContentKind.LIVE and content.live_action is LiveAction.STOP:
        return f"🔴 {content.author_name} 直播结束啦，下次见~"
    lines = [f"{content.author_name}：{content.title}"]
    if content.text and content.text != content.title:
        lines.append(content.text)
    if content.forward:
        lines.append(f"转发自 @{content.forward.author_name}")
        if content.forward.title and content.forward.title != "发布了新动态":
            lines.append(content.forward.title)
        if content.forward.text and content.forward.text != content.forward.title:
            lines.append(content.forward.text)
    lines.append(content.url)
    return "\n".join(lines)


def _onebot() -> Bot | None:
    for bot in get_bots().values():
        if isinstance(bot, Bot):
            return bot
    return None


async def _deliver_to_group(
    group_id: int,
    content: PushContent,
    *,
    bypass_filters: bool = False,
    subscription: Subscription | None = None,
) -> DeliveryResult:
    bot = _onebot()
    if bot is None:
        logger.warning("Bilibili subscription: no connected OneBot V11 bot")
        return DeliveryResult.FAILED

    if not bypass_filters:
        patterns = [pattern for _, pattern in await repository.list_filters(group_id)]
        if matches_any_filter(content.filter_text, patterns):
            logger.info(
                "Bilibili subscription: content {} was filtered for group {}",
                content.id,
                group_id,
            )
            return DeliveryResult.SKIPPED

    switches = await repository.get_atall(group_id, content.uid)
    mention = should_at_all(switches, content.kind, content.live_action)
    message = Message()
    if mention:
        message += MessageSegment.at("all")
        message += MessageSegment.text("\n")

    if content.kind is ContentKind.LIVE and content.live_action is LiveAction.STOP:
        message += MessageSegment.text(content_as_text(content))
    else:
        try:
            selection = await select_render_assets(group_id, content)
            image = await renderer.render(content, selection)
            message += MessageSegment.image(image)
        except Exception:
            logger.exception("Bilibili subscription: rendering failed, falling back to text")
            message += MessageSegment.text(content_as_text(content))

    try:
        await bot.send_group_msg(group_id=group_id, message=message)
        return DeliveryResult.SENT
    except ActionFailed as exc:
        if _is_self_echo_timeout(exc):
            logger.warning(
                "Bilibili subscription: OneBot timed out waiting for self echo after sending "
                "to group {}; treating the message as delivered to avoid duplicates",
                group_id,
            )
            return DeliveryResult.SENT
        logger.exception("Bilibili subscription: failed to send to group {}", group_id)
        return DeliveryResult.FAILED
    except Exception:
        logger.exception("Bilibili subscription: failed to send to group {}", group_id)
        return DeliveryResult.FAILED


async def push_to_group(
    group_id: int,
    content: PushContent,
    *,
    bypass_filters: bool = False,
    subscription: Subscription | None = None,
) -> bool:
    result = await _deliver_to_group(
        group_id,
        content,
        bypass_filters=bypass_filters,
        subscription=subscription,
    )
    return result is DeliveryResult.SENT


async def dispatch_content(content: PushContent) -> bool:
    namespace, content_key = _delivery_identity(content)
    await repository.prune_delivery_receipts(namespace, content.uid, content_key)
    completed = True
    for subscription in await repository.groups_for_uid(content.uid):
        if await repository.has_delivery_receipt(
            namespace, content.uid, content_key, subscription.group_id
        ):
            continue
        if not await repository.claim_delivery(
            namespace, content.uid, content_key, subscription.group_id
        ):
            completed = False
            continue
        try:
            result = await _deliver_to_group(
                subscription.group_id,
                content,
                subscription=subscription,
            )
            if result is DeliveryResult.FAILED:
                completed = False
            else:
                await repository.set_delivery_receipt(
                    namespace, content.uid, content_key, subscription.group_id
                )
        finally:
            await repository.release_delivery_claim(
                namespace, content.uid, content_key, subscription.group_id
            )
    return completed
