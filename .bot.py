# 不推荐用bot.py启动，推荐nb run启动
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter


def main():
    # 初始化 NoneBot
    nonebot.init()

    # 获取 Driver
    driver = nonebot.get_driver()

    # 注册 OneBot V11 Adapter
    driver.register_adapter(OneBotV11Adapter)

    # 加载 NoneBot 内置插件
    nonebot.load_builtin_plugin("echo")

    # 加载第三方插件
    nonebot.load_plugin("nonebot_plugin_status")
    nonebot.load_plugin("nonebot_plugin_apscheduler")
    nonebot.load_plugin("nonebot_plugin_localstore")

    # 加载自己的插件
    nonebot.load_plugins("plugins")

    # 启动机器人
    nonebot.run()


if __name__ == "__main__":
    main()
