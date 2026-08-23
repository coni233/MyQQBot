from nonebot.plugin import PluginMetadata

from . import matcher  # noqa: F401


__plugin_meta__ = PluginMetadata(
    name="退休倒计时",
    description="计算预计退休日期以及距离退休还有多少天",
    usage="用法：\n"
    "  /退休                    交互式输入出生日期与性别\n"
    "  /退休 1995-01-01 男      直接传入出生日期与性别",
    type="application",
    homepage="https://github.com/coni233/nonebot-plugin-retirement-countdown",
    supported_adapters=None,
)
