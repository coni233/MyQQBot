from pathlib import Path

from nonebot import require
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from nonebot.plugin import get_plugin_config
from pydantic import BaseModel


# Bangumi API 固定标识（请勿修改）
BANGUMI_API_UA = "ShioMI39/nonebot-plugin-anime (https://github.com/ShioMI39/nonebot-plugin-anime)"

class AnimeConfig(BaseModel):
    """番剧插件配置"""
    http_proxy: str = ""
    bgm_api_token: str = ""
    resource_dir: str = ""
    private_allow: bool = True


class Config(BaseModel):
    anime: AnimeConfig = AnimeConfig()


_cfg = get_plugin_config(Config).anime

HTTP_PROXY = _cfg.http_proxy
BANGUMI_API_TOKEN = _cfg.bgm_api_token
PRIVATE_ALLOW = _cfg.private_allow

# ====== 路径配置 ======
_data_dir = store.get_plugin_data_dir()
_cache_dir = store.get_plugin_cache_dir()

# 未配置时回退到插件数据目录下的 resource/，这样缺少资源包也能正常加载；
# 把 bangumi_resource 资源包解压到这里（或设置 ANIME__RESOURCE_DIR）即可获得完整数据
RESOURCE_DIR: Path = (
    Path(_cfg.resource_dir)
    if _cfg.resource_dir
    else _data_dir / "resource"
)
CACHE_DIR = _cache_dir
FONTS_DIR = RESOURCE_DIR / "fonts"
BGM_JSON = RESOURCE_DIR / "bgm.json"

SCORE_JSON = store.get_plugin_data_file("score.json")
CHARACTER_SCORE_JSON = store.get_plugin_data_file("character_score.json")
GROUP_PERMISSION_JSON = store.get_plugin_data_file("group_permission.json")

# ====== 固定常量 ======
STAFF_ROLE_MAPPING = {
    "导演": "director", "脚本": "script", "分镜": "storyboard",
    "演出": "episode_director", "音乐": "music",
    "人物原案": "character_design", "系列构成": "series_composition",
    "director": "director", "监督": "director", "script": "script",
    "storyboard": "storyboard", "episode_director": "episode_director",
    "music": "music", "character_design": "character_design",
    "series_composition": "series_composition",
}

FILTER_KEYWORDS_LOWER = {
    '标签', 'tag', 'tags',
    '分数', '评分', 'score',
    'cv', '声优', '配音',
    '导演', 'director','监督',
    '制作', '制作公司', '动画制作',
    'staff', '制作人员',
    '季度', '时间',
    '类型',
    '关键词', '标题', 'keyword'
}

MIN_YEAR = 1900
MONTH_NAMES = {1: "一月", 4: "四月", 7: "七月", 10: "十月"}

SUBJECT_TYPE_LABEL = {1: "书籍", 2: "动画", 3: "音乐", 4: "游戏", 6: "三次元"}

QUARTER_MONTHS = {
    1: ("01", "03"), 4: ("04", "06"),
    7: ("07", "09"), 10: ("10", "12"),
}


def ensure_dirs() -> None:
    RESOURCE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_dir.mkdir(parents=True, exist_ok=True)
    _data_dir.mkdir(parents=True, exist_ok=True)
