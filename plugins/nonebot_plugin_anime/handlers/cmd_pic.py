import os
from typing import Dict, List, Optional, Tuple

from ..core import bgm_manager, season_poster_generator
from ..core.anime_session import set_session
from ..core.anime_time import parse_single_date, validate_year, normalize_weekday
from ..core.anime_permissons import is_private_or_allowed_group
from ..config import MONTH_NAMES
from .cmd_season import _send_nodes, _bot_uin

from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import Rule


# ==================== 绘图命令 ====================
anime_view_poster = on_command("anime view poster", aliases={"番剧查看图"}, priority=5,
                               rule=Rule(is_private_or_allowed_group))
anime_week_poster = on_command("anime view week poster", aliases={"星期查看图"}, priority=5,
                               rule=Rule(is_private_or_allowed_group))

WEEKDAY_ORDER = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日', '其他']


def _to_poster_items(pairs: List[Tuple[str, Dict]]) -> List[Dict]:
    """把 (显示名, 条目) 列表转成绘图用数据"""
    items = []
    for title, info in pairs:
        bi = info.get('basic_info') or {}
        tags = sorted((info.get('tags') or []), key=lambda t: t.get('count', 0), reverse=True)
        items.append({
            'id': str(info.get('id') or ''),
            'title': title,
            'jp': (bi.get('original_title') or '').strip(),
            'eps': str(bi.get('episodes') or '').strip(),
            'day': (bi.get('broadcast_day') or '').strip() or '其他',
            'score': (info.get('rating') or {}).get('score') or 0,
            'tags': [t.get('name', '') for t in tags if t.get('name')][:season_poster_generator.MAX_TAGS],
            'cover_url': info.get('cover_url'),
        })
    return items


async def _send_poster_pages(bot: Bot, event: Event, pages: List[Tuple[str, str]]) -> bool:
    """合并转发每页一张图；失败则逐张直接发送"""
    if not pages:
        return False

    nodes = [
        MessageSegment.node_custom(
            user_id=_bot_uin(bot),
            nickname=nickname[:60],
            content=Message(MessageSegment.image(f"file:///{path}")),
        )
        for nickname, path in pages
    ]

    ok = await _send_nodes(bot, event, nodes)
    if not ok:
        await bot.send(f"发送番剧图失败，请稍后再试")
    return ok


def _cleanup(paths: List[str]) -> None:
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.unlink(path)
        except Exception:
            pass


# ==================== 番剧查看图 ====================
@anime_view_poster.handle()
async def handle_anime_view_poster(bot: Bot, event: Event, arg: Message = CommandArg()):
    """番剧查看图 <年月>：把该季度番剧绘制成图片"""
    args = arg.extract_plain_text().strip()

    if not args:
        await anime_view_poster.finish("使用方法：\n番剧查看图 <年月>\n例如：番剧查看图 2026年4月")

    result = parse_single_date(args)
    if not result[0]:
        await anime_view_poster.finish("季度格式错误，请使用如：2026年4月")
    year, month = result

    if not validate_year(year):
        await anime_view_poster.finish("年份范围超出")

    month_name = MONTH_NAMES.get(month, f"{month}月")

    season_animes = bgm_manager.get_anime_by_season(year, month)
    if not season_animes:
        await anime_view_poster.finish(f"{year}年{month_name}季度没有找到番剧数据")

    # 与文本版一致：按 bgm 评分降序（缺失排最后）
    season_animes.sort(key=lambda x: float((x[1].get('rating') or {}).get('score') or 0), reverse=True)

    # 会话：编号与图内编号一致，发完图仍可输入编号查看详情
    set_session(
        event,
        'view_season',
        search_results=season_animes,
        search_type="季度查看图",
        search_query=f"{year}-{month:02d}",
        current_page=0,
        page_size=len(season_animes),
        total_pages=1,
        view_year=year,
        view_month=month,
        view_month_name=month_name
    )

    items = _to_poster_items(season_animes)
    per = season_poster_generator.PER_IMAGE
    await anime_view_poster.send(f"正在绘制，请稍候...")

    pages: List[Tuple[str, str]] = []
    title = f"{year}年{month_name}番剧"
    for start in range(1, len(items) + 1, per):
        page_items = items[start - 1:start - 1 + per]
        path = await season_poster_generator.generate_page(page_items, title, start=start, total=len(items))
        if not path:
            continue
        pages.append((f"{title}（{start}-{start + len(page_items) - 1}）", path))

    if not pages:
        await anime_view_poster.finish("绘图失败，请稍后重试")

    try:
        await _send_poster_pages(bot, event, pages)
    finally:
        _cleanup([path for _, path in pages])

    await anime_view_poster.send(f"共 {len(items)} 部，输入编号查看详情（1~{len(items)}）")


# ==================== 星期查看图 ====================
@anime_week_poster.handle()
async def handle_anime_week_poster(bot: Bot, event: Event, arg: Message = CommandArg()):
    """星期查看图 <年月> [星期X]：按星期分组绘图"""
    args = arg.extract_plain_text().strip()

    if not args:
        await anime_week_poster.finish("使用方法：\n星期查看图 <年月> [星期X]\n例如：星期查看图 2026年4月\n　　　星期查看图 2026年4月 星期一")

    parts = args.split()
    if len(parts) > 2:
        await anime_week_poster.finish("参数格式错误，请使用：2026年4月 或 2026年4月 星期一")

    target_weekday = None
    if len(parts) == 2:
        target_weekday = normalize_weekday(parts[1])
        if not target_weekday:
            await anime_week_poster.finish("请使用正确的星期格式，如：星期一、周二、周三等")

    result = parse_single_date(parts[0])
    if not result[0]:
        await anime_week_poster.finish("季度格式错误，请使用如：2026年4月")
    year, month = result

    if not validate_year(year):
        await anime_week_poster.finish("年份范围超出")

    month_name = MONTH_NAMES.get(month, f"{month}月")
    weekday_groups = bgm_manager.get_anime_by_season_and_weekday(year, month)

    if not weekday_groups or all(not animes for animes in weekday_groups.values()):
        await anime_week_poster.finish(f"{year}年{month_name}季度没有找到番剧数据")

    # 选定要绘制的星期（指定则只画该天），并按顺序展平成会话列表
    days = [target_weekday] if target_weekday else WEEKDAY_ORDER
    plan: List[Tuple[str, List[Dict], int]] = []      # (星期, 绘图数据, 该组起始编号)
    flat: List[Tuple[str, Dict]] = []
    index = 0
    for day in days:
        group = weekday_groups.get(day) or []
        if not group:
            continue
        pairs = list(group)
        plan.append((day, _to_poster_items(pairs), index + 1))
        flat.extend(pairs)
        index += len(pairs)

    if not flat:
        which = target_weekday or '该季度'
        await anime_week_poster.finish(f"{year}年{month_name}{which}没有找到番剧")

    # 会话：编号与图内编号一致
    set_session(
        event,
        'view_week',
        search_results=flat,
        search_type="星期查看图",
        search_query=f"{year}-{month:02d} {target_weekday or '所有星期'}",
        current_page=0,
        page_size=len(flat),
        total_pages=1,
        view_year=year,
        view_month=month,
        view_month_name=month_name,
        view_target_weekday=target_weekday,
        view_weekday_groups=weekday_groups
    )

    per = season_poster_generator.PER_IMAGE
    await anime_week_poster.send(f"正在绘制，请稍候...")

    pages: List[Tuple[str, str]] = []
    for day, items, start in plan:
        title = f"{year}年{month_name} {day}"
        for offset in range(0, len(items), per):
            page_items = items[offset:offset + per]
            page_start = start + offset
            path = await season_poster_generator.generate_page(
                page_items, title, start=page_start, total=len(items))
            if not path:
                continue
            if len(items) > per:
                nickname = f"{title}（{page_start}-{page_start + len(page_items) - 1}）"
            else:
                nickname = title
            pages.append((nickname, path))

    if not pages:
        await anime_week_poster.finish("绘图失败，请稍后重试")

    try:
        await _send_poster_pages(bot, event, pages)
    finally:
        _cleanup([path for _, path in pages])

    await anime_week_poster.send(f"共 {len(flat)} 部，输入编号查看详情（1~{len(flat)}）")
