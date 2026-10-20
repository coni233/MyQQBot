from .anime_downloader import ImageManager
from .anime_data import BGMDataManager
from .anime_tag import TagManager
from .anime_score import UserScoreManager, CharacterScoreManager
from .anime_permissons import group_permission_manager
from .anime_image import CharacterScoreImageGenerator, AnimeScoreImageGenerator, SeasonPosterGenerator
from .anime_api import BangumiAPIClient

# 1. 图片管理器
image_manager = ImageManager()

# 2. BGM 数据管理器
bgm_manager = BGMDataManager(image_manager)

# 3. 标签管理器
tag_manager = TagManager(bgm_manager)

# 4. 用户评分管理器
user_score_manager = UserScoreManager()

# 5. 角色评级管理器
character_score_manager = CharacterScoreManager(bgm_manager)

# 6. Bangumi API
bgm_api = BangumiAPIClient()

# 7. 图片生成器
character_image_generator = CharacterScoreImageGenerator(bgm_manager, character_score_manager)
anime_score_image_generator = AnimeScoreImageGenerator(bgm_manager, user_score_manager)

# 8. 季度/星期海报生成器（依赖 BGMDataManager）
season_poster_generator = SeasonPosterGenerator(bgm_manager)


__all__ = [
    "image_manager",
    "bgm_manager",
    "tag_manager",
    "user_score_manager",
    "character_score_manager",
    "bgm_api",
    "group_permission_manager",
    "character_image_generator",
    "anime_score_image_generator",
    "season_poster_generator",
]