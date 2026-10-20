import math
import time

from typing import Callable
from .cmd_char import send_character_delete_list
from .cmd_score import display_user_scores
from .cmd_search import create_character_detail_message, search_characters_by_cv, display_character_detail_from_cvsearch, \
    display_anime_info
from .cmd_tag import display_anime_tags
from ..core import bgm_manager, bgm_api, user_score_manager, character_score_manager
from ..core.anime_formatting import format_search_results_page, format_cv_select_page, format_cv_search_results_page, \
    format_character_search_results_page, format_char_search_results_page, format_season_results_page, format_week_results_page
from ..core.anime_session import is_user_session_event, get_user_session, UserSession, clear_user_session

from nonebot import on_message, logger
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.rule import Rule
from nonebot.params import EventMessage


# ==================== 消息处理器 ====================
anime_session_handler = on_message(priority=10, block=True, rule=Rule(is_user_session_event))


async def _handle_pagination(
    bot: Bot,
    event: Event,
    user_input: str,
    session: UserSession,
    *,
    page_formatter: Callable = None,
    async_formatter: Callable = None,
) -> bool:
    """统一的翻页处理。返回 True 表示已处理翻页指令，调用方应 return"""
    if user_input in ('n', 'next', '下一页'):
        if session.current_page < session.total_pages - 1:
            session.current_page += 1
        else:
            await bot.send(event, "已经是最后一页了")
            return True
    elif user_input in ('p', 'prev', 'previous', '上一页'):
        if session.current_page > 0:
            session.current_page -= 1
        else:
            await bot.send(event, "已经是第一页了")
            return True
    elif user_input.startswith(('p', 'page')):
        page_text = user_input.replace('p', '').replace('age', '').strip()
        if page_text.isdigit():
            page_num = int(page_text) - 1
            if 0 <= page_num < session.total_pages:
                session.current_page = page_num
            else:
                await bot.send(event, f"页码无效，请输入 1~{session.total_pages} 之间的数字")
                return True
        else:
            await bot.send(event, "页码格式错误，请使用 'p2' 或 'page3' 格式")
            return True
    else:
        return False

    # 翻页成功，刷新页面
    if async_formatter:
        await async_formatter(bot, event, session)
    elif page_formatter:
        page_msg = page_formatter(session)
        await bot.send(event, page_msg)
    else:
        page_msg = format_search_results_page(session, f"{session.search_type} '{session.search_query}'")
        await bot.send(event, page_msg)
    return True


# ==================== 会话处理函数 ====================
@anime_session_handler.handle()
async def handle_anime_session(bot: Bot, event: Event, message: Message = EventMessage()):
    """处理所有会话消息 - 扩展版，包含所有会话类型"""
    # 获取当前会话
    session = get_user_session(event)
    user_input = message.extract_plain_text().strip().lower()

    # 更新时间戳
    session.timestamp = time.time()

    # 根据会话类型路由到不同的处理函数
    if session.session_type == 'search':
        await handle_search_session(bot, event, user_input, session)
    elif session.session_type == 'cv_list':
        await handle_cv_list_session(bot, event, user_input, session)
    elif session.session_type == 'bgmlist':
        await handle_bgmlist_session(bot, event, user_input, session)
    elif session.session_type == 'bgmtag':
        await handle_bgmtag_session(bot, event, user_input, session)
    elif session.session_type == 'score':
        await handle_score_session(bot, event, user_input, session)
    elif session.session_type == 'score_show':
        await handle_score_show_session(bot, event, user_input, session)
    elif session.session_type == 'bgmget':
        await handle_bgmget_session(bot, event, user_input, session)
    elif session.session_type == 'score_delete':
        await handle_score_delete_session(bot, event, user_input, session)  # 新增评分删除会话
    elif session.session_type == 'cv_search':
        await handle_cv_search_session(bot, event, user_input, session)
    elif session.session_type == 'cv_select':
        await handle_cv_select_session(bot, event, user_input, session)
    elif session.session_type == 'char_search':
        await handle_char_search_session(bot, event, user_input, session)
    elif session.session_type == 'character_rate':  # 新增角色评级会话
        await handle_character_rate_session(bot, event, user_input, session)
    elif session.session_type == 'character_delete':  # 新增角色评级删除会话
        await handle_character_delete_session(bot, event, user_input, session)
    elif session.session_type == 'view_season':  # 新增：季度查看会话
        await handle_view_season_session(bot, event, user_input, session)
    elif session.session_type == 'view_week':  # 新增：星期查看会话
        await handle_view_week_session(bot, event, user_input, session)


async def handle_bgmget_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理BGM获取会话 - 仅更新现有番剧"""
    if await _handle_pagination(bot, event, user_input, session):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await anime_session_handler.send(f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的番剧信息
        title_cn, anime_info = session.search_results[selection - 1]
        anime_id = anime_info.get('id')

        if anime_id:
            await anime_session_handler.send(f"正在获取番剧 '{title_cn}' 的最新数据...")

            anime_data = await bgm_api.fetch_anime_by_id(anime_id)
            if anime_data:
                # 通过名称搜索时只允许更新，不允许添加新番剧
                success = bgm_manager.update_anime_data(anime_data, anime_id, allow_add_new=False)
                if success:
                    message_parts = await bgm_manager.create_anime_message(title_cn, anime_data)
                    await bot.send(event, message_parts)
                    await anime_session_handler.send(f"已成功更新番剧数据")
                else:
                    await anime_session_handler.send("更新数据失败")
            else:
                await anime_session_handler.send("获取番剧数据失败")
        else:
            await anime_session_handler.send("该番剧没有ID信息，无法更新")

        # 清除会话
        clear_user_session(event)  # 改为使用 event


async def handle_bgmtag_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理标签管理会话 - 支持翻页"""
    if await _handle_pagination(bot, event, user_input, session):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")  # 修复
            return

        # 获取选择的番剧信息
        title_cn, anime_info = session.search_results[selection - 1]

        # 显示标签信息
        await display_anime_tags(bot, event, title_cn, anime_info)

        # 更新会话状态为已选择番剧
        session.current_anime = anime_info
        session.current_anime_title = title_cn
        session.timestamp = time.time()
        return


async def handle_search_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理搜索会话"""
    if await _handle_pagination(bot, event, user_input, session):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await anime_session_handler.send(f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        title, info = session.search_results[selection - 1]
        message_parts = await bgm_manager.create_anime_message(title, info)
        await bot.send(event, message_parts)

        # 不清除会话，用户可以继续浏览其他结果
        session.timestamp = time.time()
        return


async def handle_cv_list_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理CV list会话"""
    if user_input.isdigit():
        selection = int(user_input)
        total_characters = len(session.characters)

        if selection < 1 or selection > total_characters:
            await bot.send(f"无效的选择编号，请输入 1~{total_characters} 之间的数字")
            return

        character = session.characters[selection - 1]
        message_parts = await create_character_detail_message(character, session.anime_title)
        await bot.send(event, message_parts)
        session.timestamp = time.time()
        return


async def handle_cv_select_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理选择 CV会话"""
    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_cv_select_page(s, f"包含 '{s.search_query}'")
    ):
        return

    # CV选择处理
    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的CV名字
        cv_name, cv_info = session.search_results[selection - 1]
        session.selected_cv = cv_name

        # 搜索该CV的角色
        await search_characters_by_cv(bot, event, cv_name)

        # 不清除会话，用户可以继续浏览角色
        session.timestamp = time.time()
        return


async def handle_cv_search_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理CV搜索会话"""
    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_cv_search_results_page(s, f"CV '{s.search_query}'")
    ):
        return

    # 角色选择处理
    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的角色信息
        character_name, character_info = session.search_results[selection - 1]
        await display_character_detail_from_cvsearch(bot, event, character_info)

        # 不清除会话，用户可以继续浏览其他结果
        session.timestamp = time.time()
        return


async def handle_char_search_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理角色名搜索会话"""
    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_char_search_results_page(s, f"包含 '{s.search_query}'")
    ):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        character_name, character_info = session.search_results[selection - 1]
        anime_title = character_info.get('anime_title', '未知番剧')
        message_parts = await create_character_detail_message(character_info, anime_title)
        await bot.send(event, message_parts)

        session.timestamp = time.time()
        return


async def handle_bgmlist_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理BGM list会话"""
    if await _handle_pagination(bot, event, user_input, session):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        title_cn, anime_info = session.search_results[selection - 1]
        await display_anime_info(bot, event, title_cn, anime_info, session.search_type)
        session.timestamp = time.time()
        return


async def handle_score_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理评分会话"""
    if await _handle_pagination(bot, event, user_input, session):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await anime_session_handler.send(f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的番剧信息
        title_cn, anime_info = session.search_results[selection - 1]

        # 添加评分
        anime_id = anime_info.get('id')
        success = user_score_manager.add_user_score(anime_id, session.score_username, session.score_value)
        if success:
            await anime_session_handler.send(f"已为『{title_cn}』添加评分：{session.score_username}{session.score_value}")
        else:
            await anime_session_handler.send("评分失败，请稍后重试")

        # 清除会话
        clear_user_session(event)
        return


async def handle_score_show_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理评分展示会话"""
    if await _handle_pagination(bot, event, user_input, session):
        return

    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")  # 修复
            return

        # 获取选择的番剧信息
        title_cn, anime_info = session.search_results[selection - 1]

        # 展示用户评分
        await display_user_scores(bot, event, title_cn, anime_info)

        # 不清除会话，用户可以继续浏览其他结果（与handle_search_session保持一致）
        session.timestamp = time.time()
        return


async def handle_score_delete_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理评分删除会话"""
    if user_input == '0':
        clear_user_session(event)
        await bot.send(event, "已退出评分删除模式")
        return

    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_search_results_page(s, f"{s.delete_username}的评分")
    ):
        return

    # 删除处理
    if user_input.isdigit():
        selection = int(user_input)
        total_scores = len(session.delete_scores)

        if selection < 1 or selection > total_scores:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_scores} 之间的数字，或输入 '0' 退出")
            return

        # 获取要删除的评分
        anime_id, score, display_title = session.delete_scores[selection - 1]
        username = session.delete_username

        # 删除评分
        success = user_score_manager.delete_user_score(anime_id, username)
        if success:
            # 从会话中移除已删除的评分
            session.delete_scores.pop(selection - 1)

            # 更新search_results以保持同步
            if selection - 1 < len(session.search_results):
                session.search_results.pop(selection - 1)

            await bot.send(event, f"已删除 {username} 对『{display_title}』的评分：{score}")

            # 如果还有评分，刷新列表；否则结束会话
            if session.delete_scores:
                # 重新计算分页
                total_results = len(session.search_results)
                session.total_pages = math.ceil(total_results / session.page_size)

                # 如果当前页没有内容了，回到上一页
                if session.current_page >= session.total_pages:
                    session.current_page = max(0, session.total_pages - 1)

                selection_msg = format_search_results_page(session, f"{username}的评分")
                await bot.send(event, selection_msg)
            else:
                clear_user_session(event)
                await bot.send(event, f"{username} 的所有评分已删除完毕")
        else:
            await bot.send(event, "删除失败，请稍后重试")

        return


async def handle_character_rate_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理角色评级会话"""
    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_character_search_results_page(s, f"包含 '{s.search_query}'")
    ):
        return

    # 角色选择处理
    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的角色信息
        character_name, character_info = session.search_results[selection - 1]
        anime_title = character_info.get('anime_title', '未知番剧')
        anime_id = character_info.get('anime_id')
        username = session.character_username
        score = session.character_score

        # 添加角色评级
        success = character_score_manager.add_character_score(character_name, anime_id, anime_title, username, score)
        if success:
            level_name = character_score_manager.get_level_display_name(score)
            await bot.send(event, f"已为『{anime_title}』中的『{character_name}』添加评级：{level_name}")
        else:
            await bot.send(event, "评级失败，请稍后重试")

        # 清除会话
        clear_user_session(event)
        return


async def handle_character_delete_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理角色评级删除会话"""
    # 退出处理 - 优先检查
    if user_input == '0':
        clear_user_session(event)
        await bot.send(event, "已退出角色评级删除模式")
        return

    if await _handle_pagination(bot, event, user_input, session, async_formatter=send_character_delete_list):
        return

    # 删除处理
    if user_input.isdigit():
        selection = int(user_input)
        total_scores = len(session.delete_scores)

        if selection < 1 or selection > total_scores:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_scores} 之间的数字，或输入 '0' 退出")
            return

        # 获取要删除的评级
        character_name, anime_id, score = session.delete_scores[selection - 1]
        username = session.delete_username
        anime_title = character_score_manager.resolve_anime_title(anime_id)

        logger.info(f"删除角色评分: {character_name}（条目 {anime_id}）- 用户: {username}")

        # 删除评级
        success = character_score_manager.delete_character_score(character_name, anime_id, username)
        if success:
            # 从会话中移除已删除的评级
            session.delete_scores.pop(selection - 1)

            level_name = character_score_manager.get_level_display_name(score)
            await bot.send(event, f"已删除 {username} 对『{anime_title}』中的『{character_name}』的评级：{level_name}")

            # 如果还有评级，刷新列表；否则结束会话
            if session.delete_scores:
                await send_character_delete_list(bot, event, session)
            else:
                clear_user_session(event)
                await bot.send(event, f"{username} 的所有角色评级已删除完毕")
        else:
            await bot.send(event, "删除失败，请稍后重试")

        return


async def handle_view_season_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理季度查看会话"""
    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_season_results_page(s, f"{s.view_year}年{s.view_month_name}番剧")
    ):
        return

    # 番剧选择处理
    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的番剧信息
        title, info = session.search_results[selection - 1]
        message_parts = await bgm_manager.create_anime_message(title, info)
        await bot.send(event, message_parts)

        # 不清除会话，用户可以继续浏览其他结果
        session.timestamp = time.time()
        return


async def handle_view_week_session(bot: Bot, event: Event, user_input: str, session: UserSession):
    """处理星期查看会话"""
    if await _handle_pagination(
        bot, event, user_input, session,
        page_formatter=lambda s: format_week_results_page(s)
    ):
        return

    # 番剧选择处理
    if user_input.isdigit():
        selection = int(user_input)
        total_results = len(session.search_results)

        if selection < 1 or selection > total_results:
            await bot.send(event, f"无效的选择编号，请输入 1~{total_results} 之间的数字")
            return

        # 获取选择的番剧信息
        title, info = session.search_results[selection - 1]
        message_parts = await bgm_manager.create_anime_message(title, info)
        await bot.send(event, message_parts)

        # 不清除会话，用户可以继续浏览其他结果
        session.timestamp = time.time()
        return



