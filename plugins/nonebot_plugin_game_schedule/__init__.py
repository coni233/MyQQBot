from nonebot.plugin import PluginMetadata

from . import matcher  # noqa: F401


__plugin_meta__ = PluginMetadata(
    name="游戏日程查询",
    description="查询 coni.top 游戏日程：今日、本周或指定日期",
    usage="用法：\n"
    "  /游戏                  查看今天的游戏安排\n"
    "  /游戏 本周             查看本周游戏安排\n"
    "  /游戏 2026-08-22       查看指定日期游戏安排\n"
    "  快捷指令：/今日游戏 /本周游戏 /下周游戏",
    type="application",
    homepage="https://www.coni.top/game-schedule/",
    supported_adapters=None,
)
