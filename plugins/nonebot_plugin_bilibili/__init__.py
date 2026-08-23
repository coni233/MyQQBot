from nonebot.plugin import PluginMetadata
from nonebot import logger, require, get_driver

require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

from .api import bilibili_api  # noqa: E402
from .renderer import renderer  # noqa: E402
from .database import repository  # noqa: E402
from .config import Config, plugin_config  # noqa: E402
from .web import install_web, ensure_web_token  # noqa: E402
from .jobs import install_jobs, poll_dynamics, load_runtime_config  # noqa: E402
from .selectors import register_font_selector, register_template_selector  # noqa: E402

__plugin_meta__ = PluginMetadata(
    name="Bilibili 动态/直播订阅",
    description=(
        "基于 OneBot V11 的 Bilibili 动态、视频与直播订阅推送插件，"
        "支持扫码登录、图片卡片、关键词过滤、@全体和 Web 管理后台。"
    ),
    usage=(
        "发送 /bili help 查看完整帮助。\n"
        "常用命令：\n"
        "/bili add <uid> - 订阅 UP 主\n"
        "/bili del <uid> - 取消订阅\n"
        "/bili list - 查看本群订阅\n"
        "/bili push dynamic|video|live <编号> - 手动推送\n"
        "/bili login - Bilibili 扫码登录（超级用户）"
    ),
    type="application",
    homepage="https://github.com/mengbingnaixi/nonebot-plugin-bilibili",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={},
)


install_web()

driver = get_driver()


@driver.on_startup
async def _startup() -> None:
    await repository.initialize()
    await load_runtime_config()
    if not await renderer.prepare():
        logger.warning(
            "Bilibili subscription will use text fallback until Chromium becomes available"
        )
    if plugin_config.bili_subscription_enable_dynamic:
        await poll_dynamics()
    install_jobs()
    if plugin_config.bili_subscription_enable_dynamic and not await repository.get_setting(
        "bilibili_cookie"
    ):
        logger.warning(
            "Bilibili subscription has no Cookie; dynamic polling is paused. "
            "Use /bili login or the web UI to sign in."
        )
    if plugin_config.bili_subscription_web_enabled:
        token = await ensure_web_token()
        logger.warning(
            "Bilibili subscription web management token: {} (path: {}/)",
            token,
            plugin_config.bili_subscription_web_path,
        )


@driver.on_shutdown
async def _shutdown() -> None:
    await renderer.close()
    await bilibili_api.close()


# Importing registers the /bili command matcher.
from . import commands as commands  # noqa: E402,F401

__all__ = [
    "Config",
    "commands",
    "plugin_config",
    "register_font_selector",
    "register_template_selector",
]
