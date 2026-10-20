import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

from .anime_downloader import ImageManager
from ..config import CACHE_DIR, BGM_JSON, RESOURCE_DIR
from .anime_filter import normalize_for_person, get_display_title
from .anime_time import get_season_range, is_date_in_season, get_current_season

from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment, Message


class BGMDataManager:
    """BGM数据管理器"""

    def __init__(self, image_manager: ImageManager):
        self.plugin_dir = Path(__file__).parent
        self.resource_dir = RESOURCE_DIR
        self.cache_dir = CACHE_DIR
        self.bgm = BGM_JSON

        self.image_manager = image_manager

        self.all_data = None
        self.load_all_data()

    def load_all_data(self) -> Dict:
        """加载所有BGM数据"""
        try:
            filepath = self.bgm
            logger.info(f"从 {filepath} 加载 BGM 数据")

            if not filepath.exists():
                logger.warning("BGM 数据文件不存在，创建空数据集")
                self.all_data = {}
                return self.all_data

            with open(filepath, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            self.all_data = self._normalize_to_id_keys(raw_data)

            logger.success(f"成功加载 {len(self.all_data)} 条 BGM 数据")
            return self.all_data

        except Exception:
            logger.opt(exception=True).error("读取 BGM 文件失败")
            self.all_data = {}
            return self.all_data

    @staticmethod
    def _normalize_to_id_keys(raw_data: Dict) -> Dict:
        """把数据键统一为 str(条目id)"""
        normalized: Dict = {}
        merged = 0

        def _score(info: Dict) -> int:
            s = len(info.get('tags') or []) + len(info.get('characters') or []) * 2
            s += len(info.get('aliases') or [])
            staff = info.get('staff') or {}
            s += sum(len(v) for v in staff.values() if isinstance(v, list))
            prod = info.get('production') or {}
            s += sum(len(v) for v in prod.values() if isinstance(v, list))
            bi = info.get('basic_info') or {}
            if (bi.get('chinese_title') or '').strip():
                s += 3
            if (bi.get('original_title') or '').strip():
                s += 2
            return s

        for old_key, info in raw_data.items():
            if not isinstance(info, dict):
                continue

            # 键将改为 id
            bi = info.get('basic_info') or {}
            if not ((bi.get('chinese_title') or '').strip()
                    or (bi.get('original_title') or '').strip()
                    or (info.get('title_cn') or '').strip()
                    or (info.get('title_jp') or '').strip()):
                bi['original_title'] = old_key
                info['title_jp'] = old_key
                info['basic_info'] = bi

            anime_id = info.get('id')
            if anime_id is None:
                if old_key not in normalized:
                    normalized[old_key] = info
                continue

            key = str(anime_id)
            if key not in normalized:
                normalized[key] = info
                continue

            base, extra = normalized[key], info
            if _score(extra) > _score(base):
                normalized[key] = extra
                base, extra = extra, base
            tags = {t.get('name'): t for t in (base.get('tags') or [])}
            for t in extra.get('tags') or []:
                name = t.get('name')
                if name and (name not in tags or t.get('count', 0) > tags[name].get('count', 0)):
                    tags[name] = t
            base['tags'] = list(tags.values())
            aliases = list(base.get('aliases') or [])
            for a in extra.get('aliases') or []:
                if a not in aliases:
                    aliases.append(a)
            base['aliases'] = aliases
            merged += 1

        if merged:
            logger.warning(f"BGM 数据存在 {merged} 条重复 id，已按 id 合并")
        return normalized

    def load_from_json(self, filename: str) -> Optional[Dict]:
        """从JSON文件加载数据"""
        try:
            filepath = self.get_json_path(filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            logger.opt(exception=True).warning(f"读取 JSON 文件失败: {filename}")
            return None

    def get_json_path(self, filename: str) -> Path:
        """获取JSON文件路径"""
        if not filename.endswith('.json'):
            filename += '.json'
        return self.resource_dir / filename

    def update_anime_data(self, new_anime_data: Dict, anime_id: str = None, allow_add_new: bool = False) -> bool:
        """按 bgm 条目 id 更新番剧数据"""
        try:
            if not hasattr(self, 'all_data') or self.all_data is None:
                self.load_all_data()

            if not anime_id:
                anime_id = new_anime_data.get('id')

            if anime_id is None:
                logger.warning("无法确定番剧 id，跳过更新")
                return False

            key = str(anime_id)

            if key in self.all_data:
                logger.info(f"更新番剧: id={key}")

                old_tags = {t['name']: t for t in self.all_data[key].get('tags', [])}
                for t in new_anime_data.get('tags', []):
                    old_tags[t['name']] = t
                new_anime_data['tags'] = list(old_tags.values())

                self.all_data[key] = new_anime_data
                return self.save_all_data(self.all_data)

            elif allow_add_new:
                logger.info(f"添加新番剧: id={key}")
                self.all_data[key] = new_anime_data
                return self.save_all_data(self.all_data)

            else:
                logger.debug(f"未找到 id={key} 的现有番剧")
                return False

        except Exception:
            logger.opt(exception=True).error("更新番剧数据失败")
            return False

    def save_all_data(self, data: dict = None) -> bool:
        """保存所有数据到文件"""
        try:
            save_data = data if data is not None else self.all_data

            if save_data is None:
                logger.warning("没有数据可保存")
                return False

            filepath = self.bgm
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            logger.info(f"保存 BGM 数据完成（{len(save_data)} 条）")
            return True

        except Exception:
            logger.opt(exception=True).error("保存 BGM 数据失败")
            return False

    def search_anime_by_keyword(self, keyword: str) -> List[Tuple[str, Dict]]:
        """通过关键词搜索番剧，返回 [(显示名, 条目), ...]"""
        results = []

        if not hasattr(self, 'all_data') or self.all_data is None:
            self.load_all_data()

        data = self.all_data
        if not data:
            return results

        keyword_lower = keyword.lower()

        for dict_key, info in data.items():
            display_title = get_display_title(info) or str(dict_key)

            if keyword_lower in display_title.lower():
                results.append((display_title, info))
                continue

            if keyword_lower in (info.get('basic_info', {}).get('original_title', '') or '').lower():
                results.append((display_title, info))
                continue

            for alias in info.get('aliases', []):
                if keyword_lower in alias.lower():
                    results.append((display_title, info))
                    break

        logger.debug(f"搜索 '{keyword}' 找到 {len(results)} 条结果")
        return results

    def search_cv_names(self, cv_query: str) -> List[str]:
        """搜索CV名字"""
        cv_names = set()

        if not hasattr(self, 'all_data') or self.all_data is None:
            self.load_all_data()

        data = self.all_data
        if not data:
            return []

        cv_norm = normalize_for_person(cv_query)

        for info in data.values():
            for character in info.get('characters', []):
                cv_name = character.get('cv', '')
                if cv_norm in normalize_for_person(cv_name):
                    cv_names.add(cv_name)

        sorted_cv_names = sorted(list(cv_names))
        return sorted_cv_names

    def search_characters_by_exact_cv(self, cv_name: str) -> List[Tuple[str, Dict]]:
        """通过精确的CV名字搜索其配音的所有角色"""
        results = []

        if not hasattr(self, 'all_data') or self.all_data is None:
            self.load_all_data()

        data = self.all_data
        if not data:
            return results

        cv_norm = normalize_for_person(cv_name)

        for dict_key, info in data.items():
            anime_title = get_display_title(info) or '未知番剧'
            for character in info.get('characters', []):
                if normalize_for_person(character.get('cv', '')) == cv_norm:
                    character_info = character.copy()
                    character_info['anime_title'] = anime_title
                    character_info['anime_id'] = str(dict_key)
                    results.append((character_info['original_name'], character_info))

        return results

    def search_characters_by_name(self, character_name: str) -> List[Tuple[str, Dict]]:
        """通过角色名搜索角色"""
        results = []

        if not hasattr(self, 'all_data') or self.all_data is None:
            self.load_all_data()

        data = self.all_data
        if not data:
            return results

        character_name_lower = character_name.lower()

        for dict_key, info in data.items():
            anime_title = get_display_title(info) or '未知番剧'
            for character in info.get('characters', []):
                original_name = character.get('original_name', '')
                translated_name = character.get('translated_name', '')

                if (character_name_lower in original_name.lower()
                        or character_name_lower in translated_name.lower()):
                    character_info = character.copy()
                    character_info['anime_title'] = anime_title
                    character_info['anime_id'] = str(dict_key)
                    results.append((original_name, character_info))

        return results

    async def download_cover_image(self, img_url: str, anime_id: str) -> Optional[str]:
        """下载番剧封面图片"""
        return await self.image_manager.download_image(
            img_url, "cover", anime_id
        )

    def get_display_name_by_id(self, anime_id, fallback: str = "") -> str:
        """按条目 id 返回最新显示名"""
        if anime_id is not None and str(anime_id):
            info = self.all_data.get(str(anime_id))
            if info:
                return get_display_title(info) or str(anime_id)
        return fallback or (str(anime_id) if anime_id is not None else "未知番剧")

    async def download_character_image(self, img_url: str, character_name: str,
                                       anime_id=None) -> Optional[str]:
        """下载角色图片（缓存键使用 角色名 + 条目id）"""
        return await self.image_manager.download_image(
            img_url, "character", character_name, str(anime_id) if anime_id is not None else None
        )

    async def create_anime_message(self, title: str, info: Dict) -> List[MessageSegment]:
        """创建BGM格式消息"""
        message_parts = []

        cover_url = info.get('cover_url')
        if cover_url:
            anime_id = info.get('id', 'unknown')
            cover_path = await self.image_manager.download_image(
                cover_url, "cover", anime_id
            )
            if cover_path:
                try:
                    image_msg = MessageSegment.image(f"file:///{os.path.abspath(cover_path)}")
                    message_parts.append(image_msg)
                except Exception:
                    logger.warning("添加封面图片失败")

        basic_info = info.get('basic_info', {})
        production_info = info.get('production', {})
        tags = info.get('tags', [])
        rating_info = info.get('rating', {})

        sorted_tags = sorted(tags, key=lambda x: x.get('count', 0), reverse=True)[:3]
        tag_names = [tag['name'] for tag in sorted_tags]

        broadcast_time = basic_info.get('start_date', '')
        broadcast_day = basic_info.get('broadcast_day', '')
        if broadcast_day:
            broadcast_time = f"{broadcast_time} {broadcast_day}"

        # 构建评分信息
        score_text = "暂无评分"
        if rating_info:
            score = rating_info.get('score')
            description = rating_info.get('description', '')
            if score:
                score_text = f"{score} {description}" if description else f"{score}"

        japanese_title = basic_info.get('original_title', '') or info.get('title_jp', '')
        chinese_title = basic_info.get('chinese_title', '') or info.get('title_cn', '')

        text_parts = [
            f"番名：{japanese_title}",
            f"译名：{chinese_title}",
            f"总话数：{basic_info.get('episodes', '无')}",
            f"放送时间：{broadcast_time}",
            f"动画制作：{', '.join(production_info.get('animation_production', [])[:2]) or '无'}",
            f"标签：{', '.join(tag_names) if tag_names else '无'}",
            f"bgm评分：{score_text}"
        ]

        text_msg = MessageSegment.text("\n".join(text_parts))
        message_parts.append(text_msg)

        return message_parts

    @staticmethod
    def create_staff_message(title: str, info: Dict) -> str:
        """创建BGM格式的staff信息"""
        staff_info = info.get('staff', {})
        production_info = info.get('production', {})

        staff_parts = [
            f"导演：{', '.join(staff_info.get('director', [])) or '无'}",
            f"脚本：{', '.join(staff_info.get('script', [])) or '无'}",
            f"分镜：{', '.join(staff_info.get('storyboard', [])) or '无'}",
            f"演出：{', '.join(staff_info.get('episode_director', [])) or '无'}",
            f"音乐：{', '.join(staff_info.get('music', [])) or '无'}",
            f"人物原案：{', '.join(staff_info.get('character_design', [])) or '无'}",
            f"系列构成：{', '.join(staff_info.get('series_composition', [])) or '无'}",
            f"动画制作：{', '.join(production_info.get('animation_production', [])) or '无'}"
        ]

        return f"{title} - staff信息：\n" + "\n".join(staff_parts)

    def get_anime_by_season(self, year: int, month: int) -> List[Tuple[str, Dict]]:
        """获取指定季度的所有番剧（只返回tv类型）"""
        results = []

        # 确保使用最新数据
        if not hasattr(self, 'all_data') or self.all_data is None:
            self.load_all_data()

        data = self.all_data
        if not data:
            return results

        # 获取季度范围
        try:
            season_start, season_end = get_season_range(year, month)
        except ValueError:
            return results

        for dict_key, info in data.items():
            basic_info = info.get('basic_info', {})

            media_type = basic_info.get('media_type', '')
            if media_type != 'tv':
                continue

            start_date = basic_info.get('start_date', '')
            if not start_date:
                continue

            if is_date_in_season(start_date, season_start, season_end):
                results.append((get_display_title(info) or str(dict_key), info))

        return results

    def get_anime_by_season_and_weekday(self, year: int, month: int) -> Dict[str, List[Tuple[str, Dict]]]:
        """获取指定季度的番剧并按星期分组"""
        # 获取该季度的所有番剧
        season_animes = self.get_anime_by_season(year, month)

        # 初始化星期分组
        weekday_groups = {
            '星期一': [],
            '星期二': [],
            '星期三': [],
            '星期四': [],
            '星期五': [],
            '星期六': [],
            '星期日': [],
            '其他': []
        }

        # 有效的星期列表
        valid_weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']

        for title, info in season_animes:
            basic_info = info.get('basic_info', {})
            broadcast_day = basic_info.get('broadcast_day', '').strip()

            if broadcast_day and broadcast_day in valid_weekdays:
                weekday_groups[broadcast_day].append((title, info))
            else:
                weekday_groups['其他'].append((title, info))

        return weekday_groups

    def get_current_season_animes(self) -> Dict[str, List[Tuple[str, Dict]]]:
        """获取当前季度的番剧"""
        year, month = get_current_season()
        return self.get_anime_by_season_and_weekday(year, month)

    def get_today_animes(self) -> List[Tuple[str, Dict]]:
        """获取今天播出的番剧"""
        # 获取当前日期和星期
        now = datetime.now()
        weekdays_chinese = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        current_weekday = weekdays_chinese[now.weekday()]

        # 获取当前季度的番剧分组
        weekday_groups = self.get_current_season_animes()

        # 获取当前星期的番剧
        today_animes = []
        if current_weekday in weekday_groups:
            today_animes = weekday_groups[current_weekday]

        # 如果没有当前星期的番剧，检查"其他"组
        if not today_animes and weekday_groups.get('其他'):
            today_animes = weekday_groups['其他']

        return today_animes
