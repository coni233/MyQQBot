import re
import random
from ..config import MIN_YEAR
from ..core import bgm_manager
from ..core.anime_filter import filter_anime, parse_score_value
from ..core.anime_permissons import is_private_or_allowed_group
from ..core.anime_time import parse_date_range_optimized, get_max_year, validate_year
from nonebot import on_command
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER


anime_random = on_command("anime random", aliases={"随机番剧"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== 随机命令处理 ====================
@anime_random.handle()
async def handle_anime_random(bot: Bot, event: Event, args=CommandArg()):
    """处理 anime random 命令"""

    params = args.extract_plain_text().strip().split()

    tags = []
    year = None
    month = None
    min_score = None
    max_score = None
    date_range = None

    # 解析参数
    i = 0
    while i < len(params):
        param = params[i]

        # 检查评分
        score_match = re.search(r'(?:bgm)?评分(.+)', param, re.IGNORECASE)
        if score_match:
            score_str = score_match.group(1).strip()
            try:
                score_desc, min_score, max_score = parse_score_value(score_str)
            except ValueError:
                await anime_random.finish(f"分数格式错误: {score_str}，请使用 0.0-10.0 的一位小数")
            i += 1
            continue

        # 检查时间范围
        if '-' in param or '到' in param or '至' in param:
            potential_range = param
            if i + 1 < len(params) and (params[i + 1] in ['年', '月'] or params[i + 1].isdigit()):
                potential_range += params[i + 1]
                i += 1

            start_date, end_date = parse_date_range_optimized(potential_range)
            if start_date and end_date:
                date_range = potential_range
                i += 1
                continue
            else:
                await anime_random.finish(
                    f"年份必须在{MIN_YEAR}-{get_max_year()}之间，月份必须是1、4、7、10月")

        # 检查时间（单个季度）
        time_match = re.search(r'(\d{4})年(\d{1,2})月', param)
        if time_match:
            try:
                year = int(time_match.group(1))
                month = int(time_match.group(2))
                if month not in [1, 4, 7, 10]:
                    await anime_random.finish("月份必须是1月、4月、7月或10月")
                if not validate_year(year):
                    await anime_random.finish(f"年份必须在{MIN_YEAR}-{get_max_year()}之间")
                i += 1
                continue
            except ValueError:
                pass

        # 检查只有年份的情况
        year_match = re.search(r'(\d{4})年', param)
        if year_match:
            try:
                year = int(year_match.group(1))
                if not validate_year(year):
                    await anime_random.finish(f"年份必须在{MIN_YEAR}-{get_max_year()}之间")
                i += 1
                continue
            except ValueError:
                pass

        # 剩下的参数都可能是标签
        if '+' in param:
            tags.extend(param.split('+'))
        else:
            tags.append(param)

        i += 1

    # 构建筛选条件描述和 filters 字典
    filters = {}
    condition_desc = []
    if tags:
        filters['tags'] = tags
        condition_desc.append(f"标签: {'+'.join(tags)}")
    if date_range:
        filters['date_range'] = date_range
        condition_desc.append(f"时间范围: {date_range}")
    elif year and month:
        filters['year'] = year
        filters['month'] = month
        condition_desc.append(f"时间: {year}年{month}月")
    elif year:
        filters['year'] = year
        condition_desc.append(f"时间: {year}年")
    if min_score is not None:
        filters['score_min'] = min_score
        condition_desc.append(f"BGM评分: ≥{min_score}")
    if max_score is not None:
        filters['score_max'] = max_score
        # 如果已有 ≥min，补充为范围
        if min_score is not None:
            condition_desc[-1] = f"BGM评分: {min_score}-{max_score}"
        else:
            condition_desc.append(f"BGM评分: ≤{max_score}")

    condition_text = "，".join(condition_desc) if condition_desc else "无筛选条件"

    await anime_random.send(f"正在随机选择番剧...\n筛选条件: {condition_text}")

    all_data = bgm_manager.load_all_data()
    results = filter_anime(all_data, filters)

    if results:
        title_cn, anime_info = random.choice(results)
        message_parts = await bgm_manager.create_anime_message(title_cn, anime_info)
        await bot.send(event, message_parts)
    else:
        await anime_random.finish(f"未找到符合条件的番剧\n筛选条件: {condition_text}")
