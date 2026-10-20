import json

from typing import Dict, List, Optional
from .anime_data import BGMDataManager

from nonebot import logger




# ==================== 标签管理器 ====================
class TagManager:
    """BGM标签管理器"""

    def __init__(self, bgm_manager: BGMDataManager):
        self.bgm_manager = bgm_manager
        self.all_data = None
        self.load_all_data()

    def load_all_data(self):
        """加载所有数据到内存"""
        self.all_data = self.bgm_manager.load_all_data()

    def save_all_data(self):
        """保存所有数据到文件"""
        try:
            if self.all_data is None:
                self.load_all_data()

            filepath = self.bgm_manager.get_json_path("bgm")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.all_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.opt(exception=True).error("保存标签数据失败")
            return False

    def get_anime_tags(self, anime_info: Dict) -> List[str]:
        """获取番剧的标签列表"""
        tags = anime_info.get('tags', [])
        return [tag['name'] for tag in tags] if isinstance(tags, list) else []

    def _find_anime(self, anime_info: Dict) -> Optional[Dict]:
        """按条目 id 定位实际存储的记录"""
        if self.all_data is None:
            self.load_all_data()
        anime_id = anime_info.get('id') if isinstance(anime_info, dict) else None
        if anime_id is None:
            return None
        return self.all_data.get(str(anime_id))

    def add_tag(self, anime_info: Dict, tag_name: str, title: str = "") -> bool:
        """为番剧添加标签"""
        try:
            if self.all_data is None:
                self.load_all_data()

            target_anime = self._find_anime(anime_info)
            if target_anime is None:
                logger.warning(f"标签操作: 找不到番剧 '{title or anime_info}'")
                return False

            if 'tags' not in target_anime or not isinstance(target_anime['tags'], list):
                target_anime['tags'] = []

            if any(t.get('name') == tag_name for t in target_anime['tags']):
                return False

            target_anime['tags'].append({'name': tag_name, 'count': 0})

            if anime_info is not target_anime:
                if 'tags' not in anime_info or not isinstance(anime_info['tags'], list):
                    anime_info['tags'] = []
                if not any(t.get('name') == tag_name for t in anime_info['tags']):
                    anime_info['tags'].append({'name': tag_name, 'count': 0})

            if self.save_all_data():
                logger.info(f"添加标签 '{tag_name}' 到《{title}》(id={target_anime.get('id')})")
                return True
            return False

        except Exception:
            logger.opt(exception=True).error("添加标签失败")
            return False

    def remove_tag(self, anime_info: Dict, tag_name: str, title: str = "") -> bool:
        """删除番剧的标签"""
        try:
            if self.all_data is None:
                self.load_all_data()

            target_anime = self._find_anime(anime_info)
            if target_anime is None:
                logger.warning(f"标签操作: 找不到番剧 '{title or anime_info}'")
                return False

            if 'tags' not in target_anime or not isinstance(target_anime['tags'], list):
                return False

            original_length = len(target_anime['tags'])
            target_anime['tags'] = [tag for tag in target_anime['tags']
                                    if tag.get('name') != tag_name]

            if len(target_anime['tags']) == original_length:
                return False

            if anime_info is not target_anime and isinstance(anime_info, dict):
                if 'tags' in anime_info and isinstance(anime_info['tags'], list):
                    anime_info['tags'] = [tag for tag in anime_info['tags']
                                          if tag.get('name') != tag_name]

            if self.save_all_data():
                logger.info(f"删除标签 '{tag_name}' 从《{title}》(id={target_anime.get('id')})")
                return True
            return False

        except Exception:
            logger.opt(exception=True).error("删除标签失败")
            return False

    def format_tags_display(self, tags: List[str]) -> str:
        """格式化标签显示 - 修复：显示全部标签"""
        if not tags:
            return "暂无标签"

        return "，".join(tags)