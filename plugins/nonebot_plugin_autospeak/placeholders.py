"""AutoSpeak 预设占位符渲染。

{date[:格式]} / {time[:格式]} / {datetime[:格式]}
    当前日期时间，strftime 格式
{weekday}
    今天星期几
{days_until:日期} / {days_until_cn:日期}
    距目标日期的天数 / 中文描述
{image:路径|URL|文件名}
    发送图片，渲染为 CQ 码

未知占位符保持原样，CQ 码原样透传。
"""

import math
import re
from datetime import datetime
from pathlib import Path

_WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_PLACEHOLDER_RE = re.compile(r"\{(\w+)(?::([^}]*))?\}")

# 按从精确到宽松的顺序尝试解析目标日期
_TARGET_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")

_DEFAULT_FORMATS = {
    "date": "%Y-%m-%d",
    "time": "%H:%M:%S",
    "datetime": "%Y-%m-%d %H:%M:%S",
}


def _parse_target(text: str) -> datetime | None:
    """解析目标时间，支持 YYYY-MM-DD [HH:MM[:SS]]。"""
    text = text.strip()
    for fmt in _TARGET_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _days_until(target_str: str, now: datetime) -> int | None:
    """距目标时间的整天天数，未来为正、过去为负、当天为 0。"""
    target = _parse_target(target_str)
    if target is None:
        return None
    return math.ceil((target - now).total_seconds() / 86400)


def _days_until_cn(target_str: str, now: datetime) -> str | None:
    """中文描述距离目标日期还有多少天。"""
    days = _days_until(target_str, now)
    if days is None:
        return None
    if days > 0:
        return f"还有 {days} 天"
    if days == 0:
        return "就是今天"
    return f"已过 {-days} 天"


def _cq_escape(text: str) -> str:
    """转义 CQ 码特殊字符，先转义 & 再转义其余。"""
    return text.replace("&", "&amp;").replace(",", "&#44;").replace("]", "&#93;")


def _resolve_image_file(arg: str, images_dir: Path | None) -> str:
    """图片参数转 CQ image 的 file 值。

    链接与含路径分隔符的参数原样使用；裸文件名拼接 images_dir。
    """
    arg = arg.strip()
    lower = arg.lower()
    if lower.startswith(("http://", "https://", "base64://", "file://")):
        return arg
    if "/" in arg or "\\" in arg:
        return arg
    if images_dir is None:
        return arg
    path = (Path(images_dir) / arg).resolve().as_posix()
    return f"file:///{path}"


def render_placeholders(
    text: str, now: datetime | None = None, images_dir: Path | str | None = None
) -> str:
    """渲染文本中的占位符。

    :param images_dir: 裸文件名图片的查找目录
    """
    if now is None:
        now = datetime.now()

    def repl(match: re.Match) -> str:
        name = match.group(1)
        arg = match.group(2) or ""

        if name == "date":
            return now.strftime(arg or _DEFAULT_FORMATS["date"])
        if name == "time":
            return now.strftime(arg or _DEFAULT_FORMATS["time"])
        if name == "datetime":
            return now.strftime(arg or _DEFAULT_FORMATS["datetime"])
        if name == "weekday":
            return _WEEKDAYS_CN[now.weekday()]
        if name == "days_until":
            days = _days_until(arg, now)
            return str(days) if days is not None else match.group(0)
        if name == "days_until_cn":
            desc = _days_until_cn(arg, now)
            return desc if desc is not None else match.group(0)
        if name == "image":
            if not arg:
                return match.group(0)
            return f"[CQ:image,file={_cq_escape(_resolve_image_file(arg, images_dir))}]"


        # 未知占位符保持原样
        return match.group(0)

    return _PLACEHOLDER_RE.sub(repl, text)
