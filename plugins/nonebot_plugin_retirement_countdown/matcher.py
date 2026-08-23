"""退休倒计时命令处理。"""

from __future__ import annotations

from datetime import date

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import ArgStr, CommandArg

from .data_source import (
    RetirementResult,
    calculate_retirement,
    parse_birth_date,
    parse_worker_type,
)

__all__ = ["retirement"]

retirement = on_command("退休", aliases={"退休倒计时"}, priority=10, block=True)

_BIRTH_PROMPT = (
    "请告诉我你的出生日期，例如：1995-01-01"
    "（也可以写成 1995年1月1日；回复「取消」可退出）"
)
_GENDER_PROMPT = (
    "请告诉我你的性别，例如：男 / 女"
    "（女默认按女干部、原 55 岁计算，如需按工人请写 女工人；回复「取消」可退出）"
)
_GENDER_HINT = "性别格式不对，请输入：男 / 女 / 女工人 / 女干部"
_CANCEL_KEYWORDS = {"取消", "退出", "算了", "不弄了", "不用了", "stop", "cancel", "exit"}


def _is_cancel(text: str) -> bool:
    return text.strip().lower() in _CANCEL_KEYWORDS


def _format_result(result: RetirementResult) -> str:
    delay_text = (
        f"（延迟 {result.delay_months} 个月）" if result.delay_months else "（未延迟）"
    )
    lines = [
        "📅 退休倒计时测算",
        "",
        f"出生日期：{result.birth_date:%Y-%m-%d}",
        f"职工类型：{result.worker_type.value}",
        f"原法定退休年龄：{result.original_retirement_age}岁",
        f"改革后退休年龄：{result.new_retirement_age}{delay_text}",
        f"预计退休日期：{result.retirement_date:%Y-%m-%d}",
    ]
    if result.is_retired:
        lines.extend(["", "🎉 你已退休，好好享受生活吧！"])
    elif result.remaining_days == 0:
        lines.extend(["", "🎉 今天就是你退休的日子！"])
    else:
        lines.extend(["", f"⏳ 距离退休还有 {result.remaining_days} 天"])
    return "\n".join(lines)


@retirement.handle()
async def handle_first(matcher: Matcher, args: Message = CommandArg()) -> None:
    parts = args.extract_plain_text().strip().split()
    if not parts:
        return

    if len(parts) > 3:
        await matcher.finish("参数太多啦，格式：/退休 出生日期 性别，例如：/退休 1995-01-01 男")

    birth_text = parts[0]
    if parse_birth_date(birth_text) is None:
        await matcher.finish("出生日期格式不对，请使用 YYYY-MM-DD，例如：/退休 1995-01-01 男")
    matcher.set_arg("birth", birth_text)  # type: ignore[arg-type]

    if len(parts) >= 2:
        # 允许“女 干部”这种带空格的写法，合并后一起解析
        gender_text = "".join(parts[1:])
        if parse_worker_type(gender_text) is None:
            await matcher.finish(_GENDER_HINT)
        matcher.set_arg("gender", gender_text)  # type: ignore[arg-type]


@retirement.got("birth", prompt=_BIRTH_PROMPT)
async def got_birth(matcher: Matcher, birth: str = ArgStr("birth")) -> None:
    if _is_cancel(birth):
        await matcher.finish("好的，已取消本次退休测算～")
    birth_date = parse_birth_date(birth)
    if birth_date is None:
        await matcher.reject_arg("birth", "出生日期格式不对，请重新输入，例如：1995-01-01")
    if birth_date.year < 1900:
        await matcher.reject_arg("birth", "出生日期太早啦，请重新输入，例如：1995-01-01")
    if birth_date > date.today():
        await matcher.reject_arg("birth", "出生日期不能在未来哦，请重新输入")


@retirement.got("gender", prompt=_GENDER_PROMPT)
async def got_gender(
    matcher: Matcher,
    birth: str = ArgStr("birth"),
    gender: str = ArgStr("gender"),
) -> None:
    if _is_cancel(gender):
        await matcher.finish("好的，已取消本次退休测算～")
    worker_type = parse_worker_type(gender)
    if worker_type is None:
        await matcher.reject_arg("gender", _GENDER_HINT)

    birth_date = parse_birth_date(birth)
    if birth_date is None:
        # 正常情况下不会走到这里，前面已经校验过
        await matcher.reject_arg("birth", "出生日期格式不对，请重新输入，例如：1995-01-01")

    result = calculate_retirement(birth_date, worker_type)
    await matcher.finish(_format_result(result))
