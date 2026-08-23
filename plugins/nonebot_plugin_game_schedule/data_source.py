"""游戏日程查询数据层：请求 API 并格式化输出。"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from nonebot import get_plugin_config
from nonebot.log import logger

from .config import Config

config = get_plugin_config(Config)

_DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_DATE_RE = re.compile(
    r"^(?P<year>\d{4})[年./-](?P<month>\d{1,2})[月./-](?P<day>\d{1,2})日?$"
)
_MONTH_DAY_RE = re.compile(r"^(?P<month>\d{1,2})[月./-](?P<day>\d{1,2})[日号]?$")

_RELATIVE_DAY = {
    "今天": 0,
    "今日": 0,
    "明天": 1,
    "明日": 1,
    "后天": 2,
    "昨天": -1,
    "昨日": -1,
}

_WEEK_OFFSET = {
    "本周": 0,
    "这周": 0,
    "下周": 1,
    "下星期": 1,
    "上周": -1,
    "上星期": -1,
}

_WEEK_LABEL = {
    0: "本周",
    1: "下周",
    -1: "上周",
}


class ScheduleError(Exception):
    """日程查询失败。"""


def today() -> date:
    return datetime.now().astimezone().date()


def parse_date_text(text: str) -> date | None:
    """把用户输入的日期文本解析为具体日期。"""
    text = text.strip()
    if text in _RELATIVE_DAY:
        return today() + timedelta(days=_RELATIVE_DAY[text])

    match = _DATE_RE.match(text)
    if match:
        year, month, day = (int(v) for v in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    match = _MONTH_DAY_RE.match(text)
    if match:
        month, day = (int(v) for v in match.groups())
        try:
            return date(today().year, month, day)
        except ValueError:
            return None

    return None


def resolve_target(text: str) -> tuple[str, Any] | None:
    """把命令参数解析为查询目标：(类型, 参数)。"""
    text = text.strip()
    lowered = text.lower()
    if lowered == "today" or text in ("今天", "今日"):
        return ("today", None)
    if text in _WEEK_OFFSET:
        return ("week", _WEEK_OFFSET[text])
    day = parse_date_text(text)
    if day is None:
        return None
    return ("day", day)


async def _fetch(params: dict[str, Any]) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(config.game_schedule_api_base, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        logger.opt(exception=exc).warning("获取游戏日程接口失败")
        raise
    except ValueError as exc:
        raise ScheduleError("接口返回数据格式异常") from exc


def _check_success(data: dict[str, Any]) -> None:
    if not data.get("success"):
        raise ScheduleError(str(data.get("message") or "未知错误"))


def _format_item(item: dict[str, Any]) -> str:
    hour = int(item["hour"])
    parts = [
        f"{hour:02d}:00-{hour + 1:02d}:00 {item['game']}",
        f"主持：{item['nickname']}",
    ]
    participants = item.get("participants") or []
    if participants:
        parts.append("参与：" + "、".join(participants))
    return "｜".join(parts)


def _format_day(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    header = f"📅 {data['dayName']} {data['date']} 游戏安排"
    if not items:
        return f"{header}\n还没有游戏安排，快去找人开黑吧～"
    lines = [header, ""]
    lines.extend(_format_item(item) for item in items)
    return "\n".join(lines)


def _format_week(data: dict[str, Any], label: str) -> str:
    days = data.get("days") or []
    lines = [f"📅 {label}游戏安排（{data['weekStart']} ~ {data['weekEnd']}）"]
    total = 0
    for day in days:
        items = day.get("items") or []
        if not items:
            continue
        total += len(items)
        lines.extend(["", f"{day['date'][5:]} {day['dayName']}"])
        lines.extend("  " + line for line in map(_format_item, items))
    if total == 0:
        return f"📅 {label}游戏安排（{data['weekStart']} ~ {data['weekEnd']}）\n{label}还没有游戏安排～"
    lines.extend(["", f"共 {total} 场游戏"])
    return "\n".join(lines)


def _monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def _reply_day(day: date) -> str:
    data = await _fetch({"action": "day", "date": day.isoformat()})
    _check_success(data)
    return _format_day(data)


async def _reply_week(offset: int) -> str:
    week_start = _monday_of(today()) + timedelta(weeks=offset)
    data = await _fetch({"action": "week", "weekStart": week_start.isoformat()})
    _check_success(data)
    return _format_week(data, _WEEK_LABEL.get(offset, f"{offset:+d}周"))


async def build_reply(kind: str, payload: Any = None) -> str:
    """根据查询目标获取并格式化日程文本。"""
    try:
        if kind == "today":
            data = await _fetch({"action": "today"})
            _check_success(data)
            return _format_day(data)
        if kind == "day":
            if not isinstance(payload, date):
                raise ScheduleError("日期参数错误")
            return await _reply_day(payload)
        if kind == "week":
            return await _reply_week(int(payload or 0))
    except httpx.HTTPError:
        return "网络开小差了，暂时无法获取游戏安排，请稍后再试～"
    except ScheduleError as exc:
        return f"查询失败：{exc}"
    raise ValueError(f"未知查询类型：{kind}")
