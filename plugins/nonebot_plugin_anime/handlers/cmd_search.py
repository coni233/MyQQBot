import os
from typing import Dict, List, Tuple
from ..config import STAFF_ROLE_MAPPING, FILTER_KEYWORDS_LOWER
from ..core import bgm_manager
from ..core.anime_filter import filter_anime, parse_score_value, get_display_title
from ..core.anime_session import get_user_session, set_session, cleanup_old_sessions
from ..core.anime_formatting import format_search_results_page, format_cv_search_results_page, format_cv_select_page, format_char_search_results_page
from ..core.anime_permissons import is_private_or_allowed_group
from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.rule import Rule, to_me
from nonebot.params import CommandArg


def _split_tag_value(value: str) -> List[str]:
    """拆分标签字符串为标签列表，支持 + 空格 , 三种分隔符"""
    for delimiter in ['+', ' ', ',']:
        if delimiter in value:
            return [t.strip() for t in value.split(delimiter) if t.strip()]
    return [value.strip()]


def _parse_filters(args_text: str) -> Tuple[Dict, str]:
    """解析筛选条件字典和条件描述文本"""
    tokens = args_text.strip().split()
    if not tokens:
        return {}, ""

    filters = {}
    desc_parts = []

    i = 0
    keyword_parts = []

    while i < len(tokens):
        if tokens[i].lower() in FILTER_KEYWORDS_LOWER:
            break
        keyword_parts.append(tokens[i])
        i += 1

    if keyword_parts:
        kw = ' '.join(keyword_parts)
        filters['keyword'] = kw
        desc_parts.append(f"关键词 '{kw}'")

    while i < len(tokens):
        token = tokens[i]
        token_lower = token.lower()

        # 确定筛选类型
        if token_lower in ('标签', 'tag', 'tags'):
            filter_type = 'tags'
        elif token_lower in ('分数', '评分', 'score'):
            filter_type = 'score'
        elif token_lower in ('cv', '声优', '配音'):
            filter_type = 'cv'
        elif token_lower in ('导演', 'director','监督'):
            filter_type = 'director'
        elif token_lower in ('制作', '动画制作'):
            filter_type = 'production'
        elif token_lower in ('staff', '制作人员'):
            filter_type = 'staff'
        elif token_lower in ('季度', '时间'):
            filter_type = 'season'
        elif token_lower in ('类型',):
            filter_type = 'media_type'
        elif token_lower in ('关键词', '标题', 'keyword'):
            filter_type = 'keyword'
        else:
            i += 1
            continue

        i += 1

        if filter_type == 'staff' and i < len(tokens):
            if tokens[i] in STAFF_ROLE_MAPPING:
                role = tokens[i]
                i += 1
                name_parts = []
                while i < len(tokens) and tokens[i].lower() not in FILTER_KEYWORDS_LOWER:
                    name_parts.append(tokens[i])
                    i += 1
                name = ' '.join(name_parts)
                filters['staff'] = name
                filters['staff_role'] = role
                desc_parts.append(f"{role} '{name}'")
                continue

        value_parts = []
        while i < len(tokens) and tokens[i].lower() not in FILTER_KEYWORDS_LOWER:
            value_parts.append(tokens[i])
            i += 1
        value = ' '.join(value_parts)
        if not value:
            continue

        if filter_type == 'tags':
            tags = _split_tag_value(value)
            filters['tags'] = tags
            desc_parts.append(f"标签: {'+'.join(tags)}")
        elif filter_type == 'score':
            score_desc, score_min, score_max = parse_score_value(value)
            filters['score_min'] = score_min
            filters['score_max'] = score_max
            desc_parts.append(f"评分 {score_desc}")
        elif filter_type == 'cv':
            filters['cv'] = value
            desc_parts.append(f"CV '{value}'")
        elif filter_type == 'director':
            filters['director'] = value
            desc_parts.append(f"导演 '{value}'")
        elif filter_type == 'production':
            filters['production'] = value
            desc_parts.append(f"制作公司 '{value}'")
        elif filter_type == 'staff':
            filters['staff'] = value
            desc_parts.append(f"制作人员 '{value}'")
        elif filter_type == 'season':
            filters['date_range'] = value
            desc_parts.append(f"时间范围 {value}")
        elif filter_type == 'media_type':
            filters['media_type'] = value
            desc_parts.append(f"类型 '{value}'")
        elif filter_type == 'keyword':
            filters['keyword'] = value
            for idx, d in enumerate(desc_parts):
                if d.startswith("关键词"):
                    desc_parts[idx] = f"关键词 '{value}'"
                    break
            else:
                desc_parts.insert(0, f"关键词 '{value}'")

    search_description = "，".join(desc_parts) if desc_parts else "无筛选条件"
    return filters, search_description


# ==================== 命令注册 ====================
anime_bgmsearch = on_command("anime bgmsearch", aliases={"bgm搜索", "番剧搜索"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_cvsearch = on_command("anime cvsearch", aliases={"cv搜索", "声优搜索"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_charsearch = on_command("anime charsearch", aliases={"角色搜索"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_bgmlist = on_command("anime bgmlist", aliases={"bgm详情", "番剧详情"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== BGM搜索命令处理 ====================
@anime_bgmsearch.handle()
async def handle_anime_bgmsearch(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理 anime bgmsearch 命令 — 支持多条件组合筛选"""
    cleanup_old_sessions()
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmsearch.finish(
            "使用方法:\n"
            "anime bgmsearch <番剧名> \n\n"
            "筛选条件: 标签/分数/cv/导演/staff/制作/时间/类型\n"
            "示例:\n"
            "  bgm搜索 标签 百合+日常 分数 6-8.5 cv 种田梨沙\n"
            "  bgm搜索 标签 百合 staff 脚本 花田十辉\n"
            "  bgm搜索 利兹与青鸟 标签 校园 分数 ≥8\n"
            "  bgm搜索 时间 2025年4月-2026年4月 标签 奇幻"
        )

    try:
        filters, search_description = _parse_filters(args_text)
    except ValueError as e:
        await anime_bgmsearch.finish(str(e))

    # 调用统一筛选引擎
    all_data = bgm_manager.load_all_data()
    results = filter_anime(all_data, filters)

    if not results:
        await anime_bgmsearch.finish(f"未找到符合条件的番剧\n筛选条件: {search_description}")

    # 如果只有一个结果，直接显示
    if len(results) == 1:
        title_cn, anime_info = results[0]
        message_parts = await bgm_manager.create_anime_message(title_cn, anime_info)
        await bot.send(event, message_parts)
        return

    # 设置搜索会话
    set_session(
        event,
        'search',
        search_results=results,
        search_type='filter',
        search_query=search_description,
        current_page=0
    )

    # 显示搜索结果第一页
    selection_msg = format_search_results_page(get_user_session(event), search_description)
    await anime_bgmsearch.send(selection_msg)


async def create_character_detail_message(character: Dict, anime_title: str) -> List[MessageSegment]:
    """创建角色详细信息消息"""
    message_parts = []

    image_url = character.get('image_url')
    if image_url:
        original_name = character.get('original_name', 'unknown')
        anime_id = character.get('anime_id')
        image_path = await bgm_manager.download_character_image(
            image_url, original_name, anime_id
        )
        if image_path:
            try:
                image_msg = MessageSegment.image(f"file:///{os.path.abspath(image_path)}")
                message_parts.append(image_msg)
            except Exception as e:
                logger.warning("添加角色图片失败")

    original_name = character.get('original_name', '未知')
    translated_name = character.get('translated_name', '')
    role_type = character.get('role', '未知')
    cv_name = character.get('cv', '未知')

    info_parts = [
        f"原名：{original_name}",
        f"译名：{translated_name if translated_name else '无'}",
        f"类型：{role_type}",
        f"CV：{cv_name}"
    ]

    text_msg = MessageSegment.text("\n".join(info_parts))
    message_parts.append(text_msg)

    return message_parts


async def display_anime_info(bot: Bot, event: Event, title_cn: str, anime_info: Dict, field: str):
    """显示番剧信息"""
    if field == 'staff':
        staff_message = bgm_manager.create_staff_message(title_cn, anime_info)
        await bot.send(event, staff_message)
    else:
        characters = anime_info.get('characters', [])
        if not characters:
            await bot.send(event, f"{title_cn} - 暂无角色信息")
            return

        set_session(
            event,
            'cv_list',
            characters=characters,
            anime_title=title_cn
        )

        character_list = []
        for i, char in enumerate(characters, 1):
            translated_name = char.get('translated_name', '')
            original_name = char.get('original_name', '')
            cv_name = char.get('cv', '未知')
            display_name = translated_name if translated_name else original_name
            character_list.append(f"{i}.{display_name}\nCV：{cv_name}")

        cv_message = f"{title_cn} - 角色CV信息：\n\n" + "\n".join(character_list)
        cv_message += f"\n\n请回复编号查看角色详细信息 (输入数字 1~{len(characters)})"
        await bot.send(event, cv_message)


# ==================== cv搜索命令处理 ====================
@anime_cvsearch.handle()
async def handle_anime_cvsearch(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理 anime cvsearch 命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_cvsearch.finish("使用方法: anime cvsearch <CV>")

    # 第一步：搜索CV名字
    cv_names = bgm_manager.search_cv_names(args_text)
    if not cv_names:
        await anime_cvsearch.finish(f"未找到包含 '{args_text}' 的CV")

    # 如果只有一个CV名字，直接搜索该CV的角色
    if len(cv_names) == 1:
        cv_name = cv_names[0]
        await search_characters_by_cv(bot, event, cv_name)
        return

    # 多个CV名字，设置CV选择会话
    set_session(
        event,
        'cv_select',
        search_results=[(cv_name, {"type": "cv_name"}) for cv_name in cv_names],
        search_type='cv_select',
        search_query=args_text,
        current_page=0
    )

    # 显示CV选择列表
    selection_msg = format_cv_select_page(get_user_session(event), f"包含 '{args_text}'")
    await anime_cvsearch.send(selection_msg)


async def search_characters_by_cv(bot: Bot, event: Event, cv_name: str):
    """搜索指定CV的角色"""
    # 搜索角色
    results = bgm_manager.search_characters_by_exact_cv(cv_name)
    if not results:
        await bot.send(event, f"未找到CV '{cv_name}' 配音的角色")
        return

    # 如果只有一个结果，直接显示
    if len(results) == 1:
        character_name, character_info = results[0]
        await display_character_detail_from_cvsearch(bot, event, character_info)
        return

    # 设置CV角色搜索会话
    set_session(
        event,
        'cv_search',
        search_results=results,
        search_type='cv_search',
        search_query=cv_name,
        current_page=0
    )

    # 显示搜索结果第一页
    selection_msg = format_cv_search_results_page(get_user_session(event), f"CV '{cv_name}'")
    await bot.send(event, selection_msg)


async def display_character_detail_from_cvsearch(bot: Bot, event: Event, character_info: Dict):
    """从CV搜索显示角色详细信息"""
    anime_title = character_info.get('anime_title', '未知番剧')
    message_parts = await create_character_detail_message(character_info, anime_title)
    await bot.send(event, message_parts)


# ==================== 角色搜索命令处理 ====================
@anime_charsearch.handle()
async def handle_anime_charsearch(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理 anime charsearch 命令"""
    cleanup_old_sessions()
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_charsearch.finish("使用方法: anime charsearch <角色名>")

    results = bgm_manager.search_characters_by_name(args_text)

    if not results:
        await anime_charsearch.finish(f"未找到包含 '{args_text}' 的角色")

    if len(results) == 1:
        character_name, character_info = results[0]
        anime_title = character_info.get('anime_title', '未知番剧')
        message_parts = await create_character_detail_message(character_info, anime_title)
        await bot.send(event, message_parts)
        return

    set_session(
        event,
        'char_search',
        search_results=results,
        search_type='char_search',
        search_query=args_text,
        current_page=0
    )

    selection_msg = format_char_search_results_page(get_user_session(event), f"包含 '{args_text}'")
    await bot.send(event, selection_msg)


# ==================== BGM列表命令处理 ====================
@anime_bgmlist.handle()
async def handle_anime_bgmlist(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理 anime bgmlist 命令"""
    cleanup_old_sessions()
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmlist.finish("使用方法:\n"
                                   "anime bgmlist <番剧名> staff\n"
                                   "anime bgmlist <番剧名> cv")

    parts = args_text.rsplit(' ', 1)
    if len(parts) < 2:
        await anime_bgmlist.finish("使用方法:\n"
                                   "anime bgmlist <番剧名> staff\n"
                                   "anime bgmlist <番剧名> cv")

    anime_name = parts[0].strip()
    field = parts[1].lower().strip()

    if field not in ['staff', 'cv']:
        await anime_bgmlist.finish(f"字段必须是 'staff' 或 'cv'，错误字段 '{field}'")

    # 搜索番剧
    results = bgm_manager.search_anime_by_keyword(anime_name)
    if not results:
        all_data = bgm_manager.load_all_data()
        fuzzy_results = []

        for dict_key, info in all_data.items():
            # 模糊匹配
            display_title = get_display_title(info) or str(dict_key)
            candidates = [display_title] + [a for a in info.get('aliases', []) if a]
            keywords = anime_name.split()
            if any(all(keyword in candidate for keyword in keywords) for candidate in candidates):
                fuzzy_results.append((display_title, info))

        if fuzzy_results:
            results = fuzzy_results
        else:
            await anime_bgmlist.finish(f"未找到包含 '{anime_name}' 的番剧")

    if len(results) == 1:
        title_cn, anime_info = results[0]
        await display_anime_info(bot, event, title_cn, anime_info, field)
    else:
        # 设置BGM列表会话
        set_session(
            event,
            'bgmlist',
            search_results=results,
            search_type=field,
            search_query=anime_name,
            current_page=0
        )

        # 显示搜索结果第一页
        selection_msg = format_search_results_page(get_user_session(event), f"包含 '{anime_name}'")
        await anime_bgmlist.send(selection_msg)