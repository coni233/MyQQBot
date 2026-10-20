import time
from typing import Dict, Union
from .anime_permissons import group_permission_manager

from nonebot.adapters.onebot.v11 import Event, PrivateMessageEvent, GroupMessageEvent


class UserSession:
    """统一的用户会话状态"""

    def __init__(self):
        self.session_type = None
        self.search_results = []
        self.characters = []
        self.anime_title = ""
        self.search_type = ""
        self.search_query = ""
        self.current_page = 0
        self.page_size = 10
        self.total_pages = 0
        self.timestamp = 0

        # 用于标签管理
        self.current_anime = None  # 当前操作的番剧信息
        self.current_anime_title = ""  # 当前操作的番剧标题

        # 用于评分管理
        self.score_username = ""  # 评分用户特征名
        self.score_value = 0.0  # 评分分数

        # 用于评分删除
        self.delete_scores = []  # 要删除的评分列表
        self.delete_username = ""  # 要删除评分的用户名

        # 用于CV搜索
        self.selected_cv = ""  # 选择的CV名字

        # 用于角色评级
        self.character_username = ""  # 角色评级用户特征名
        self.character_score = 0  # 角色评级分数

        # 用于角色评级删除
        self.delete_character_scores = []  # 要删除的角色评级列表

        # 用于季度和星期查看
        self.view_year = 0
        self.view_month = 0
        self.view_month_name = ""
        self.view_target_weekday = None
        self.view_weekday_groups = {}


user_sessions: Dict[str, UserSession] = {}


def get_session_key(event: Event) -> str:
    """生成会话键值：用户ID_群组ID"""
    user_id = event.get_user_id()

    # 私聊
    if isinstance(event, PrivateMessageEvent):
        return f"{user_id}_private"

    # 群聊
    if isinstance(event, GroupMessageEvent):
        return f"{user_id}_{event.group_id}"

    return f"{user_id}_unknown"


def get_user_session(event: Event) -> UserSession:
    """获取用户会话（基于事件）"""
    session_key = get_session_key(event)
    if session_key not in user_sessions:
        user_sessions[session_key] = UserSession()
    return user_sessions[session_key]


def clear_user_session(event: Event):
    """清除用户会话（基于事件）"""
    session_key = get_session_key(event)
    if session_key in user_sessions:
        del user_sessions[session_key]


def cleanup_old_sessions():
    """清理过期的会话"""
    current_time = time.time()
    expired_users = []
    for user_id, session in user_sessions.items():
        if current_time - session.timestamp > 300:  # 5分钟过期
            expired_users.append(user_id)
    for user_id in expired_users:
        del user_sessions[user_id]


def set_session(event: Event, session_type: str, **kwargs):
    """设置用户会话"""
    # 先清除旧的会话状态
    clear_user_session(event)

    # 创建新会话
    session = get_user_session(event)
    session.session_type = session_type
    session.timestamp = time.time()

    # 设置默认值
    session.current_anime = None
    session.current_anime_title = ""

    # 根据会话类型设置相关属性
    for key, value in kwargs.items():
        if hasattr(session, key):
            setattr(session, key, value)


async def is_user_session_event(event: Union[PrivateMessageEvent, GroupMessageEvent]) -> bool:
    """检查是否是用户会话消息"""
    message = event.get_message()
    text = message.extract_plain_text().strip()

    cleanup_old_sessions()

    session = get_user_session(event)

    if not session.session_type:
        return False

    # 群聊必须在白名单中
    if isinstance(event, GroupMessageEvent) and not group_permission_manager.is_group_allowed(str(event.group_id)):
        return False

    # 纯数字（选择编号）
    if text.isdigit():
        if session.search_results:
            total_results = len(session.search_results)
            if int(text) == 0:
                return True
            if 1 <= int(text) <= total_results:
                return True
        elif session.session_type == 'cv_list' and session.characters:
            if 1 <= int(text) <= len(session.characters):
                return True

    # 翻页指令
    if session.search_results:
        if text.lower() in ['n', 'next', '下一页', 'p', 'prev', 'previous', '上一页']:
            return True
        if text.lower().startswith(('p', 'page')):
            page_text = text.lower().replace('p', '').replace('age', '').strip()
            if page_text.isdigit():
                return True

    return False