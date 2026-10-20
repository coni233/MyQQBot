import math
import re
import os
from ..core import bgm_manager, character_score_manager, character_image_generator
from ..core.anime_formatting import format_character_search_results_page
from ..core.anime_session import get_user_session, set_session, cleanup_old_sessions, UserSession
from ..core.anime_permissons import is_private_or_allowed_group
from nonebot import on_command, logger
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.typing import T_State


# ==================== 角色评级命令处理器 ====================
anime_character_rate = on_command("anime character rate", aliases={"角色评级"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_character_view = on_command("anime character view", aliases={"角色评级查看"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_character_delete = on_command("anime character delete", aliases={"角色评级删除"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_character_pic = on_command("anime character pic", aliases={"角色评级图"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== 角色评级命令处理 ====================
@anime_character_rate.handle()
async def handle_anime_character_rate(event: Event, args: Message = CommandArg()):
    """处理角色评级命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()
    score = 0

    if not args_text:
        await anime_character_rate.finish(
            "使用方法: \n"
            "anime character <角色名> <特征名><等级>\n"
            "等级: 1-5")

    # 解析参数：角色名 + 特征名+等级
    parts = args_text.rsplit(' ', 1)
    if len(parts) < 2:
        await anime_character_rate.finish("参数格式错误，请使用: anime character <角色名> <特征名><等级>")

    character_name = parts[0]
    user_score_text = parts[1]

    # 解析特征名和等级
    match = re.match(r'^([^\d]+)([1-5])$', user_score_text)
    if not match:
        await anime_character_rate.finish("等级格式错误，请使用: 特征名等级 (如: 缪5)\n等级必须是1-5的数字")

    username = match.group(1)
    try:
        score = int(match.group(2))
        if score < 1 or score > 5:
            await anime_character_rate.finish("等级必须在1-5之间")
    except ValueError:
        await anime_character_rate.finish("等级必须是数字")

    # 搜索角色
    results = bgm_manager.search_characters_by_name(character_name)
    if not results:
        await anime_character_rate.finish(f"未找到包含 '{character_name}' 的角色")

    if len(results) == 1:
        char_name, character_info = results[0]
        anime_title = character_info.get('anime_title', '未知番剧')
        anime_id = character_info.get('anime_id')
        image_url = character_info.get('image_url')

        success = character_score_manager.add_character_score(char_name, anime_id, anime_title, username, score, image_url)
        if success:
            level_name = character_score_manager.get_level_display_name(score)
            await anime_character_rate.finish(f"已为『{anime_title}』中的『{char_name}』添加评级：{level_name}")
        else:
            await anime_character_rate.finish("评级失败，请稍后重试")
    else:
        set_session(
            event,
            'character_rate',
            search_results=results,
            search_type='character_rate',
            search_query=character_name,
            character_username=username,
            character_score=score
        )

        # 显示搜索结果第一页
        selection_msg = format_character_search_results_page(get_user_session(event), f"包含 '{character_name}'")
        await anime_character_rate.send(selection_msg)


@anime_character_view.handle()
async def handle_anime_character_view(args: Message = CommandArg()):
    """处理角色评级查看命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_character_view.finish(
            "使用方法: \n"
            "anime character view <特征名>")

    username = args_text

    # 显示用户角色评级
    display_message = character_score_manager.format_user_character_scores_display(username)
    await anime_character_view.finish(display_message)


@anime_character_delete.handle()
async def handle_anime_character_delete(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理角色评级删除命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_character_delete.finish(
            "使用方法: \n"
            "anime character delete <特征名>")

    username = args_text

    # 获取该用户的所有角色评级（角色名, 条目id, 等级）
    user_scores = character_score_manager.get_all_character_scores_by_user(username)

    if not user_scores:
        await anime_character_delete.finish(f"用户 '{username}' 暂无角色评级记录")

    # 设置角色评级删除会话 - delete_scores 为 (角色名, 条目id, 等级) 三元组
    set_session(
        event,
        'character_delete',
        delete_scores=list(user_scores),
        delete_username=username,
        search_type='character_delete',
        search_query=username,
        current_page=0
    )

    # 显示用户角色评级列表
    await send_character_delete_list(bot, event, get_user_session(event))


@anime_character_pic.handle()
async def handle_character_pic(args: Message = CommandArg()):
    """处理角色评级图片命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_character_pic.finish(
            "使用方法: \n"
            "角色评级图 <特征名>")

    feature_name = args_text

    # 生成图片
    await anime_character_pic.send(f"正在为 {feature_name} 生成角色评级图片，请稍候...")

    image_path = await character_image_generator.generate_character_score_image(feature_name)

    if not image_path:
        await anime_character_pic.finish(f"生成 {feature_name} 的角色评级图片失败，可能没有评级数据")

    # 发送图片
    try:
        image_segment = MessageSegment.image(f"file:///{image_path}")
        await anime_character_pic.send(image_segment)

        # 清理临时文件
        if os.path.exists(image_path):
            os.unlink(image_path)

    except Exception:
        logger.warning("发送角色评级图片失败")
        await anime_character_pic.finish("发送图片失败，请稍后重试")


async def send_character_delete_list(bot: Bot, event: Event, session: UserSession):
    """发送角色评级删除列表"""
    user_scores = session.delete_scores
    username = session.delete_username

    # 分页处理
    total_scores = len(user_scores)
    session.total_pages = math.ceil(total_scores / session.page_size) if total_scores else 1

    # 如果当前页超出范围，回到最后一页
    if session.current_page >= session.total_pages:
        session.current_page = max(0, session.total_pages - 1)

    start_idx = session.current_page * session.page_size
    end_idx = min((session.current_page + 1) * session.page_size, total_scores)
    current_scores = user_scores[start_idx:end_idx]

    # 构建消息
    message_parts = [f"{username}已评级的角色有：\n"]

    for i, (character_name, anime_id, score) in enumerate(current_scores, 1):
        global_index = start_idx + i
        level_name = character_score_manager.get_level_display_name(score)
        anime_title = character_score_manager.resolve_anime_title(anime_id)
        message_parts.append(f"{global_index}. {character_name} - {anime_title} ({level_name})")

    # 添加分页信息
    if session.total_pages > 1:
        message_parts.append(f"\n第{session.current_page + 1}/{session.total_pages}页")

        # 添加翻页提示
        page_commands = []
        if session.current_page > 0:
            page_commands.append("输入 'p' 或 '上一页' 查看上一页")
        if session.current_page < session.total_pages - 1:
            page_commands.append("输入 'n' 或 '下一页' 查看下一页")

        if page_commands:
            message_parts.append("\n" + "\n".join(page_commands))

    message_parts.append(f"\n请回复编号删除对应评级 (输入数字 1~{total_scores})")
    message_parts.append("输入 '0' 退出删除模式")

    await bot.send(event, "\n".join(message_parts))