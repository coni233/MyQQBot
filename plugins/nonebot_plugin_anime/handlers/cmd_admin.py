import json
import shutil
from ..core import bgm_manager
from ..core.anime_permissons import group_permission_manager, is_private_or_allowed_group
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule


# ==================== 群组管理命令处理器 ====================
anime_add_group = on_command("anime add_group", aliases={"番剧群组添加"}, priority=5, permission=SUPERUSER)
anime_remove_group = on_command("anime remove_group", aliases={"番剧群组移除"}, priority=5, permission=SUPERUSER)
anime_list_groups = on_command("anime list_groups", aliases={"番剧群组列表"}, priority=5, permission=SUPERUSER)
anime_help = on_command("anime help", priority=5, rule=Rule(is_private_or_allowed_group))
anime_debug = on_command("anime debug", priority=5, permission=SUPERUSER)
anime_clear_cache = on_command("anime clear_cache", aliases={"清理番剧缓存"}, priority=5, permission=SUPERUSER)

# ==================== 群组管理命令处理 ====================
@anime_add_group.handle()
async def handle_anime_add_group(args: Message = CommandArg()):
    """添加群组到白名单"""
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_add_group.finish("请输入要添加的群号")

    if not args_text.isdigit():
        await anime_add_group.finish("群号必须是数字")

    success = group_permission_manager.add_group(args_text)
    if success:
        await anime_add_group.finish(f"已成功添加群组 {args_text} 到白名单")
    else:
        await anime_add_group.finish("添加群组失败")


@anime_remove_group.handle()
async def handle_anime_remove_group(args: Message = CommandArg()):
    """从白名单移除群组"""
    args_text = args.extract_plain_text().strip()

    if not args_text:
        await anime_remove_group.finish("请输入要移除的群号")

    if not args_text.isdigit():
        await anime_remove_group.finish("群号必须是数字")

    success = group_permission_manager.remove_group(args_text)
    if success:
        await anime_remove_group.finish(f"已成功从白名单移除群组 {args_text}")
    else:
        await anime_remove_group.finish("移除群组失败")


@anime_list_groups.handle()
async def handle_anime_list_groups():
    """显示所有允许的群组"""
    allowed_groups = group_permission_manager.get_allowed_groups()

    if not allowed_groups:
        await anime_list_groups.finish("当前没有允许的群组")

    groups_list = "\n".join([f"- {group_id}" for group_id in allowed_groups])
    await anime_list_groups.finish(f"当前允许的群组:\n{groups_list}")


@anime_help.handle()
async def handle_anime_help():
    await anime_help.finish(
        MessageSegment.text(
            "—— 番剧助手 指令列表 ——\n"
            "\n"
            "  番剧搜索 <番剧名> [条件] — 搜索番剧\n"
            "  声优搜索 <CV名>        — 搜索角色\n"
            "  角色搜索 <角色名>       — 角色名搜索\n"
            "  番剧详情 <番剧名> cv/staff — 番剧详细\n"
            "\n"
            "  番剧评分 <番剧名> <用户><0-10>  — 添加番剧评分\n"
            "  评分搜索 <用户> <分数范围>      — 搜索用户评分\n"
            "  评分展示 <番剧名>              — 展示番剧的用户评分\n"
            "  评分删除 <用户>                — 删除用户评分\n"
            "  评分图 <用户> [分数范围]        — 生成评分图片\n"
            "\n"
            "  角色评级 <角色名> <用户><1-5>  — 对角色进行评级\n"
            "  角色评级查看 <用户>            — 查看角色评级\n"
            "  角色评级删除 <用户>            — 删除角色评级\n"
            "  角色评级图 <用户>              — 生成角色评级图片\n"
            "\n"
            "  随机番剧 [条件]     — 随机番剧\n"
            "  番剧查看 <年月>     — 查看番剧\n"
            "  星期查看 <年月>     — 按星期查看\n"
            "  今天有什么番        — 查看今日番剧\n"
            "\n"
            "  标签查看 <番剧名>      — 查看番剧标签\n"
            "  标签添加 <番剧名> <标签>   — 添加标签\n"
            "  标签删除 <番剧名> <标签>   — 删除标签\n"
            "\n"
            "  番剧获取 <ID>         — 获取番剧数据\n"
            "  月份获取 <年月> <类型>  — 获取月份番剧\n"
            "  季度更新 <年月>        — 更新已有季度番剧\n"
            "\n"
            "  番剧群组添加 <群号>     — 添加群组白名单\n"
            "  番剧群组移除 <群号>     — 移除群组白名单\n"
            "  番剧群组列表           — 查看白名单\n"
            "  清理番剧缓存           — 清理图片缓存"
        )
    )


@anime_debug.handle()
async def handle_anime_debug():
    """调试命令，检查文件状态"""
    filepath = bgm_manager.get_json_path("bgm")

    message_parts = [
        f"文件存在: {filepath.exists()}",
        f"文件大小: {filepath.stat().st_size if filepath.exists() else 0} 字节",
        f"数据库记录数: {len(bgm_manager.all_data) if hasattr(bgm_manager, 'all_data') and bgm_manager.all_data else 0}"
    ]

    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        message_parts.append(f"实际文件记录数: {len(data)}")

    await anime_debug.send("\n".join(message_parts))


@anime_clear_cache.handle()
async def handle_anime_clear_cache():
    """清理图片缓存"""
    try:
        # 只清理bgm缓存
        if bgm_manager.cache_dir.exists():
            shutil.rmtree(bgm_manager.cache_dir)
            bgm_manager.cache_dir.mkdir(exist_ok=True)

        await anime_clear_cache.finish("番剧图片缓存已清理")
    except Exception as e:
        await anime_clear_cache.finish(f"清理缓存失败: {e}")

