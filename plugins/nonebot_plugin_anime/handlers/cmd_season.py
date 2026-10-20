from datetime import datetime
from typing import List
from ..core import bgm_manager
from ..core.anime_session import set_session, get_user_session
from ..core.anime_formatting import format_season_results_page, format_week_results_page
from ..core.anime_time import get_current_season, parse_single_date, validate_year
from ..core.anime_permissons import is_private_or_allowed_group
from ..config import MONTH_NAMES
from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, GroupMessageEvent
from nonebot.exception import ActionFailed
from nonebot.rule import Rule, to_me
from nonebot.params import CommandArg


# ==================== 番剧查看命令 ====================
anime_view = on_command("anime view", aliases={"番剧查看"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_view_week = on_command("anime view week", aliases={"星期查看"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_view_today = on_command("anime view today", aliases={"今天有什么番"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== 合并转发辅助 ====================
FORWARD_NODE_LINES = 10  # 每个合并转发节点包含的番剧行数


def _anime_line_text(anime_info) -> str:
    """番剧列表单行文本：显示名 + 评分"""
    basic_info = anime_info.get('basic_info', {})
    chinese_title = basic_info.get('chinese_title', '').strip()
    original_title = basic_info.get('original_title', '').strip()
    display_title = chinese_title if chinese_title else original_title
    score = anime_info.get('rating', {}).get('score')
    score_text = f" 评分：{score}" if score else " 评分：暂无"
    return f"{display_title}{score_text}"


async def _send_nodes(bot: Bot, event: Event, nodes: list) -> bool:
    """调用协议端 API 发送合并转发；失败返回 False"""
    try:
        if isinstance(event, GroupMessageEvent):
            await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=nodes)
        else:
            await bot.call_api("send_private_forward_msg", user_id=int(event.get_user_id()), messages=nodes)
        return True
    except ActionFailed:
        logger.warning("合并转发发送失败（协议端不支持或超出限制），降级为分页文本")
        return False
    except Exception:
        logger.opt(exception=True).warning("合并转发发送异常，降级为分页文本")
        return False


def _bot_uin(bot: Bot) -> int:
    try:
        return int(bot.self_id)
    except (TypeError, ValueError):
        return 10000


async def _send_forward_nodes(bot: Bot, event: Event, title: str, lines: List[str]) -> bool:
    """把文本行按每节点 FORWARD_NODE_LINES 行打包成合并转发发送。

    编号由调用方写入行首，全局连续，与会话 search_results 索引一一对应，
    因此转发后用户仍可输入编号查看详情。
    发送失败（协议端不支持/超限）返回 False，由调用方降级为分页文本。
    """
    lines = [line for line in lines if line]
    if not lines:
        return False

    uin = _bot_uin(bot)
    total = len(lines)
    nodes = []
    for start in range(0, total, FORWARD_NODE_LINES):
        chunk = lines[start:start + FORWARD_NODE_LINES]
        if total > FORWARD_NODE_LINES:
            nickname = f"{title}（{start + 1}-{start + len(chunk)}）"
        else:
            nickname = title
        nodes.append(
            MessageSegment.node_custom(
                user_id=uin,
                nickname=nickname[:60],
                content=Message("\n".join(chunk)),
            )
        )

    return await _send_nodes(bot, event, nodes)


async def _send_forward_sections(bot: Bot, event: Event, sections: List[tuple]) -> bool:
    """按「分组 = 气泡」构造合并转发：sections 为 [(节点昵称, [行, ...]), ...]。

    用于星期查看：每个星期一个气泡，编号仍由调用方全局连续编号。
    """
    cleaned = [(name, [line for line in lines if line]) for name, lines in sections]
    cleaned = [(name, lines) for name, lines in cleaned if lines]
    if not cleaned:
        return False

    uin = _bot_uin(bot)
    nodes = [
        MessageSegment.node_custom(
            user_id=uin,
            nickname=str(name)[:60],
            content=Message("\n".join(lines)),
        )
        for name, lines in cleaned
    ]

    return await _send_nodes(bot, event, nodes)


# ==================== 番剧查看处理 ====================
@anime_view.handle()
async def handle_anime_view(bot: Bot, event: Event, arg: Message = CommandArg()):
    """处理番剧季度查看指令"""

    args = arg.extract_plain_text().strip()

    if not args:
        await anime_view.finish("请指定季度，格式如：2025年4月")

    # 解析参数
    result = parse_single_date(args)
    if not result[0]:
        await anime_view.finish("季度格式错误，请使用如：2025年4月")
    year, month = result

    # 验证年份范围
    if not validate_year(year):
        await anime_view.finish("年份范围超出")

    # 获取月份名称
    month_name = MONTH_NAMES.get(month, f"{month}月")

    # 获取该季度的番剧
    season_animes = bgm_manager.get_anime_by_season(year, month)

    if not season_animes:
        await anime_view.finish(f"{year}年{month_name}季度没有找到番剧数据")

    # 按评分降序排列（评分缺失的排在最后）
    def sort_key(item):
        title, info = item
        score = info.get('rating', {}).get('score')
        if score is None:
            return -1
        return float(score)

    season_animes.sort(key=sort_key, reverse=True)

    # 全量文本行（编号全局连续，与 search_results 索引一一对应，保证编号交互可用）
    lines = []
    for i, (anime_title, anime_info) in enumerate(season_animes, 1):
        basic_info = anime_info.get('basic_info', {})
        chinese_title = basic_info.get('chinese_title', '').strip()
        original_title = basic_info.get('original_title', '').strip()
        display_title = chinese_title if chinese_title else original_title
        broadcast_day = basic_info.get('broadcast_day', '').strip()
        day_info = f"【{broadcast_day}】" if broadcast_day else ""
        score = anime_info.get('rating', {}).get('score')
        score_text = f" 评分：{score}" if score else " 评分：暂无"
        lines.append(f"{i}. {display_title}{day_info}{score_text}")

    # 会话保存完整列表：只有一页，编号可继续用于查看详情
    set_session(
        event,
        'view_season',  # 会话类型
        search_results=season_animes,  # 搜索结果
        search_type="季度查看",
        search_query=f"{year}-{month:02d}",
        current_page=0,
        page_size=len(season_animes),  # 一次性全量输出
        total_pages=1,
        view_year=year,
        view_month=month,
        view_month_name=month_name
    )

    title = f"{year}年{month_name}番剧"
    if await _send_forward_nodes(bot, event, title, lines):
        await anime_view.send(f"共 {len(season_animes)} 部，输入编号查看详情（1~{len(season_animes)}）")
    else:
        # 降级：合并转发不可用时回退到原来的分页文本
        session = get_user_session(event)
        session.page_size = 20
        session.total_pages = (len(season_animes) + 19) // 20
        selection_msg = format_season_results_page(session, f"{year}年{month_name}番剧")
        await anime_view.send(selection_msg)


@anime_view_week.handle()
async def handle_anime_view_week(bot: Bot, event: Event, arg: Message = CommandArg()):
    """处理番剧星期查看指令"""

    args = arg.extract_plain_text().strip()
    season_arg = None
    target_weekday = None

    if not args:
        await anime_view_week.finish("请指定季度，格式如：2025年4月 或 2025年4月 星期一")

    # 解析参数
    parts = args.split()
    if len(parts) == 1:
        season_arg = parts[0]
        target_weekday = None
    elif len(parts) == 2:
        season_arg = parts[0]
        target_weekday = parts[1]
    else:
        await anime_view_week.finish("参数格式错误，请使用：2025年4月 或 2025年4月 星期一")

    # 解析季度参数
    result = parse_single_date(season_arg)
    if not result[0]:
        await anime_view_week.finish("季度格式错误，请使用如：2025年4月")
    year, month = result

    # 验证年份范围
    if not validate_year(year):
        await anime_view_week.finish("年份范围超出")

    # 获取月份名称
    month_name = MONTH_NAMES.get(month, f"{month}月")

    weekday_mapping = {
        '星期一': '星期一', '周一': '星期一', '礼拜一': '星期一',
        '星期二': '星期二', '周二': '星期二', '礼拜二': '星期二',
        '星期三': '星期三', '周三': '星期三', '礼拜三': '星期三',
        '星期四': '星期四', '周四': '星期四', '礼拜四': '星期四',
        '星期五': '星期五', '周五': '星期五', '礼拜五': '星期五',
        '星期六': '星期六', '周六': '星期六', '礼拜六': '星期六',
        '星期日': '星期日', '周日': '星期日', '星期天': '星期日', '礼拜天': '星期日'
    }

    if target_weekday:
        normalized_weekday = weekday_mapping.get(target_weekday)
        if not normalized_weekday:
            await anime_view_week.finish("请使用正确的星期格式，如：星期一、周二、周三等")
        target_weekday = normalized_weekday

    # 获取该季度的番剧并按星期分组
    weekday_groups = bgm_manager.get_anime_by_season_and_weekday(year, month)

    if not weekday_groups or all(not animes for animes in weekday_groups.values()):
        await anime_view_week.finish(f"{year}年{month_name}季度没有找到番剧数据")

    # 根据是否指定星期，构建不同的番剧列表
    if target_weekday:
        # 只显示指定星期的番剧
        if target_weekday in weekday_groups and weekday_groups[target_weekday]:
            filtered_animes = weekday_groups[target_weekday]
            search_query = f"{year}-{month:02d} {target_weekday}"
        else:
            await anime_view_week.finish(f"{year}年{month_name}季度{target_weekday}没有找到番剧")
            return
    else:
        # 显示所有番剧，按星期顺序排列
        filtered_animes = []
        weekday_order = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日', '其他']

        for weekday in weekday_order:
            if weekday in weekday_groups and weekday_groups[weekday]:
                # 为每个星期的番剧添加星期标签
                for title, info in weekday_groups[weekday]:
                    # 在番剧信息中添加星期标签，方便显示
                    if 'weekday' not in info:
                        info['weekday'] = weekday
                    filtered_animes.append((title, info))

        search_query = f"{year}-{month:02d} 所有星期"

    # 全量文本行（编号全局连续，与 search_results 索引一一对应，保证编号交互可用）
    lines = []
    sections = []
    if target_weekday:
        lines = [f"{i}. {_anime_line_text(anime_info)}"
                 for i, (anime_title, anime_info) in enumerate(filtered_animes, 1)]
    else:
        # 按星期分割气泡：每个星期一个转发节点，编号跨节点全局连续
        index = 0
        for weekday in ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日', '其他']:
            group = weekday_groups.get(weekday) or []
            if not group:
                continue
            group_lines = [f"{year}年{month_name}季度番剧 {weekday}"]
            for anime_title, anime_info in group:
                index += 1
                group_lines.append(f"{index}. {_anime_line_text(anime_info)}")

            sections.append((" ", group_lines))

    # 会话保存完整列表：只有一页，编号可继续用于查看详情
    set_session(
        event,
        'view_week',  # 会话类型
        search_results=filtered_animes,  # 搜索结果
        search_type="星期查看",
        search_query=search_query,
        current_page=0,
        page_size=len(filtered_animes),  # 一次性全量输出
        total_pages=1,
        view_year=year,
        view_month=month,
        view_month_name=month_name,
        view_target_weekday=target_weekday,
        view_weekday_groups=weekday_groups  # 保留分组信息（降级分页时使用）
    )

    if target_weekday:
        title = f"{year}年{month_name}季度番剧 {target_weekday}"
    else:
        title = f"{year}年{month_name}季度番剧"

    if target_weekday:
        forward_ok = await _send_forward_nodes(bot, event, title, lines)
    else:
        forward_ok = await _send_forward_sections(bot, event, sections)

    if forward_ok:
        await anime_view_week.send(f"共 {len(filtered_animes)} 部，输入编号查看详情（1~{len(filtered_animes)}）")
    else:
        # 降级：合并转发不可用时回退到原来的分页文本
        session = get_user_session(event)
        session.page_size = 30
        session.total_pages = (len(filtered_animes) + 29) // 30
        await anime_view_week.send(format_week_results_page(session))


@anime_view_today.handle()
async def handle_anime_view_today(event: Event):
    """处理今天有什么番指令"""

    # 获取当前日期
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day

    # 获取当前星期
    weekdays_chinese = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_num = now.weekday()
    current_weekday = weekdays_chinese[weekday_num]

    # 获取当前季度
    season_year, season_month = get_current_season()

    # 获取月份名称
    month_name = MONTH_NAMES.get(season_month, f"{season_month}月")

    # 获取今天播出的番剧
    today_animes = bgm_manager.get_today_animes()

    if not today_animes:
        await anime_view_today.finish(
            f"今天是{current_year}年{current_month}月{current_day}日 {current_weekday}\n"
            f"在{season_year}年{month_name}季度中，{current_weekday}没有找到番剧播出"
        )

    # 设置会话
    set_session(
        event,
        'view_season',  # 使用季度查看会话类型
        search_results=today_animes,
        search_type="今天番剧",
        search_query=f"today-{current_weekday}",
        current_page=0,
        page_size=30,
        view_year=season_year,
        view_month=season_month,
        view_month_name=month_name
    )

    # 格式化输出
    output_lines = [
        f"今天是{current_year}年{current_month}月{current_day}日 {current_weekday}",
        f"在{season_year}年{month_name}季度中，{current_weekday}播出的番剧有："
    ]

    for i, (title, anime_info) in enumerate(today_animes[:30], 1):  # 最多显示30条
        basic_info = anime_info.get('basic_info', {})

        # 使用chinese_title，如果没有则使用original_title
        chinese_title = basic_info.get('chinese_title', '').strip()
        original_title = basic_info.get('original_title', '').strip()
        display_title = chinese_title if chinese_title else original_title

        # 获取评分
        rating_info = anime_info.get('rating', {})
        score = rating_info.get('score')
        score_text = f" 评分：{score}" if score else " 评分：暂无"

        if display_title:
            output_lines.append(f"{i}. {display_title}{score_text}")

    # 如果番剧数量超过30条，显示翻页提示
    if len(today_animes) > 30:
        output_lines.append("")
        output_lines.append(f"共有 {len(today_animes)} 部番剧，输入编号查看详情，或输入 'n' 查看更多")
    else:
        output_lines.append("")
        output_lines.append("输入编号查看详情")

    await anime_view_today.send("\n".join(output_lines))
