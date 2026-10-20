import re
import os
from typing import Dict
from ..core import user_score_manager, bgm_manager, anime_score_image_generator
from ..core.anime_formatting import format_search_results_page
from ..core.anime_session import get_user_session, set_session, cleanup_old_sessions
from ..core.anime_permissons import is_private_or_allowed_group
from ..core.anime_filter import parse_score_value
from nonebot import on_command, logger
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg

# ==================== 评分命令处理器 ====================
anime_score = on_command("anime score", aliases={"番剧评分"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_score_search = on_command("anime score search", aliases={"评分搜索"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_score_show = on_command("anime score show", aliases={"评分展示"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_score_delete = on_command("anime score delete", aliases={"评分删除"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_score_pic = on_command("anime score pic", aliases={"评分图"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== 评分命令处理 ====================
@anime_score.handle()
async def handle_anime_score(event: Event, args: Message = CommandArg()):
    """处理用户评分命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()
    score = 0

    if not args_text:
        await anime_score.finish("使用方法: \n"
                                 "anime score <番剧名> <特征名><分数>\n"
                                 "例如: anime score 奇蛋物语 缪2.0")

    parts = args_text.rsplit(' ', 1)
    if len(parts) < 2:
        await anime_score.finish("参数格式错误，请使用: anime score <番剧名> <特征名><分数>")

    anime_name = parts[0]
    user_score_text = parts[1]

    match = re.match(r'^([^\d]+)(\d+(?:\.\d)?)$', user_score_text)
    if not match:
        await anime_score.finish("分数格式错误！请使用 0.0-10.0 的一位小数")

    username = match.group(1)
    try:
        _, score, _ = parse_score_value(match.group(2))
    except ValueError as e:
        await anime_score.finish(str(e))

    # 搜索番剧
    results = bgm_manager.search_anime_by_keyword(anime_name)
    if not results:
        await anime_score.finish(f"未找到包含 '{anime_name}' 的番剧")

    # 如果只有一个结果，直接评分
    if len(results) == 1:
        title_cn, anime_info = results[0]
        success = user_score_manager.add_user_score(anime_info.get('id'), username, score)
        if success:
            await anime_score.finish(f"已为『{title_cn}』添加评分：{username}{score}")
        else:
            await anime_score.finish("评分失败，请稍后重试")
    else:
        # 多个结果，设置评分会话
        set_session(
            event,
            'score',
            search_results=results,
            search_type='score',
            search_query=anime_name,
            score_username=username,
            score_value=score
        )

        # 显示搜索结果列表
        selection_msg = format_search_results_page(get_user_session(event), f"包含 '{anime_name}'")
        await anime_score.send(selection_msg)


@anime_score_search.handle()
async def handle_anime_score_search(args: Message = CommandArg()):
    """处理评分搜索命令"""
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_score_search.finish(
            "使用方法:\n"
            "anime score search <特征名> <分数> \n"
            "例如: anime score search 缪 9.0"
        )

    # 解析参数
    parts = args_text.split(' ', 1)
    if len(parts) < 2:
        await anime_score_search.finish("参数格式错误，请使用: anime score search <特征名> <分数>")

    username = parts[0]
    score_param = parts[1]

    try:
        _, min_score, max_score = parse_score_value(score_param)
    except ValueError as e:
        await anime_score_search.finish(str(e))

    if min_score == max_score:
        # 精确搜索
        results = user_score_manager.search_scores_by_user_and_score(username, min_score)
        if not results:
            await anime_score_search.finish(f"未找到{username}{min_score}的番剧")

        result_list = []
        for i, anime_id in enumerate(results, 1):
            result_list.append(f"{i}. {bgm_manager.get_display_name_by_id(anime_id)}")
        result_msg = f"{username}{min_score}的番剧有：\n" + "\n".join(result_list)
        await anime_score_search.send(result_msg)
    else:
        # 范围搜索
        results = user_score_manager.search_scores_by_user_and_score_range(username, min_score, max_score)
        if not results:
            await anime_score_search.finish(f"未找到{username}在{min_score}-{max_score}分数范围内的番剧")

        # 显示结果 - 按分数从高到低分组显示
        result_messages = []
        for score, anime_list in results.items():
            score_group = []
            for i, anime_id in enumerate(anime_list, 1):
                score_group.append(f"{i}. {bgm_manager.get_display_name_by_id(anime_id)}")

            result_messages.append(f"{username}{score}的番剧有：\n" + "\n".join(score_group))

        await anime_score_search.send("\n\n".join(result_messages))


@anime_score_show.handle()
async def handle_anime_score_show(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理评分展示命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_score_show.finish("使用方法: \n"
                                      "anime score show <番剧名>\n"
                                      "例如: anime score show 奇蛋物语")

    # 搜索番剧
    results = bgm_manager.search_anime_by_keyword(args_text)
    if not results:
        await anime_score_show.finish(f"未找到包含 '{args_text}' 的番剧")

    if len(results) == 1:
        title_cn, anime_info = results[0]
        await display_user_scores(bot, event, title_cn, anime_info)
    else:
        # 多个结果，设置评分展示会话
        set_session(
            event,
            'score_show',
            search_results=results,
            search_type='score_show',
            search_query=args_text,
            current_page=0
        )

        # 显示搜索结果第一页
        selection_msg = format_search_results_page(get_user_session(event), f"包含 '{args_text}'")
        await anime_score_show.send(selection_msg)


async def display_user_scores(bot: Bot, event: Event, title_cn: str, anime_info: Dict):
    """展示番剧的用户评分"""
    anime_id = anime_info.get('id')
    sorted_scores = user_score_manager.get_sorted_user_scores(anime_id) if anime_id is not None else []

    # 构建消息
    message_parts = []

    # 添加封面图片
    cover_url = anime_info.get('cover_url')
    if cover_url:
        anime_id = anime_info.get('id', 'unknown')
        cover_path = await bgm_manager.download_cover_image(cover_url, anime_id)
        if cover_path:
            try:
                image_msg = MessageSegment.image(f"file:///{os.path.abspath(cover_path)}")
                message_parts.append(image_msg)
            except Exception as e:
                logger.warning("添加封面失败")

    # 添加番剧名称
    title_msg = MessageSegment.text(f"番名：{title_cn}")
    message_parts.append(title_msg)

    # 添加用户评分
    if sorted_scores:
        # 构建评分列表
        score_lines = []
        for username, score in sorted_scores:
            score_lines.append(f"{username} {score}")

        scores_text = "\n".join(score_lines)
        scores_msg = MessageSegment.text(f"\n{scores_text}")
        message_parts.append(scores_msg)

    else:
        no_scores_msg = MessageSegment.text("\n暂无用户评分")
        message_parts.append(no_scores_msg)

    await bot.send(event, message_parts)


@anime_score_delete.handle()
async def handle_anime_score_delete(event: Event, args: Message = CommandArg()):
    """处理评分删除命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_score_delete.finish("使用方法: \n"
                                        "anime score delete <特征名>\n")

    username = args_text

    # 获取该用户的所有评分
    user_scores = user_score_manager.get_all_scores_by_user(username)

    if not user_scores:
        await anime_score_delete.finish(f"用户 '{username}' 暂无评分记录")

    # 构造删除会话
    delete_scores = []
    search_results = []
    for anime_id, score in user_scores:
        display_title = bgm_manager.get_display_name_by_id(anime_id)
        delete_scores.append((anime_id, score, display_title))
        search_results.append((display_title, {"score": score, "anime_id": anime_id}))

    # 设置评分删除会话
    set_session(
        event,
        'score_delete',
        delete_scores=delete_scores,
        delete_username=username,
        search_results=search_results,
        search_type='score_delete',
        search_query=username,
        current_page=0
    )

    # 使用统一的格式化函数显示列表
    session = get_user_session(event)
    selection_msg = format_search_results_page(session, f"{username}的评分")
    await anime_score_delete.send(selection_msg)


@anime_score_pic.handle()
async def handle_score_pic(args: Message = CommandArg()):
    """处理评分图片命令"""
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_score_pic.finish(
            "使用方法: \n"
            "评分图 <特征名> <最低分>-<最高分>")

    # 解析参数
    parts = args_text.split(' ', 1)
    if len(parts) < 1:
        await anime_score_pic.finish("参数格式错误，请提供特征名")

    username = parts[0]
    score_range = parts[1] if len(parts) > 1 else None

    if score_range:
        try:
            _, min_score, max_score = parse_score_value(score_range)
            score_range = f"{min_score}-{max_score}"
        except ValueError as e:
            await anime_score_pic.finish(str(e))

    # 生成图片
    await anime_score_pic.send(f"正在为 {username} 生成评分图，请稍候...")

    image_path = await anime_score_image_generator.generate_anime_score_image(username, score_range)

    if not image_path:
        await anime_score_pic.finish(f"生成 {username} 的评分图失败，可能没有评分数据")

    # 发送图片
    try:
        image_segment = MessageSegment.image(f"file:///{image_path}")
        await anime_score_pic.send(image_segment)

        # 清理临时文件
        if os.path.exists(image_path):
            os.unlink(image_path)

    except Exception:
        logger.warning("发送图片失败")
        await anime_score_pic.finish("发送图片失败，请稍后重试")