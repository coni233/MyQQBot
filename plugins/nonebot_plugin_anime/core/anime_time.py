import re
import datetime as dt
from datetime import datetime
from typing import List, Tuple, Optional

from nonebot import logger

from ..config import MIN_YEAR


# ==================== 季度范围处理函数 ====================
def get_season_range(year: int, month: int) -> Tuple[str, str]:
    """根据年份和月份获取季度范围"""
    if month == 1:  # 1月季度：12月20日到3月19日
        start_date = f"{year - 1}-12-20"
        end_date = f"{year}-03-19"
    elif month == 4:  # 4月季度：3月20日到6月19日
        start_date = f"{year}-03-20"
        end_date = f"{year}-06-19"
    elif month == 7:  # 7月季度：6月20日到9月19日
        start_date = f"{year}-06-20"
        end_date = f"{year}-09-19"
    elif month == 10:  # 10月季度：9月20日到12月19日
        start_date = f"{year}-09-20"
        end_date = f"{year}-12-19"
    else:
        raise ValueError("月份必须是1、4、7、10中的一个")

    return start_date, end_date


def parse_date_string(date_str: str) -> Optional[datetime]:
    """解析日期字符串"""
    if not date_str:
        return None

    date_str = re.sub(r'[年月日]', '-', date_str).strip('-')

    formats = [
        '%Y-%m-%d',
        '%Y-%m',
        '%Y'
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def is_date_in_season(anime_date: str, season_start: str, season_end: str) -> bool:
    """检查番剧播出时间是否在指定季度范围内"""
    anime_dt = parse_date_string(anime_date)
    start_dt = datetime.strptime(season_start, '%Y-%m-%d')
    end_dt = datetime.strptime(season_end, '%Y-%m-%d')

    if not anime_dt:
        return False

    return start_dt <= anime_dt <= end_dt


def is_date_in_year(anime_date: str, year: int) -> bool:
    """检查番剧播出时间是否在指定年份"""
    anime_dt = parse_date_string(anime_date)
    if not anime_dt:
        return False

    return anime_dt.year == year


# ==================== 时间范围处理函数 ====================
def get_max_year() -> int:
    """获取最大允许年份（当前年份+5）"""
    return dt.datetime.now().year + 5


def validate_year(year: int) -> bool:
    """验证年份是否在有效范围内"""
    return MIN_YEAR <= year <= get_max_year()


def validate_month(month: int) -> bool:
    """验证月份是否为有效季度月份"""
    return month in [1, 4, 7, 10]


def parse_date_range_optimized(date_range_str: str) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """解析时间范围字符串"""
    if not date_range_str or '-' not in date_range_str:
        return None, None

    try:
        # 支持多种分隔符：-、到、至
        date_range_str = date_range_str.replace('到', '-').replace('至', '-')
        start_str, end_str = date_range_str.split('-', 1)

        # 解析开始时间
        start_year, start_month = parse_single_date(start_str)
        # 解析结束时间
        end_year, end_month = parse_single_date(end_str)

        if not start_year or not end_year:
            return None, None

        # 验证年份范围
        if not validate_year(start_year) or not validate_year(end_year):
            return None, None

        # 验证月份
        if not validate_month(start_month) or not validate_month(end_month):
            return None, None

        # 验证时间顺序
        if start_year > end_year or (start_year == end_year and start_month > end_month):
            return None, None

        return (start_year, start_month), (end_year, end_month)

    except Exception:
        logger.warning("解析时间范围失败")
        return None, None


def parse_single_date(date_str: str) -> Tuple[Optional[int], Optional[int]]:
    """解析单个日期字符串，返回(年,月)"""
    date_str = date_str.strip()

    # 统一分隔符为 .
    date_str = re.sub(r'[年月日]', '.', date_str)
    date_str = re.sub(r'[-/]', '.', date_str)
    date_str = date_str.strip('.')

    parts = [p for p in date_str.split('.') if p]

    try:
        year = int(parts[0])
        month = 1

        if len(parts) >= 2:
            month = int(parts[1])
            if 1 <= month <= 3:
                month = 1
            elif 4 <= month <= 6:
                month = 4
            elif 7 <= month <= 9:
                month = 7
            elif 10 <= month <= 12:
                month = 10
            else:
                month = 1

        return year, month

    except (ValueError, IndexError):
        return None, None


def get_seasons_in_range(start_year: int, start_month: int, end_year: int, end_month: int) -> List[Tuple[int, int]]:
    """获取时间范围内的所有季度"""
    seasons = []

    current_year = start_year
    current_month = start_month

    while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
        seasons.append((current_year, current_month))

        # 移动到下一个季度
        if current_month == 1:
            current_month = 4
        elif current_month == 4:
            current_month = 7
        elif current_month == 7:
            current_month = 10
        elif current_month == 10:
            current_month = 1
            current_year += 1

        # 如果超出范围则停止
        if current_year > end_year or (current_year == end_year and current_month > end_month):
            break

    return seasons


# ==================== 获取当前季度的准确范围 ====================
def get_current_season() -> Tuple[int, int]:
    """获取当前日期所在的季度（年份和季度月份）"""
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_day = now.day

    # 检查当前年份的四个季度
    for season_month in [1, 4, 7, 10]:
        try:
            start_date_str, end_date_str = get_season_range(current_year, season_month)
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

            if start_date <= now <= end_date:
                return current_year, season_month
        except ValueError:
            continue

    # 检查下一年的1月季度
    try:
        start_date_str, end_date_str = get_season_range(current_year + 1, 1)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

        if start_date <= now <= end_date:
            return current_year + 1, 1
    except ValueError:
        pass

    # 根据月份和日期判断
    if 1 <= current_month <= 3:
        if current_month == 3 and current_day > 9:
            return current_year, 4
        return current_year, 1
    elif 4 <= current_month <= 6:
        if current_month == 6 and current_day > 9:
            return current_year, 7
        return current_year, 4
    elif 7 <= current_month <= 9:
        if current_month == 9 and current_day > 9:
            return current_year, 10
        return current_year, 7
    else:  # 10-12月
        if current_month == 12 and current_day > 9:
            return current_year + 1, 1
        return current_year, 10

# ==================== 星期写法归一化 ====================
WEEKDAY_MAPPING = {
    '星期一': '星期一', '周一': '星期一', '礼拜一': '星期一',
    '星期二': '星期二', '周二': '星期二', '礼拜二': '星期二',
    '星期三': '星期三', '周三': '星期三', '礼拜三': '星期三',
    '星期四': '星期四', '周四': '星期四', '礼拜四': '星期四',
    '星期五': '星期五', '周五': '星期五', '礼拜五': '星期五',
    '星期六': '星期六', '周六': '星期六', '礼拜六': '星期六',
    '星期日': '星期日', '周日': '星期日', '星期天': '星期日', '礼拜天': '星期日',
}


def normalize_weekday(text: str) -> Optional[str]:
    """把「周一/礼拜一/星期天」等写法归一化成「星期一」；无法识别返回 None"""
    if not text:
        return None
    return WEEKDAY_MAPPING.get(str(text).strip())
