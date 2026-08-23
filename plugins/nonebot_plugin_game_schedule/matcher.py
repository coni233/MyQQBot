"""游戏日程查询命令处理。"""

from __future__ import annotations

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from .data_source import build_reply, resolve_target

__all__ = ["game", "today_game", "week_game", "next_week_game"]

today_game = on_command("今日游戏", aliases={"今天游戏"}, priority=10, block=True)
week_game = on_command("本周游戏", aliases={"这周游戏"}, priority=10, block=True)
next_week_game = on_command("下周游戏", aliases={"下星期游戏"}, priority=10, block=True)
game = on_command("游戏", aliases={"日程"}, priority=10, block=True)


@today_game.handle()
async def handle_today(matcher: Matcher) -> None:
    await matcher.finish(await build_reply("today"))


@week_game.handle()
async def handle_week(matcher: Matcher) -> None:
    await matcher.finish(await build_reply("week", 0))


@next_week_game.handle()
async def handle_next_week(matcher: Matcher) -> None:
    await matcher.finish(await build_reply("week", 1))


@game.handle()
async def handle_game(matcher: Matcher, args: Message = CommandArg()) -> None:
    text = args.extract_plain_text().strip()
    if not text:
        await matcher.finish(await build_reply("today"))

    target = resolve_target(text)
    if target is None:
        await matcher.finish(
            "格式不对哦，试试这些：\n"
            "  /游戏              查看今天\n"
            "  /游戏 本周         查看本周\n"
            "  /游戏 下周         查看下周\n"
            "  /游戏 明天         查看明天\n"
            "  /游戏 2026-08-22   查看指定日期"
        )

    kind, payload = target
    await matcher.finish(await build_reply(kind, payload))
