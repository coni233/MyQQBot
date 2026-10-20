from ..core import bgm_manager, bgm_api
from ..core.anime_session import set_session, cleanup_old_sessions, get_user_session
from ..core.anime_formatting import format_search_results_page
from ..core.anime_permissons import is_private_or_allowed_group
from ..core.anime_time import parse_single_date, validate_year
from ..config import BANGUMI_API_TOKEN
from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.rule import Rule, to_me
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER


# ==================== BGM 获取命令处理器 ====================
anime_bgmget = on_command("anime bgmget", aliases={"bgm获取", "番剧获取"}, priority=5, rule=Rule(is_private_or_allowed_group))
anime_getmonth = on_command("anime getmonth", aliases={"季度更新"}, priority=5, permission=SUPERUSER)
anime_bgmmonth = on_command("anime bgmmonth", aliases={"月份获取"}, priority=5, permission=SUPERUSER)


# ==================== 获取命令处理 ====================
@anime_bgmget.handle()
async def handle_anime_bgmget(bot: Bot, event: Event, args: Message = CommandArg()):
    """处理 anime bgmget 命令"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmget.finish("使用方法:\n"
                                  "anime bgmget <番剧ID> （可添加新番剧）\n"
                                  "anime bgmget <番剧名> （仅更新现有番剧）")

    # 检查是否是数字（ID）
    if args_text.isdigit():
        # 通过ID获取 - 允许添加新番剧
        await anime_bgmget.send(f"正在通过ID {args_text} 获取番剧数据...")

        anime_data = await bgm_api.fetch_anime_by_id(args_text)
        if anime_data:
            logger.info(f"成功获取番剧数据: {anime_data.get('title_cn') or anime_data.get('title_jp')}")

            # 数据键为条目 id，先判断该 id 是否已存在
            existed = str(args_text) in bgm_manager.load_all_data()

            success = bgm_manager.update_anime_data(anime_data, args_text, allow_add_new=True)
            if success:
                # 显示更新/添加后的数据
                title = anime_data.get('title_cn') or anime_data.get('title_jp', '未知')
                message_parts = await bgm_manager.create_anime_message(title, anime_data)
                await bot.send(event, message_parts)

                # 数据键为条目 id：新增前若已存在同 id 记录则为更新
                all_data = bgm_manager.load_all_data()
                if str(args_text) in all_data:
                    stored_title = (anime_data.get('title_cn')
                                    or (anime_data.get('basic_info') or {}).get('chinese_title')
                                    or anime_data.get('title_jp') or '未知')
                    if existed:
                        await anime_bgmget.send(f"已成功更新番剧数据")
                    else:
                        await anime_bgmget.send(f"已成功添加新番剧: {stored_title}")
                else:
                    await anime_bgmget.finish("操作失败，可能是数据格式问题")
            else:
                await anime_bgmget.finish("操作失败，可能是数据格式问题")
        else:
            await anime_bgmget.finish("获取番剧数据失败，请检查ID是否正确")
    else:
        # 通过名称搜索 - 仅更新现有番剧
        results = bgm_manager.search_anime_by_keyword(args_text)
        if not results:
            await anime_bgmget.finish(f"未找到包含 '{args_text}' 的番剧")

        # 如果只有一个结果，直接更新
        if len(results) == 1:
            title_cn, anime_info = results[0]
            anime_id = anime_info.get('id')

            if anime_id:
                await anime_bgmget.send(f"正在获取番剧 '{title_cn}' 的最新数据...")

                anime_data = await bgm_api.fetch_anime_by_id(anime_id)
                if anime_data:
                    success = bgm_manager.update_anime_data(anime_data, anime_id, allow_add_new=False)
                    if success:
                        message_parts = await bgm_manager.create_anime_message(title_cn, anime_data)
                        await bot.send(event, message_parts)
                        await anime_bgmget.send(f"已成功更新番剧数据")
                    else:
                        await anime_bgmget.finish("更新数据失败")
                else:
                    await anime_bgmget.finish("获取番剧数据失败")
            else:
                await anime_bgmget.finish("该番剧没有ID信息，无法更新")
        else:
            # 多个结果，设置选择会话
            set_session(
                event,
                'bgmget',
                search_results=results,
                search_type='bgmget',
                search_query=args_text
            )
            page_msg = format_search_results_page(get_user_session(event), f"包含 '{args_text}'")
            await anime_bgmget.send(page_msg)


@anime_getmonth.handle()
async def handle_anime_getmonth(args: Message = CommandArg()):
    """处理 anime getmonth 命令 - 批量获取并更新季度番剧"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_getmonth.finish("使用方法:\n"
                                    "anime getmonth <年月>\n"
                                    "例如: anime getmonth 2025年10月")

    year, month = parse_single_date(args_text)
    if not year or not validate_year(year) or not (1 <= month <= 12):
        await anime_getmonth.finish(
            "日期解析错误，请使用正确的年月格式，例如: 2025年10月 或 2025-10"
        )

    await anime_getmonth.send(f"正在从 Bangumi API 获取 {year}年{month}月 季度番剧...")

    concurrency = 5 if BANGUMI_API_TOKEN else 1
    new_anime = await bgm_api.fetch_anime_by_month(year, month, "tv", max_concurrency=concurrency)

    if not new_anime:
        await anime_getmonth.finish(f"未在 {year}年{month}月 季度找到任何番剧")

    # 合并并保存数据
    existing_data = bgm_manager.load_all_data()
    added = 0
    updated = 0

    for anime_id, data in new_anime.items():
        if anime_id in existing_data:
            updated += 1
        else:
            added += 1
        existing_data[anime_id] = data

    if bgm_manager.save_all_data(existing_data):
        await anime_getmonth.send(
            f"获取完成！共 {len(new_anime)} 部番剧\n"
            f"新增: {added} 部, 更新: {updated} 部"
        )
    else:
        await anime_getmonth.send("获取数据成功，但保存失败")


@anime_bgmmonth.handle()
async def handle_anime_bgmmonth(args: Message = CommandArg()):
    """处理 anime bgmmonth 命令 - 获取指定月份的新番剧数据"""
    cleanup_old_sessions()

    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_bgmmonth.finish("使用方法:\n"
                                    "anime bgmmonth <年月> <类型>\n"
                                    "例如: anime bgmmonth 2026年1月 tv\n"
                                    "例如: anime bgmmonth 2026年1月 movie")

    parts = args_text.split()
    if len(parts) < 2:
        await anime_bgmmonth.finish("参数不足，请提供年月和类型")

    year_month = parts[0]
    media_type = parts[1].lower()

    if media_type not in ['tv', 'movie']:
        await anime_bgmmonth.finish("类型必须是 'tv' 或 'movie'")

    year, month = parse_single_date(year_month)
    if not year or not validate_year(year) or not (1 <= month <= 12):
        await anime_bgmmonth.finish("年月格式不正确，请使用例如: 2026年1月")

    await anime_bgmmonth.send(f"开始获取 {year}年{month}月季度 的 {media_type.upper()} 番剧信息...")

    existing_data = bgm_manager.load_all_data()

    concurrency = 5 if BANGUMI_API_TOKEN else 1
    new_anime = await bgm_api.fetch_anime_by_month(year, month, media_type, max_concurrency=concurrency)

    if not new_anime:
        await anime_bgmmonth.finish("获取数据失败，未找到任何番剧")

    added = 0
    updated = 0
    for anime_id, data in new_anime.items():
        if anime_id in existing_data:
            updated += 1
        else:
            added += 1
        existing_data[anime_id] = data

    if bgm_manager.save_all_data(existing_data):
        await anime_bgmmonth.finish(
            f"成功获取并更新了 {len(new_anime)} 部番剧\n"
            f"新增: {added} 部, 更新: {updated} 部"
        )
    else:
        await anime_bgmmonth.finish("获取数据成功，但保存失败")







