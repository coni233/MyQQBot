"""游戏日程查询插件配置。"""

from pydantic import BaseModel


class Config(BaseModel):
    """插件配置，可通过环境变量或全局配置覆盖。"""

    # 游戏日程表 API 地址
    game_schedule_api_base: str = "https://www.coni.top/game-schedule/api.php"
