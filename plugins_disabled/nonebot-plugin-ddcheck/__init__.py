import traceback

from nonebot import require
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_localstore")

from nonebot_plugin_alconna import Alconna, Args, CommandMeta, UniMessage, on_alconna

from .config import Config
from .data_source import (
    BilibiliPrivateFollowingsError,
    get_attention_uids,
    get_medal_list,
    get_uid_by_name,
    get_user_info,
    get_vtb_list,
    render_ddcheck_image,
)

__plugin_meta__ = PluginMetadata(
    name="成分姬",
    description="查询B站用户关注的VTuber成分",
    usage="查成分 B站用户名/UID",
    type="application",
    homepage="https://github.com/noneplugin/nonebot-plugin-ddcheck",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={
        "example": "查成分 小南莓Official",
    },
)


ddcheck = on_alconna(
    Alconna(
        "查成分",
        Args["name#B站UID或用户名", str],
        meta=CommandMeta(description="查询B站用户关注的VTuber成分"),
    ),
    use_cmd_start=True,
    block=True,
    priority=12,
)


@ddcheck.handle()
async def _(matcher: Matcher, name: str):
    query = name.strip()
    if query.upper().startswith(("UID:", "UID：")):
        query = query[4:].strip()

    if query.isdigit():
        uid = int(query)
    else:
        try:
            uid = await get_uid_by_name(query)
        except Exception:
            logger.warning(traceback.format_exc())
            await matcher.finish("获取用户信息失败，请检查名称或使用uid查询")

        if not uid:
            await matcher.finish(f"未找到名为 {query} 的用户")

    try:
        user_info = await get_user_info(uid)
        attentions = await get_attention_uids(uid)
        user_info["attentions"] = attentions
    except BilibiliPrivateFollowingsError:
        await matcher.finish("该用户已将关注列表设为不可见，无法查询成分")
    except Exception:
        logger.warning(traceback.format_exc())
        await matcher.finish("获取用户信息失败，请检查名称或稍后再试")

    attentions = user_info.get("attentions", [])
    follows_num = int(user_info["attention"])
    if not attentions and follows_num:
        await matcher.finish("获取用户关注列表失败，关注列表可能未公开")

    vtb_list = await get_vtb_list()
    if not vtb_list:
        await matcher.finish("获取vtb列表失败，请稍后再试")

    try:
        medal_list = await get_medal_list(uid)
    except Exception:
        logger.warning(traceback.format_exc())
        medal_list = []

    try:
        result = await render_ddcheck_image(user_info, vtb_list, medal_list)
    except Exception:
        logger.warning(traceback.format_exc())
        await matcher.finish("出错了，请稍后再试")

    await UniMessage.image(raw=result).send()
