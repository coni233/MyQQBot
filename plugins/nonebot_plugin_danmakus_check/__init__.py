from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import date, datetime, timedelta, timezone

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
    description="通过 Danmakus 弹幕数据查询 B 站用户看过的直播主播，deep 模式输出完整成分画像",
    usage="/查成分 <B站UID>：看过的直播主播列表\n"
    "/查成分 deep <B站UID> [最近N天|开始日期|开始日期 结束日期]："
    "完整画像（指标、互动画像、主播榜、打米、词频、分区、作息、年度、昵称）",
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
        # 结果里的 eventTypes 等字段以整数为键，默认的 strict_map_key 会直接拒收
        return msgpack.unpackb(resp.content, raw=False, strict_map_key=False)


_EVENT_LABELS = {
    0: "弹幕",
    1: "礼物",
    2: "醒目留言",
    3: "大航海",
    4: "入场记录",
    5: "禁言记录",
}

_WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]


def _pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def _top_channels(result: dict, limit: int = MAX_ROWS) -> list[dict]:
    """按弹幕数排序的互动频道，兼容旧版 channels -> lives -> danmakus 结构。"""
    rows: list[dict] = []
    affinities = result.get("channelAffinities")
    if isinstance(affinities, list) and affinities:
        for entry in affinities:
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "name": str(
                        entry.get("channelName") or entry.get("channelUid") or "?"
                    ),
                    "messages": int(entry.get("messageCount") or 0),
                    "payment": float(entry.get("payment") or 0),
                    "active_days": int(entry.get("activeDays") or 0),
                    "lives": int(entry.get("liveCount") or 0),
                    "loyalty": float(entry.get("loyaltyScore") or 0),
                    "last": int(entry.get("lastActiveAt") or 0),
                }
            )
    else:
        for entry in result.get("channels") or []:
            if not isinstance(entry, dict):
                continue
            channel = entry.get("channel") or entry
            messages = 0
            payment = 0.0
            last = 0
            for live in entry.get("lives") or []:
                for item in live.get("danmakus") or []:
                    messages += 1
                    payment += max(float(item.get("price") or 0), 0.0)
                    last = max(last, int(item.get("sendDate") or 0))
            rows.append(
                {
                    "name": str(channel.get("uName") or channel.get("uId") or "?"),
                    "messages": messages,
                    "payment": payment,
                    "active_days": 0,
                    "lives": 0,
                    "loyalty": 0.0,
                    "last": last,
                }
            )
    rows.sort(key=lambda row: -row["messages"])
    return rows[:limit]


def _longest_streak(days: list[dict]) -> int:
    """有互动的日期连续出现的最长天数。"""
    best = run = 0
    prev: date | None = None
    for text in sorted({str(day.get("date") or "") for day in days}):
        try:
            current = date.fromisoformat(text)
        except ValueError:
            continue
        run = run + 1 if prev is not None and (current - prev).days == 1 else 1
        best = max(best, run)
        prev = current
    return best


def _yearly_rows(days: list[dict]) -> list[list[str]]:
    buckets: dict[str, dict[str, float]] = {}
    for day in days:
        year = str(day.get("date") or "")[:4]
        if len(year) != 4:
            continue
        bucket = buckets.setdefault(
            year, {"messages": 0, "events": 0, "payment": 0.0, "days": 0}
        )
        bucket["messages"] += int(day.get("messages") or 0)
        bucket["events"] += int(day.get("events") or 0)
        bucket["payment"] += float(day.get("payment") or 0)
        bucket["days"] += 1
    return [
        [
            year,
            _fmt_count(int(bucket["messages"])),
            _fmt_count(int(bucket["events"])),
            str(int(bucket["days"])),
            _fmt_money(float(bucket["payment"])),
        ]
        for year, bucket in sorted(buckets.items())
    ]


def _collect_stats(result: dict) -> dict:
    """把接口返回的各块数据汇总成展示用的统计值。"""
    summary = result.get("summary") or {}
    insights = result.get("insights") or {}
    days = [d for d in result.get("activityDays") or [] if isinstance(d, dict)]
    affinities = [
        a for a in result.get("channelAffinities") or [] if isinstance(a, dict)
    ]
    areas = [a for a in result.get("areas") or [] if isinstance(a, dict)]
    events = {
        int(key): int(value or 0)
        for key, value in (result.get("eventTypes") or {}).items()
    }
    rhythm = [
        [int(value or 0) for value in row[:24]]
        for row in result.get("rhythmMatrix") or []
        if isinstance(row, list)
    ]

    peak = -1
    fav_weekday = fav_hour = -1
    for weekday, row in enumerate(rhythm[:7]):
        for hour, value in enumerate(row):
            if value > peak:
                peak, fav_weekday, fav_hour = value, weekday, hour

    top_channel = max(
        affinities, key=lambda a: float(a.get("loyaltyScore") or 0), default=None
    )
    return {
        "messages": int(summary.get("totalMessages") or events.get(0) or 0),
        "payment": float(summary.get("totalPayment") or 0),
        "active_days": int(summary.get("activeDays") or len(days)),
        "blocks": int(summary.get("blockCount") or 0),
        "interactions": sum(int(day.get("events") or 0) for day in days),
        "records": sum(events.values()) + int(summary.get("blockCount") or 0),
        "lives": sum(int(a.get("liveCount") or 0) for a in affinities),
        "channels": len(affinities),
        "paid_channels": sum(1 for a in affinities if float(a.get("payment") or 0) > 0),
        "streak": _longest_streak(days),
        "favorite_weekday": fav_weekday,
        "favorite_hour": fav_hour,
        "peak": max(peak, 0),
        "areas": areas,
        "rhythm": rhythm,
        "days": days,
        "insights": insights,
        "events": events,
        "top_channel": top_channel,
        "years": _yearly_rows(days),
    }


_DEEP_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 760px; background: #16171d; color: #e8e8ee;
       font-family: "Microsoft YaHei", "PingFang SC", sans-serif; padding: 16px; }
h1 { font-size: 18px; }
.sub { font-size: 12px; color: #9a9aa5; margin: 4px 0; }
h2 { font-size: 14px; color: #c9c9d4; margin: 16px 0 8px;
     display: flex; justify-content: space-between; align-items: baseline; }
h2 span { font-size: 11px; font-weight: 400; color: #7c7c88; }
.grid { display: grid; gap: 8px; }
.m2 { grid-template-columns: repeat(2, 1fr); }
.m3 { grid-template-columns: repeat(3, 1fr); }
.card { background: #1d1e26; border: 1px solid #26272f;
        border-radius: 8px; padding: 8px 10px; }
.card .label { font-size: 11px; color: #8f8f9c; }
.card .value { font-size: 17px; font-weight: 700; margin-top: 2px; }
.card .note { font-size: 10px; color: #7c7c88; margin-top: 2px; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th { background: #23242e; color: #c9c9d4; text-align: left;
     padding: 5px 6px; font-weight: 600; }
td { padding: 5px 6px; border-bottom: 1px solid #26272f; white-space: nowrap; }
tr:nth-child(even) td { background: #1b1c24; }
.num { color: #9a9aa5; text-align: center; width: 26px; }
.name { font-weight: 600; }
.money { text-align: right; font-variant-numeric: tabular-nums; }
.dur { color: #9a9aa5; }
.bar-row { display: flex; align-items: center; gap: 8px;
           font-size: 12px; margin-bottom: 4px; }
.bar-label { width: 92px; overflow: hidden; text-overflow: ellipsis;
             white-space: nowrap; color: #c9c9d4; }
.bar-track { flex: 1; height: 8px; background: #23242e;
             border-radius: 4px; overflow: hidden; }
.bar-fill { display: block; height: 100%;
            background: linear-gradient(90deg, #4d8dff, #7ec8ff); }
.bar-value { width: 96px; text-align: right; color: #9a9aa5;
             font-variant-numeric: tabular-nums; white-space: nowrap; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { background: #23242e; border: 1px solid #2b2c36; border-radius: 10px;
       padding: 3px 10px; font-size: 12px; color: #c9c9d4; }
.heat { display: grid; grid-template-columns: 34px repeat(24, 1fr);
        gap: 2px; align-items: center; }
.heat-day { font-size: 10px; color: #8f8f9c; }
.heat-cell { height: 15px; border-radius: 2px; background: #23242e; }
.heat-axis { font-size: 9px; color: #6f6f7c; text-align: center; }
.divider { margin: 20px 0 2px; border-top: 1px dashed #2f303a; text-align: center; }
.divider span { position: relative; top: -9px; background: #16171d;
                padding: 0 10px; font-size: 11px; color: #7c7c88; }
.foot { margin-top: 12px; font-size: 10px; color: #6f6f7c; }
"""


def _shell(title: str, sub: str, body: str) -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<style>{_DEEP_CSS}</style></head><body>"
        f'<h1>{html.escape(title)}</h1><div class="sub">{html.escape(sub)}</div>'
        f"{body}</body></html>"
    )


def _card(label: str, value: str, note: str = "") -> str:
    note_html = f'<div class="note">{html.escape(note)}</div>' if note else ""
    return (
        f'<div class="card"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>{note_html}</div>'
    )


def _cards(items: list[tuple[str, str, str]], columns: int = 3) -> str:
    inner = "".join(_card(*item) for item in items)
    return f'<div class="grid m{columns}">{inner}</div>'


def _section(title: str, note: str, inner: str) -> str:
    note_html = f"<span>{html.escape(note)}</span>" if note else ""
    return f"<h2>{html.escape(title)}{note_html}</h2>{inner}"


def _table(headers: list[str], rows: list[list[str]], classes: list[str]) -> str:
    head = "".join(
        f'<th class="{cls}">{html.escape(item)}</th>'
        for item, cls in zip(headers, classes)
    )
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{cls}">{html.escape(cell)}</td>'
            for cls, cell in zip(classes, row)
        )
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _bars(items: list[tuple[str, str, float]]) -> str:
    rows = []
    for label, value, ratio in items:
        width = min(max(ratio, 0.0), 1.0) * 100
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{html.escape(label)}</span>'
            '<span class="bar-track"><span class="bar-fill" '
            f'style="width:{width:.1f}%"></span></span>'
            f'<span class="bar-value">{html.escape(value)}</span></div>'
        )
    return "".join(rows)


def _heatmap(rhythm: list[list[int]], peak: int) -> str:
    cells = []
    for weekday in range(7):
        row = rhythm[weekday] if weekday < len(rhythm) else []
        cells.append(f'<div class="heat-day">{_WEEKDAYS[weekday]}</div>')
        for hour in range(24):
            value = row[hour] if hour < len(row) else 0
            alpha = 0.06 + 0.94 * (value / peak if peak else 0)
            cells.append(
                f'<div class="heat-cell" style="background:rgba(126,200,255,{alpha:.2f})"></div>'
            )
    cells.append('<div class="heat-axis"></div>')
    cells.extend(
        f'<div class="heat-axis">{hour if hour % 3 == 0 else ""}</div>'
        for hour in range(24)
    )
    return f'<div class="heat">{"".join(cells)}</div>'


def _deep_html(uid: int, result: dict, range_label: str) -> str:
    """生成 deep 分析的长图：概览画像 + 排行明细。"""
    st = _collect_stats(result)
    insight = st["insights"]
    names = [str(name) for name in result.get("nameHistory") or [] if str(name)]
    nickname = names[-1] if names else ""
    title = f"UID {uid}" + (f" · {nickname}" if nickname else "") + " · 直播成分分析"
    sub = (
        f"{range_label} · 数据来源 danmakus.com · 共 {_fmt_count(st['messages'])} 条弹幕 / "
        f"{_fmt_count(st['records'])} 条留痕 / {st['channels']} 个互动频道"
    )

    metrics = [
        (
            "弹幕",
            f"{_fmt_count(st['messages'])} 条",
            f"活跃日均 {_fmt_count(round(st['messages'] / max(st['active_days'], 1)))}",
        ),
        (
            "互动次数",
            f"{_fmt_count(st['interactions'])} 次",
            f"含入场 {_fmt_count(st['events'].get(4, 0))} · 不含禁言"
            if st["events"].get(4)
            else "不含禁言",
        ),
        (
            "互动场次",
            f"{_fmt_count(st['lives'])} 场",
            f"场均 {st['interactions'] / max(st['lives'], 1):.1f} 次",
        ),
        ("互动频道", f"{st['channels']} 个", f"其中 {st['paid_channels']} 位收到打米"),
        ("活跃天数", f"{st['active_days']} 天", f"最长连续 {st['streak']} 天"),
        ("打米", f"{_fmt_money(st['payment'])} 元", "礼物 / SC / 大航海"),
    ]
    profile = [
        (
            "复读机指数",
            f"{float(insight.get('repeaterIndex') or 0):.1f}x",
            "越高越爱跟风复读",
        ),
        ("独立发言率", _pct(float(insight.get("uniqueMessageRatio") or 0)), "原创弹幕占比"),
        (
            "平均弹幕长度",
            f"{float(insight.get('avgMessageLength') or 0):.1f} 字",
            "单条弹幕平均字数",
        ),
        ("表情包占比", _pct(float(insight.get("emojiRatio") or 0)), "含表情的弹幕"),
        ("深夜发言", _pct(float(insight.get("nightOwlRatio") or 0)), "01:00-05:00 占比"),
        (
            "最常复读",
            f"{int(insight.get('maxRepeatedCount') or 0)} 次",
            f"「{str(insight.get('maxRepeatedText') or '—')[:10]}」",
        ),
    ]

    highlights: list[tuple[str, str, str]] = []
    if st["streak"]:
        highlights.append(("最长连续活跃", f"{st['streak']} 天", "按有互动的日期连续计算"))
    if st["favorite_weekday"] >= 0:
        highlights.append(
            (
                "常互动时段",
                f"{_WEEKDAYS[st['favorite_weekday']]} {st['favorite_hour']:02d}:00",
                f"该时段 {_fmt_count(st['peak'])} 次",
            )
        )
    if st["areas"]:
        top_area = st["areas"][0]
        highlights.append(
            (
                "常看分区",
                str(top_area.get("name") or "—"),
                f"{_fmt_count(int(top_area.get('count') or 0))} 场",
            )
        )
    top_channel = st["top_channel"]
    if top_channel and float(top_channel.get("loyaltyScore") or 0) > 10:
        highlights.append(
            (
                "真爱主播",
                str(top_channel.get("channelName") or "—"),
                f"综合亲密度 {float(top_channel.get('loyaltyScore') or 0):.1f} 分",
            )
        )
    night = float(insight.get("nightOwlRatio") or 0)
    if st["messages"] > 20:
        if night >= 0.35:
            highlights.append(("作息特征", "深夜修仙党", f"深夜发言 {_pct(night)}"))
        elif night <= 0.05:
            highlights.append(("作息特征", "健康作息", "极少在后半夜发言"))
        repeater = float(insight.get("repeaterIndex") or 0)
        unique = float(insight.get("uniqueMessageRatio") or 0)
        if repeater >= 2:
            highlights.append(("复读倾向", f"复读指数 {repeater:.1f}x", "倾向跟随大流复读"))
        elif unique >= 0.85:
            highlights.append(("复读倾向", "独立发言派", f"独创内容率 {_pct(unique)}"))
    if float(insight.get("emojiRatio") or 0) >= 0.25:
        highlights.append(
            ("表达习惯", "表情包达人", f"表情弹幕 {_pct(float(insight.get('emojiRatio') or 0))}")
        )

    total_events = max(sum(st["events"].values()), 1)
    mix = [
        (
            _EVENT_LABELS.get(key, f"类型 {key}"),
            f"{_fmt_count(value)} · {_pct(value / total_events)}",
            value / total_events,
        )
        for key, value in sorted(st["events"].items())
        if value > 0
    ]
    if st["blocks"]:
        mix.append(("禁言记录", _fmt_count(st["blocks"]), st["blocks"] / total_events))

    word_items = sorted(
        (
            (str(word), int(count or 0))
            for word, count in (result.get("wordCloud") or {}).items()
        ),
        key=lambda item: -item[1],
    )[:24]
    if word_items:
        words_html = (
            '<div class="tags">'
            + "".join(
                f'<span class="tag">{html.escape(word)} × {_fmt_count(count)}</span>'
                for word, count in word_items
            )
            + "</div>"
        )
    else:
        words_html = '<div class="card"><div class="note">暂无词频数据</div></div>'

    area_items = [
        (
            str(area.get("name") or "—"),
            f"{_fmt_count(int(area.get('count') or 0))} 场",
            int(area.get("count") or 0),
        )
        for area in st["areas"][:10]
    ]
    area_max = max((item[2] for item in area_items), default=1) or 1
    area_bars = [(name, value, count / area_max) for name, value, count in area_items]

    overview = (
        _cards(metrics)
        + _section("互动画像", "来自接口 insights", _cards(profile))
        + (_section("行为摘要", "", _cards(highlights, 2)) if highlights else "")
        + _section("留痕构成", f"共 {_fmt_count(sum(st['events'].values()))} 条", _bars(mix))
        + _section("高频词 Top 24", "分词统计", words_html)
        + _section("分区偏好 Top 10", "按有互动的场次统计", _bars(area_bars))
    )

    channels = _top_channels(result)
    channel_rows = [
        [
            str(index),
            row["name"],
            _fmt_count(row["messages"]),
            _fmt_money(row["payment"]),
            str(row["active_days"]) if row["active_days"] else "—",
            str(row["lives"]) if row["lives"] else "—",
            f"{row['loyalty']:.1f}" if row["loyalty"] else "—",
            _fmt_date(row["last"]),
        ]
        for index, row in enumerate(channels, 1)
    ]

    payments = [item for item in result.get("topPayments") or [] if isinstance(item, dict)][:12]
    payment_rows = [
        [
            _fmt_date(int(item.get("timestamp") or 0)),
            str(item.get("typeLabel") or _EVENT_LABELS.get(int(item.get("type") or 0), "其他")),
            str(item.get("name") or "—"),
            _fmt_money(float(item.get("amount") or 0)),
            str(item.get("channelName") or "—"),
        ]
        for item in payments
    ]

    aliases = [a for a in result.get("aliasTimeline") or [] if isinstance(a, dict)]
    same_timestamp = all(
        str(alias.get("firstSeen")) == str(alias.get("lastSeen")) for alias in aliases
    )
    if aliases and same_timestamp:
        name_headers = ["昵称", "记录时间"]
        name_classes = ["name", "dur"]
        name_rows = [
            [str(alias.get("name") or "—"), _fmt_date(int(alias.get("firstSeen") or 0))]
            for alias in aliases
        ]
    elif aliases:
        name_headers = ["昵称", "首次", "最近"]
        name_classes = ["name", "dur", "dur"]
        name_rows = [
            [
                str(alias.get("name") or "—"),
                _fmt_date(int(alias.get("firstSeen") or 0)),
                _fmt_date(int(alias.get("lastSeen") or 0)),
            ]
            for alias in aliases
        ]
    else:
        name_headers = ["昵称"]
        name_classes = ["name"]
        name_rows = [[name] for name in names]

    rhythm_note = (
        f"按互动次数 · 最活跃 {_WEEKDAYS[st['favorite_weekday']]} {st['favorite_hour']:02d}:00"
        if st["favorite_weekday"] >= 0
        else "按互动次数"
    )
    detail = (
        (
            _section(
                "主播排行 Top 25",
                "按弹幕数排序",
                _table(
                    ["#", "主播", "弹幕", "打米", "活跃天", "场次", "亲密度", "最近"],
                    channel_rows,
                    ["num", "name", "money", "money", "money", "money", "money", "dur"],
                ),
            )
            if channel_rows
            else _section(
                "主播排行",
                "",
                '<div class="card"><div class="note">暂无频道数据</div></div>',
            )
        )
        + (
            _section(
                "打米记录 Top 12",
                "按金额排序",
                _table(
                    ["日期", "类型", "名称", "金额", "主播"],
                    payment_rows,
                    ["dur", "dur", "name", "money", "name"],
                ),
            )
            if payment_rows
            else ""
        )
        + _section(
            "作息分布",
            rhythm_note,
            _heatmap(st["rhythm"], st["peak"])
            if st["rhythm"]
            else '<div class="card"><div class="note">暂无作息数据</div></div>',
        )
        + _section(
            "年度活跃",
            "弹幕 / 互动 / 活跃天 / 打米",
            _table(
                ["年份", "弹幕", "互动", "活跃天", "打米"],
                st["years"],
                ["name", "money", "money", "money", "money"],
            ),
        )
        + (
            _section(
                "昵称演变",
                "接口记录",
                _table(name_headers, name_rows, name_classes),
            )
            if name_rows
            else ""
        )
    )
    return _shell(
        title,
        sub,
        overview
        + '<div class="divider"><span>主播排行与打米明细</span></div>'
        + detail
        + '<div class="foot">数据来源 danmakus.com（ukamnads.icu）· 由机器人自动生成</div>',
    )


def _deep_text(uid: int, result: dict, range_label: str) -> str:
    st = _collect_stats(result)
    insight = st["insights"]
    lines = [
        f"UID {uid} 直播成分分析（{range_label}）",
        f"弹幕 {_fmt_count(st['messages'])} | 互动 {_fmt_count(st['interactions'])} 次 | "
        f"场次 {_fmt_count(st['lives'])} | 频道 {st['channels']} | "
        f"活跃 {st['active_days']} 天 | 打米 {_fmt_money(st['payment'])} 元",
        f"复读 {float(insight.get('repeaterIndex') or 0):.1f}x | "
        f"独立发言 {_pct(float(insight.get('uniqueMessageRatio') or 0))} | "
        f"平均长度 {float(insight.get('avgMessageLength') or 0):.1f} 字 | "
        f"表情 {_pct(float(insight.get('emojiRatio') or 0))} | "
        f"深夜 {_pct(float(insight.get('nightOwlRatio') or 0))}",
        f"最常复读「{str(insight.get('maxRepeatedText') or '—')[:10]}」"
        f"×{int(insight.get('maxRepeatedCount') or 0)} | 最长连续活跃 {st['streak']} 天"
        + (
            f" | 常互动 {_WEEKDAYS[st['favorite_weekday']]} {st['favorite_hour']:02d}:00"
            if st["favorite_weekday"] >= 0
            else ""
        ),
    ]
    if st["areas"]:
        top_area = st["areas"][0]
        lines.append(
            f"常看分区：{top_area.get('name')}（{_fmt_count(int(top_area.get('count') or 0))} 场）"
        )
    lines.append("主播排行：")
    for index, row in enumerate(_top_channels(result, 10), 1):
        lines.append(
            f"{index}. {row['name']} 弹幕{_fmt_count(row['messages'])} "
            f"打米{_fmt_money(row['payment'])} 活跃{row['active_days']}天 "
            f"{row['lives']}场 亲密度{row['loyalty']:.1f}"
        )
    payments = [item for item in result.get("topPayments") or [] if isinstance(item, dict)][:5]
    if payments:
        lines.append("打米记录：")
        for item in payments:
            lines.append(
                f"  {_fmt_date(int(item.get('timestamp') or 0))} "
                f"{item.get('typeLabel') or '其他'} {item.get('name') or '—'} "
                f"{_fmt_money(float(item.get('amount') or 0))}元 @{item.get('channelName') or '—'}"
            )
    words = sorted(
        (
            (str(word), int(count or 0))
            for word, count in (result.get("wordCloud") or {}).items()
        ),
        key=lambda item: -item[1],
    )[:12]
    if words:
        lines.append("高频词：" + "、".join(f"{word}×{_fmt_count(count)}" for word, count in words))
    if st["years"]:
        lines.append("年度：" + " / ".join(f"{row[0]} {row[1]}条" for row in st["years"]))
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
