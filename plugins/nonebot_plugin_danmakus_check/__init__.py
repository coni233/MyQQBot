from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import datetime, timedelta, timezone

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

try:
    import msgpack
except ImportError:
    msgpack = None

__plugin_meta__ = PluginMetadata(
    name="查成分（Danmakus）",
    description="通过 Danmakus 弹幕数据查询 B 站用户看过的直播主播与消费成分",
    usage="/查成分 <B站UID>\n/查成分 deep <B站UID> [最近N天|开始日期|开始日期 结束日期]",
    type="application",
    supported_adapters={"~onebot.v11"},
)

API = "https://ukamnads.icu"
TIMEOUT = 30.0
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
)
DEEP_START_TS = 1577808000  # 北京时间 2020-01-01 00:00:00（秒）
DEEP_POLL_INTERVAL = 2
DEEP_POLL_TIMEOUT = 90
MAX_ROWS = 25

check_cmd = on_command("查成分", aliases={"dd"}, priority=10, block=True)


def _parse_uid(text: str) -> int | None:
    t = re.sub(r"^[Uu][Ii][Dd]\s*[:：]", "", text.strip())
    return int(t) if t.isdigit() else None


def _parse_date_ts(text: str) -> int | None:
    m = re.match(r"^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?$", text.strip())
    if not m:
        return None
    try:
        dt = datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            tzinfo=timezone(timedelta(hours=8)),
        )
    except ValueError:
        return None
    return int(dt.timestamp())


def _fmt_date_s(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _parse_range(rest: list[str]) -> tuple[int, int, str]:
    """解析 deep 范围参数，返回 (start_ts, end_ts, 显示标签)。"""
    end_ts = int(time.time())
    if not rest:
        return DEEP_START_TS, end_ts, "全量（2020-01-01 起）"
    if len(rest) == 1:
        token = rest[0]
        if token.isdigit():
            days = int(token)
            if days <= 0:
                raise ValueError("天数必须大于 0")
            return end_ts - days * 86400, end_ts, f"最近 {days} 天"
        start = _parse_date_ts(token)
        if start is None:
            raise ValueError(
                f"无法识别的日期：{token}（支持 YYYY-MM-DD 或最近天数）"
            )
        return start, end_ts, f"{_fmt_date_s(start)} 起"
    if len(rest) == 2:
        start = _parse_date_ts(rest[0])
        end = _parse_date_ts(rest[1])
        if start is None or end is None:
            raise ValueError("日期格式应为 YYYY-MM-DD")
        if start > end:
            raise ValueError("开始日期不能晚于结束日期")
        return start, end + 86400 - 1, f"{_fmt_date_s(start)} 至 {_fmt_date_s(end)}"
    raise ValueError("范围参数过多（最多两个日期）")


def _fmt_money(value: float) -> str:
    if value >= 10000:
        return f"{value / 10000:.2f}万"
    return f"{value:.1f}"


def _fmt_count(value: int) -> str:
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    return str(value)


def _fmt_date(ts_ms: int) -> str:
    if not ts_ms:
        return "—"
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")


async def _get_json(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers={"User-Agent": UA, "Accept": "application/json"}
    ) as client:
        resp = await client.get(API + path, params=params)
        resp.raise_for_status()
        return resp.json()


async def fetch_watched(uid: int) -> list[dict]:
    payload = await _get_json(
        "/api/v2/user/watchedChannelsSimple", {"uid": uid, "distinct": True}
    )
    return payload.get("data") or []


async def fetch_counts(uid: int) -> dict[int, int]:
    try:
        payload = await _get_json(
            "/api/v2/user/watchedChannels", {"uid": uid, "simple": True}
        )
    except Exception:
        return {}
    return {
        int(item.get("uId") or 0): int(item.get("count") or 0)
        for item in payload.get("data") or []
    }


def _page(
    header: str,
    sub: str,
    headers: list[str],
    rows: list[list[str]],
    classes: list[str],
    columns: int = 1,
) -> str:
    ths = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    if columns > 1 and rows:
        col_size = (len(rows) + columns - 1) // columns
        chunks = [rows[i * col_size : (i + 1) * col_size] for i in range(columns)]
    else:
        chunks = [rows]
    tables = ""
    for chunk in chunks:
        body = "".join(
            "<tr>"
            + "".join(
                f'<td class="{cls}">{html.escape(cell)}</td>'
                for cell, cls in zip(row, classes)
            )
            + "</tr>"
            for row in chunk
        )
        tables += (
            f'<table class="col"><thead><tr>{ths}</tr></thead>'
            f"<tbody>{body}</tbody></table>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ width: 760px; background: #16171d; color: #e8e8ee;
         font-family: "Microsoft YaHei", "PingFang SC", sans-serif; padding: 16px; }}
  h1 {{ font-size: 18px; margin-bottom: 4px; }}
  .sub {{ font-size: 12px; color: #9a9aa5; margin-bottom: 12px; }}
  .cols {{ display: flex; gap: 10px; }}
  table {{ border-collapse: collapse; font-size: 13px; }}
  table.col {{ flex: 1 1 0; min-width: 0; }}
  th {{ background: #23242e; color: #c9c9d4; text-align: left; padding: 6px 8px; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #26272f; white-space: nowrap; }}
  tr:nth-child(even) td {{ background: #1b1c24; }}
  .num {{ color: #9a9aa5; text-align: center; }} .name {{ font-weight: 600; }}
  .money {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .total {{ color: #ffb454; font-weight: 700; }} .gift {{ color: #7ec8ff; }}
  .guard {{ color: #ff8fa3; }} .sc {{ color: #b3f0a5; }} .dur {{ color: #9a9aa5; }}
  .words {{ margin-top: 12px; font-size: 12px; color: #c9c9d4; line-height: 1.9; }}
</style></head>
<body><h1>{html.escape(header)}</h1><div class="sub">{html.escape(sub)}</div>
<div class="cols">{tables}</div></body></html>"""


async def _send_image(matcher: Matcher, html_text: str) -> bool:
    if not HAS_RENDER:
        return False
    try:
        pic = await html_to_pic(
            html=html_text, viewport={"width": 740, "height": 10}, device_scale_factor=2
        )
        await matcher.send(MessageSegment.image(pic))
    except FinishedException:
        raise
    except Exception as exc:
        logger.warning("查成分图片渲染失败：{}", exc)
        return False
    return True


def _watched_rows(
    channels: list[dict], counts: dict[int, int], limit: int | None = None
) -> list[list[str]]:
    rows = []
    selected = channels[:limit] if limit else channels
    for idx, ch in enumerate(selected, 1):
        uid = int(ch.get("uId") or 0)
        rows.append(
            [
                str(idx),
                str(ch.get("uName") or uid),
                str(counts.get(uid, 0)),
            ]
        )
    return rows


def _watched_text(uid: int, channels: list[dict], counts: dict[int, int]) -> str:
    lines = [f"UID {uid} 看过的直播主播（共 {len(channels)} 位）"]
    rows = _watched_rows(channels, counts, limit=50)
    for row in rows:
        lines.append(f"{row[0]}. {row[1]}  看过 {row[2]} 次")
    if len(rows) < len(channels):
        lines.append("……（其余请查看图片）")
    return "\n".join(lines)


async def _create_job(uid: int, start_ts: int, end_ts: int) -> str:
    async with httpx.AsyncClient(
        timeout=TIMEOUT, headers={"User-Agent": UA, "Accept": "application/json"}
    ) as client:
        resp = await client.post(
            API + "/api/v3/user-analysis-jobs",
            json={"userId": uid, "startTime": start_ts, "endTime": end_ts},
        )
        resp.raise_for_status()
        return str(resp.json().get("jobId") or "")


async def _wait_job(job_id: str) -> None:
    deadline = time.monotonic() + DEEP_POLL_TIMEOUT
    while True:
        payload = await _get_json(f"/api/v3/user-analysis-jobs/{job_id}")
        status = str(payload.get("status") or "")
        if status == "completed":
            return
        if status in {"failed", "canceled"}:
            raise RuntimeError(f"分析任务{status}")
        if time.monotonic() > deadline:
            raise TimeoutError("分析超时，请稍后再试")
        await asyncio.sleep(DEEP_POLL_INTERVAL)


async def _fetch_result(job_id: str) -> dict:
    if msgpack is None:
        raise RuntimeError("缺少 msgpack 依赖，请执行 pip install msgpack")
    async with httpx.AsyncClient(
        timeout=120, headers={"User-Agent": UA, "Accept": "application/x-msgpack"}
    ) as client:
        resp = await client.get(API + f"/api/v3/user-analysis-jobs/{job_id}/result")
        resp.raise_for_status()
        return msgpack.unpackb(resp.content, raw=False)


def _deep_channel_rows(result: dict) -> list[list[str]]:
    """按频道统计该用户自己的弹幕数、消费与最近观看时间。"""
    per: list[tuple[str, int, float, int]] = []
    for entry in result.get("channels") or []:
        if not isinstance(entry, dict):
            continue
        ch = entry.get("channel") or entry
        name = str(ch.get("uName") or ch.get("uId") or "?")
        total_msgs = 0
        total_price = 0.0
        last = 0
        for lv in entry.get("lives") or []:
            for d in lv.get("danmakus") or []:
                total_msgs += 1
                price = float(d.get("price") or 0)
                if price > 0:
                    total_price += price
                t = int(d.get("sendDate") or 0)
                if t > last:
                    last = t
        per.append((name, total_msgs, total_price, last))
    per.sort(key=lambda x: -x[1])
    rows = []
    for idx, (name, msgs, price, last) in enumerate(per[:MAX_ROWS], 1):
        rows.append([str(idx), name, _fmt_count(msgs), _fmt_money(price), _fmt_date(last)])
    return rows


def _deep_html(uid: int, result: dict, range_label: str) -> str:
    summary = result.get("summary") or {}
    total_messages = _fmt_count(int(summary.get("totalMessages") or 0))
    total_payment = _fmt_money(float(summary.get("totalPayment") or 0))
    active_days = str(int(summary.get("activeDays") or 0))
    block_count = str(int(summary.get("blockCount") or 0))
    header = f"UID {uid} 直播成分分析（{range_label}）"
    sub = (
        f"TA 总弹幕 {total_messages} | TA 总消费 {total_payment} | "
        f"活跃 {active_days} 天 | 被拉黑 {block_count} 次"
    )
    body = _page(
        header,
        sub + " · 数据来源 ukamnads.icu（Danmakus）",
        ["#", "主播", "用户弹幕", "用户消费", "最近观看"],
        _deep_channel_rows(result),
        ["num", "name", "money", "money", "dur"],
    )
    word_cloud = result.get("wordCloud") or {}
    if isinstance(word_cloud, dict) and word_cloud:
        top_words = sorted(word_cloud.items(), key=lambda kv: -int(kv[1] or 0))[:15]
        words = "　".join(
            f"{html.escape(str(w))}×{n}" for w, n in top_words
        )
        body = body.replace(
            "</body></html>",
            f'<div class="words">词云 Top15：{words}</div></body></html>',
        )
    return body


def _deep_text(uid: int, result: dict, range_label: str) -> str:
    summary = result.get("summary") or {}
    lines = [
        f"UID {uid} 直播成分分析（{range_label}）",
        f"总弹幕 {_fmt_count(int(summary.get('totalMessages') or 0))} | "
        f"总消费 {_fmt_money(float(summary.get('totalPayment') or 0))} | "
        f"活跃 {int(summary.get('activeDays') or 0)} 天 | "
        f"被拉黑 {int(summary.get('blockCount') or 0)} 次",
    ]
    for row in _deep_channel_rows(result):
        lines.append(f"{row[0]}. {row[1]}  弹幕{row[2]} | 消费{row[3]} | 最近{row[4]}")
    word_cloud = result.get("wordCloud") or {}
    if isinstance(word_cloud, dict) and word_cloud:
        top_words = sorted(word_cloud.items(), key=lambda kv: -int(kv[1] or 0))[:15]
        lines.append("词云 Top15：" + "、".join(f"{w}×{n}" for w, n in top_words))
    return "\n".join(lines)


@check_cmd.handle()
async def _handle(matcher: Matcher, event: MessageEvent, arg: Message = CommandArg()):
    tokens = arg.extract_plain_text().strip().split()
    deep = False
    if tokens and tokens[0].lower() == "deep":
        deep = True
        tokens = tokens[1:]
    if not tokens:
        await matcher.finish(
            "用法：/查成分 <B站UID>\n"
            "       /查成分 deep <B站UID> [最近N天|开始日期|开始日期 结束日期]"
        )
    uid = _parse_uid(tokens[0])
    if uid is None or uid <= 0:
        await matcher.finish("UID 无效，请输入 B 站 UID（支持 UID:xxx 格式）")

    try:
        if deep:
            try:
                start_ts, end_ts, range_label = _parse_range(tokens[1:])
            except ValueError as exc:
                await matcher.finish(str(exc))
            await matcher.send(
                f"正在分析（{range_label}，约需 10~30 秒），请稍候…"
            )
            job_id = await _create_job(uid, start_ts, end_ts)
            await _wait_job(job_id)
            result = await _fetch_result(job_id)
            if await _send_image(matcher, _deep_html(uid, result, range_label)):
                return
            await matcher.finish(_deep_text(uid, result, range_label))
        else:
            if len(tokens) > 1:
                await matcher.finish("参数过多：普通模式只支持 UID")
            channels = await fetch_watched(uid)
            if not channels:
                await matcher.finish("没有找到该用户的直播观看记录")
            counts = await fetch_counts(uid)
            html_text = _page(
                f"UID {uid} 看过的直播主播（共 {len(channels)} 位）",
                "看过次数为用户维度 · 数据来源 ukamnads.icu（Danmakus）",
                ["#", "主播", "次数"],
                _watched_rows(channels, counts),
                ["num", "name", "money"],
                columns=3,
            )
            if await _send_image(matcher, html_text):
                return
            await matcher.finish(_watched_text(uid, channels, counts))
    except FinishedException:
        raise
    except Exception as exc:
        logger.warning("查成分失败：{}", exc)
        await matcher.finish(f"查询失败：{exc}")
