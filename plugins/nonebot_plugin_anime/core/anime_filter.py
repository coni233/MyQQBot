import re
import opencc

from typing import Dict, List, Tuple, Optional
from ..config import STAFF_ROLE_MAPPING
from .anime_time import (
    parse_date_range_optimized,
    get_seasons_in_range,
    get_season_range,
    is_date_in_season,
    is_date_in_year,
    parse_single_date,
)

_cc_jp2t = opencc.OpenCC('jp2t')
_cc_t2s = opencc.OpenCC('t2s')


def get_display_title(info: Dict) -> str:
    """从条目数据中取可读番剧名"""
    if not isinstance(info, dict):
        return ""
    basic_info = info.get('basic_info') or {}
    for key in ('chinese_title', 'original_title'):
        val = (basic_info.get(key) or "").strip()
        if val:
            return val
    for key in ('title_cn', 'title_jp'):
        val = (info.get(key) or "").strip()
        if val:
            return val
    return ""


def normalize_for_person(text: str) -> str:
    """将人名中的日语汉字归一化为简体中文
    日语汉字 - 繁中 - 简中
    """
    text = _cc_jp2t.convert(text)
    text = _cc_t2s.convert(text)
    return text.lower()


def parse_score_value(score_str: str) -> Tuple[str, float, float]:
    """解析评分数值字符串。

    支持格式：
    - 单个数值: "9.0" "6.5" "10"  → min=max=该值
    - 范围:     "6-8.5" "3.0-7.0"  → min/max
    - 比较:     "≥8" "<=6"          → 单边比较

    校验：范围 0.0–10.0，最多一位小数，不符合则抛出 ValueError。
    返回 (描述, min, max)。
    """
    score_str = score_str.strip()

    if not score_str:
        raise ValueError("分数不能为空")

    # ≥ / <=  单边比较
    if score_str.startswith('≥') or score_str.startswith('>='):
        v = _validate_score(score_str.lstrip('≥>='))
        return f"≥{v}", v, 10.0

    if score_str.startswith('≤') or score_str.startswith('<='):
        v = _validate_score(score_str.lstrip('≤<='))
        return f"≤{v}", 0.0, v

    # 范围
    if '-' in score_str:
        parts = score_str.split('-', 1)
        lo = _validate_score(parts[0].strip())
        hi = _validate_score(parts[1].strip())
        if lo > hi:
            lo, hi = hi, lo
        return f"{lo}-{hi}", lo, hi

    # 单个数值
    v = _validate_score(score_str)
    return str(v), v, v


def _validate_score(raw: str) -> float:
    """校验并转换单个分数：0.0–10.0，最多一位小数。不符合抛出 ValueError。"""
    raw = raw.strip()
    if not re.match(r'^(?:10(?:\.0)?|[0-9](?:\.[0-9])?)$', raw):
        raise ValueError(f"无效的分数 '{raw}'，应为 0.0–10.0 的一位小数")
    val = float(raw)
    if val < 0 or val > 10:
        raise ValueError(f"分数 '{raw}' 超出 0.0–10.0 范围")
    return val


def filter_anime(all_data: Dict[str, Dict], filters: Dict) -> List[Tuple[str, Dict]]:
    """番剧筛选
    支持：
        keyword:    str   — 标题
        tags:       List[str] — 标签列表（全部匹配）
        score_min:  float — 最低BGM评分
        score_max:  float — 最高BGM评分
        cv:         str   — 声优名
        director:   str   — 导演名
        staff:      str   — 制作人员名
        staff_role: str   — 限定staff角色（与staff配合使用）
        production: str   — 制作公司
        date_range: str   — 时间范围字符串（如"2025年4月-2026年4月"）
        year:       int   — 单年份筛选
        month:      int   — 单季度月份
        media_type: str   — 类型（tv/movie）

    返回: List[Tuple[str, Dict]]
    """
    if not all_data:
        return []

    seasons = None
    season_range_tuple = None

    if 'date_range' in filters:
        date_val = filters['date_range']
        start_dt, end_dt = parse_date_range_optimized(date_val)
        if start_dt and end_dt:
            seasons = get_seasons_in_range(start_dt[0], start_dt[1], end_dt[0], end_dt[1])
        else:
            # 不是范围格式，尝试当作单个日期/季度解析
            single_year, single_month = parse_single_date(date_val)
            if single_year:
                filters['year'] = single_year
                if re.search(r'\d{1,2}月', date_val):
                    filters['month'] = single_month

    if seasons is None and 'year' in filters:
        year = filters['year']
        if 'month' in filters:
            season_range_tuple = get_season_range(year, filters['month'])

    results = []
    for dict_key, info in all_data.items():
        # 1. 关键词
        if 'keyword' in filters:
            kw = filters['keyword'].lower()
            display_title = get_display_title(info)
            matched = kw in display_title.lower()
            if not matched:
                aliases = info.get('aliases', [])
                for alias in aliases:
                    if kw in alias.lower():
                        matched = True
                        break
            if not matched:
                continue

        # 2. 标签
        if 'tags' in filters:
            anime_tags = [t['name'].lower() for t in info.get('tags', [])]
            if not all(tag.lower() in anime_tags for tag in filters['tags']):
                continue

        # 3. 评分范围
        score_min = filters.get('score_min')
        score_max = filters.get('score_max')
        if score_min is not None or score_max is not None:
            score_str = info.get('rating', {}).get('score')
            if not score_str:
                continue
            try:
                score_val = float(score_str)
            except (ValueError, TypeError):
                continue
            if score_min is not None and score_val < score_min:
                continue
            if score_max is not None and score_val > score_max:
                continue

        # 4. CV
        if 'cv' in filters:
            cv_norm = normalize_for_person(filters['cv'])
            found = False
            for char in info.get('characters', []):
                if cv_norm in normalize_for_person(char.get('cv', '')):
                    found = True
                    break
            if not found:
                continue

        # 5. 导演
        if 'director' in filters:
            director_norm = normalize_for_person(filters['director'])
            found = False
            for d in info.get('staff', {}).get('director', []):
                if director_norm in normalize_for_person(d):
                    found = True
                    break
            if not found:
                continue

        # 6. 制作人员/staff
        if 'staff' in filters:
            staff_norm = normalize_for_person(filters['staff'])
            staff_role = filters.get('staff_role')
            staff_dict = info.get('staff', {})
            found = False
            if staff_role:
                mapped_role = STAFF_ROLE_MAPPING.get(staff_role, staff_role)
                people = staff_dict.get(mapped_role, [])
                for person in people:
                    if staff_norm in normalize_for_person(person):
                        found = True
                        break
            else:
                for role, people in staff_dict.items():
                    for person in people:
                        if staff_norm in normalize_for_person(person):
                            found = True
                            break
                    if found:
                        break
            if not found:
                continue

        # 7. 制作公司
        if 'production' in filters:
            prod_lower = normalize_for_person(filters['production']).lower()
            found = False
            for p in info.get('production', {}).get('animation_production', []):
                if prod_lower in normalize_for_person(p).lower():
                    found = True
                    break
            if not found:
                continue

        # 8. 时间范围 / 季度
        start_date = info.get('basic_info', {}).get('start_date', '')
        if seasons is not None:
            found = False
            for s_year, s_month in seasons:
                try:
                    s_start, s_end = get_season_range(s_year, s_month)
                    if is_date_in_season(start_date, s_start, s_end):
                        found = True
                        break
                except ValueError:
                    continue
            if not found:
                continue
        elif season_range_tuple is not None:
            season_start, season_end = season_range_tuple
            if not is_date_in_season(start_date, season_start, season_end):
                continue
        elif 'year' in filters and 'month' not in filters:
            if not is_date_in_year(start_date, filters['year']):
                continue

        # 9. 类型
        if 'media_type' in filters:
            if info.get('basic_info', {}).get('media_type', '') != filters['media_type']:
                continue

        results.append((get_display_title(info) or str(dict_key), info))

    return results
