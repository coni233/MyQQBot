from __future__ import annotations

import html
import re
from datetime import datetime

import httpx

from nonebot import logger, on_command, require
from nonebot.exception import FinishedException
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

try:
    require("nonebot_plugin_htmlrender")
    from nonebot_plugin_htmlrender import html_to_pic

    HAS_RENDER = True
except Exception:
    HAS_RENDER = False

__plugin_meta__ = PluginMetadata(
    name="虚拟主播营收",
    description="查询 VirtuaReal / PSPlive 等 B 站虚拟主播月度/年度营收",
    usage="/营收 [年份|月份] [all|vr|psp] [数量]",
    type="application",
    supported_adapters={"~onebot.v11"},
)

API = "https://dc.hihivr.top/gift/by_month"
TIMEOUT = 15.0
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
)

revenue_cmd = on_command("营收", aliases={"营收榜"}, priority=10, block=True)


def _current_month() -> str:
    return datetime.now().strftime("%Y%m")


def _parse_year(text: str) -> str | None:
    return text if re.fullmatch(r"\d{4}", text.strip()) else None


def _parse_month(text: str) -> str | None:
    m = re.match(r"^(\d{4})[-年]?(\d{1,2})月?$", text.strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return f"{year}{month:02d}"


def _fmt_money(value: float) -> str:
    if value >= 10000:
        return f"{value / 10000:.2f}万"
    return f"{value:.1f}"


def _fmt_duration(duration: str) -> str:
    parts = duration.split(":")
    if len(parts) == 3:
        return f"{int(parts[0])}h{int(parts[1]):02d}m"
    return duration or "—"


def _sum_duration(durations: list[str]) -> str:
    total_seconds = 0
    for d in durations:
        parts = d.split(":")
        if len(parts) == 3:
            total_seconds += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


async def _fetch_anchors(month: str, filter_: str) -> list[dict]:
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        headers={"User-Agent": UA, "Referer": "https://dc.hihivr.top/"},
    ) as client:
        resp = await client.get(API, params={"month": month, "filter": filter_})
        resp.raise_for_status()
        data = resp.json()
    return data.get("anchors") or []


def _merge_annual(monthly: list[tuple[str, list[dict]]]) -> list[dict]:
    """把一年中多个月份的榜单按 room_id 聚合。"""
    year_map: dict[int, dict] = {}
    for _month, anchors in monthly:
        for a in anchors:
            rid = int(a.get("room_id") or 0)
            if rid == 0:
                continue
            row = year_map.get(rid)
            if row is None:
                row = {
                    "anchor_name": a.get("anchor_name") or "",
                    "room_id": rid,
                    "union": a.get("union") or "",
                    "total_revenue": 0.0,
                    "gift": 0.0,
                    "guard": 0.0,
                    "super_chat": 0.0,
                    "effective_days": 0,
                    "attention": 0,
                    "fans_count": 0,
                    "durations": [],
                }
                year_map[rid] = row
            row["total_revenue"] += float(a.get("total_revenue") or 0)
            row["gift"] += float(a.get("gift") or 0)
            row["guard"] += float(a.get("guard") or 0)
            row["super_chat"] += float(a.get("super_chat") or 0)
            row["effective_days"] += int(a.get("effective_days") or 0)
            row["durations"].append(str(a.get("live_duration") or ""))
            attention = int(a.get("attention") or 0)
            fans = int(a.get("fans_count") or 0)
            if attention:
                row["attention"] = attention
            if fans:
                row["fans_count"] = fans

    result = []
    for row in year_map.values():
        result.append(
            {
                "anchor_name": row["anchor_name"],
                "room_id": row["room_id"],
                "union": row["union"],
                "total_revenue": row["total_revenue"],
                "gift": row["gift"],
                "guard": row["guard"],
                "super_chat": row["super_chat"],
                "effective_days": row["effective_days"],
                "live_duration": _sum_duration(row["durations"]),
            }
        )
    result.sort(key=lambda a: a["total_revenue"], reverse=True)
    return result


def _rows(anchors: list[dict]) -> list[tuple[str, str, str, str, str, str, str]]:
    rows = []
    for idx, a in enumerate(anchors, 1):
        name = a.get("anchor_name") or str(a.get("room_id"))
        rows.append(
            (
                str(idx),
                str(name),
                _fmt_money(float(a.get("total_revenue") or 0)),
                _fmt_money(float(a.get("gift") or 0)),
                _fmt_money(float(a.get("guard") or 0)),
                _fmt_money(float(a.get("super_chat") or 0)),
                _fmt_duration(str(a.get("live_duration") or "")),
            )
        )
    return rows


def _build_html(
    label: str,
    filter_: str,
    rows: list[tuple[str, str, str, str, str, str, str]],
) -> str:
    body_rows = "".join(
        "<tr>"
        f'<td class="num">{html.escape(r[0])}</td>'
        f'<td class="name">{html.escape(r[1])}</td>'
        f'<td class="money total">{html.escape(r[2])}</td>'
        f'<td class="money gift">{html.escape(r[3])}</td>'
        f'<td class="money guard">{html.escape(r[4])}</td>'
        f'<td class="money sc">{html.escape(r[5])}</td>'
        f'<td class="dur">{html.escape(r[6])}</td>'
        "</tr>"
        for r in rows
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 700px;
    background: #16171d;
    color: #e8e8ee;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    padding: 16px;
  }}
  h1 {{ font-size: 18px; margin-bottom: 4px; }}
  .sub {{ font-size: 12px; color: #9a9aa5; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    background: #23242e; color: #c9c9d4; text-align: left;
    padding: 7px 8px; font-weight: 600;
  }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #26272f; white-space: nowrap; }}
  tr:nth-child(even) td {{ background: #1b1c24; }}
  .num {{ color: #9a9aa5; text-align: center; }}
  .name {{ font-weight: 600; }}
  .money {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .total {{ color: #ffb454; font-weight: 700; }}
  .gift {{ color: #7ec8ff; }}
  .guard {{ color: #ff8fa3; }}
  .sc {{ color: #b3f0a5; }}
  .dur {{ color: #9a9aa5; }}
</style>
</head>
<body>
  <h1>{label} {filter_.upper()} 营收榜（共 {len(rows)} 人）</h1>
  <div class="sub">数据来源 dc.hihivr.top（第三方非官方接口，仅供参考）</div>
  <table>
    <thead>
      <tr><th>#</th><th>主播</th><th>总营收</th><th>礼物</th><th>大航海</th><th>SC</th><th>时长</th></tr>
    </thead>
    <tbody>{body_rows}</tbody>
  </table>
</body>
</html>"""


async def _send_images(
    matcher: Matcher, label: str, filter_: str, anchors: list[dict]
) -> bool:
    if not HAS_RENDER:
        return False
    sent_any = False
    try:
        pic = await html_to_pic(
            html=_build_html(label, filter_, _rows(anchors)),
            viewport={"width": 720, "height": 10},
            device_scale_factor=2,
        )
        await matcher.send(MessageSegment.image(pic))
        sent_any = True
        await matcher.finish()
    except FinishedException:
        raise
    except Exception as exc:
        # 只要发出去过图片就不再回退文本，避免“图 + 文”重复输出
        if sent_any:
            logger.warning("营收图片发送中断：{}", exc)
        else:
            logger.warning("营收图片渲染失败，回退为文本输出：{}", exc)
        return sent_any
    return True


@revenue_cmd.handle()
async def _handle_revenue(
    matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()
):
    month = _current_month()
    year: str | None = None
    filter_ = "vr"
    limit: int | None = None

    for token in arg.extract_plain_text().strip().split():
        if year is None and (parsed_year := _parse_year(token)):
            year = parsed_year
        elif parsed := _parse_month(token):
            month = parsed
        elif token.lower() in {"all", "vr", "psp"}:
            filter_ = token.lower()
        elif token.isdigit():
            limit = int(token)
        else:
            await matcher.finish(
                f"无法识别的参数：{token}\n用法：/营收 [年份|月份] [all|vr|psp] [数量]"
            )

    logger.debug(
        "营收查询参数：year={} month={} filter={} limit={}", year, month, filter_, limit
    )

    try:
        if year:
            # 年份查询只到当前月份：现在是 8 月就查 1-8 月，往年查全年
            current = datetime.now()
            if int(year) < current.year:
                end_month = 12
            elif int(year) == current.year:
                end_month = current.month
            else:
                end_month = 0
            monthly: list[tuple[str, list[dict]]] = []
            for m in range(1, end_month + 1):
                month_str = f"{year}{m:02d}"
                try:
                    month_anchors = await _fetch_anchors(month_str, filter_)
                except Exception as exc:
                    logger.warning("获取 {} 营收数据失败：{}", month_str, exc)
                    continue
                if month_anchors:
                    monthly.append((month_str, month_anchors))
            anchors = _merge_annual(monthly)
            if end_month == 12:
                label = f"{year}（全年）"
            elif end_month > 0:
                label = f"{year}（1-{end_month}月）"
            else:
                label = f"{year}"
        else:
            anchors = await _fetch_anchors(month, filter_)
            label = month
    except Exception as exc:
        logger.warning("营收数据获取失败：{}", exc)
        await matcher.finish("营收数据获取失败，请稍后重试")

    if not anchors:
        await matcher.finish(f"{label} 没有 {filter_} 的营收数据")

    if limit:
        anchors = anchors[:limit]

    if await _send_images(matcher, label, filter_, anchors):
        return

    # 图片渲染不可用时回退为文本
    header = f"{label} {filter_.upper()} 营收榜（共 {len(anchors)} 人）"
    lines = []
    for idx, a in enumerate(anchors, 1):
        name = a.get("anchor_name") or str(a.get("room_id"))
        total = _fmt_money(float(a.get("total_revenue") or 0))
        gift = _fmt_money(float(a.get("gift") or 0))
        guard = _fmt_money(float(a.get("guard") or 0))
        sc = _fmt_money(float(a.get("super_chat") or 0))
        dur = _fmt_duration(str(a.get("live_duration") or ""))
        lines.append(
            f"{idx}. {name}  总营收 {total} | 礼物 {gift} | 大航海 {guard} | SC {sc} | 时长 {dur}"
        )

    chunks: list[str] = []
    current = header
    for line in lines:
        if len(current) + len(line) + 1 > 1500:
            chunks.append(current)
            current = header
        current += "\n" + line
    chunks.append(current)

    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await matcher.finish(chunk)
        await matcher.send(chunk)
