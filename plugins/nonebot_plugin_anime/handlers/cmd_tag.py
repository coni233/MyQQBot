import time
import os
from typing import Dict
from ..core import bgm_manager, tag_manager
from ..core.anime_formatting import format_search_results_page
from ..core.anime_session import get_user_session, set_session, cleanup_old_sessions
from ..core.anime_permissons import is_private_or_allowed_group
from nonebot import on_command, logger
from nonebot.rule import Rule, to_me
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg


# ==================== 标签管理命令处理器 ====================
anime_bgmtag = on_command("anime bgmtag", aliases={"bgm标签"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_bgmtag_view = on_command("anime bgmtag view", aliases={"标签查看"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_bgmtag_add = on_command("anime bgmtag add", aliases={"标签添加"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_bgmtag_del = on_command("anime bgmtag del", aliases={"标签删除"}, priority=5, rule=Rule(is_private_or_allowed_group))


# ==================== BGM标签命令处理 ====================
@anime_bgmtag_view.handle()
async def handle_bgmtag_view(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理标签查看命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmtag_view.finish("请输入要查看标签的番剧名")

    # 搜索番剧
    results = bgm_manager.search_anime_by_keyword(args_text)
    if not results:
        await anime_bgmtag_view.finish(f"未找到包含 '{args_text}' 的番剧")

    # 如果只有一个结果，直接显示
    if len(results) == 1:
        title_cn, anime_info = results[0]
        await display_anime_tags(bot, event, title_cn, anime_info)

        # 设置当前操作的番剧
        session = get_user_session(event)
        session.current_anime = anime_info
        session.current_anime_title = title_cn
    else:
        # 多个结果，设置标签管理会话
        set_session(
            event,
            'bgmtag',
            search_results=results,
            search_type='view',
            search_query=args_text,
            current_page=0
        )

        # 显示搜索结果列表
        selection_msg = format_search_results_page(get_user_session(event), f"包含 '{args_text}'")
        await anime_bgmtag_view.send(selection_msg)


async def display_anime_tags(bot: Bot, event: Event, title_cn: str, anime_info: Dict):
    """显示番剧标签信息"""
    tag_manager.load_all_data()

    anime_id = anime_info.get('id') if isinstance(anime_info, dict) else None
    latest_anime_info = tag_manager.all_data.get(str(anime_id)) if anime_id is not None else None
    if latest_anime_info is None:
        latest_anime_info = anime_info

    # 获取标签
    tags = tag_manager.get_anime_tags(latest_anime_info)
    tags_display = tag_manager.format_tags_display(tags)

    # 更新会话中的番剧信息
    session = get_user_session(event)
    session.current_anime = latest_anime_info
    session.current_anime_title = title_cn
    session.timestamp = time.time()

    # 构建消息
    message_parts = []

    # 添加封面图片
    cover_url = latest_anime_info.get('cover_url')
    if cover_url:
        anime_id = latest_anime_info.get('id', 'unknown')
        # 使用统一的图片管理器下载封面
        cover_path = await bgm_manager.download_cover_image(cover_url, anime_id)
        if cover_path:
            try:
                image_msg = MessageSegment.image(f"file:///{os.path.abspath(cover_path)}")
                message_parts.append(image_msg)
            except Exception as e:
                logger.warning("添加封面失败")

    # 添加标签信息
    text_msg = MessageSegment.text(f"番名：{title_cn}\n标签：{tags_display}")
    message_parts.append(text_msg)

    # 添加操作提示
    if tags:
        operation_msg = MessageSegment.text(f"\n\n可使用以下命令修改标签：\n"
                                            f"标签添加 <标签名> \n"
                                            f"标签删除 <标签名> ")
        message_parts.append(operation_msg)
    else:
        operation_msg = MessageSegment.text(f"\n\n可使用以下命令添加标签：\n"
                                            f"标签添加 <标签名> ")
        message_parts.append(operation_msg)

    await bot.send(event, message_parts)


@anime_bgmtag_add.handle()
async def handle_bgmtag_add(event: Event, args: Message = CommandArg()):
    """处理标签添加命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmtag_add.finish("请输入要添加的标签名")

    # 获取当前操作的番剧
    session = get_user_session(event)
    if not session.current_anime or not session.current_anime_title:
        await anime_bgmtag_add.finish("请先使用 '标签查看 <番剧名>' 选择要操作的番剧")

    # 添加标签
    success = tag_manager.add_tag(session.current_anime, args_text, session.current_anime_title)
    if success:
        await anime_bgmtag_add.send(f"已为『{session.current_anime_title}』添加标签：{args_text}")

        # 重新显示更新后的标签
        tags = tag_manager.get_anime_tags(session.current_anime)
        tags_display = tag_manager.format_tags_display(tags)
        await anime_bgmtag_add.send(f"当前标签：{tags_display}")


        session.timestamp = time.time()
    else:
        await anime_bgmtag_add.finish(f"添加标签失败，可能标签已存在")


@anime_bgmtag_del.handle()
async def handle_bgmtag_del(event: Event, args: Message = CommandArg()):
    """处理标签删除命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmtag_del.finish("请输入要删除的标签名")

    # 获取当前操作的番剧
    session = get_user_session(event)
    if not session.current_anime or not session.current_anime_title:
        await anime_bgmtag_del.finish("请先使用 '标签查看 <番剧名>' 选择要操作的番剧")

    # 检查标签是否存在
    tags = tag_manager.get_anime_tags(session.current_anime)
    if args_text not in tags:
        await anime_bgmtag_del.finish(f"标签 '{args_text}' 不存在")

    # 删除标签
    success = tag_manager.remove_tag(session.current_anime, args_text, session.current_anime_title)
    if success:
        await anime_bgmtag_del.send(f"已为『{session.current_anime_title}』删除标签：{args_text}")

        # 重新显示更新后的标签
        tags = tag_manager.get_anime_tags(session.current_anime)
        tags_display = tag_manager.format_tags_display(tags)
        await anime_bgmtag_del.send(f"当前标签：{tags_display}")

        # 更新时间戳
        session.timestamp = time.time()
    else:
        await anime_bgmtag_del.finish(f"删除标签失败")

