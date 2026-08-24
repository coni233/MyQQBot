"""AutoSpeak 插件配置，全部有默认值，零配置即可加载。"""

from pydantic import BaseModel


class Config(BaseModel):
    """配置项通过 NoneBot 全局配置提供，全部可选。"""

    #: autospk 指令的响应优先级，数值越小越优先
    autospeak_command_priority: int = 10
