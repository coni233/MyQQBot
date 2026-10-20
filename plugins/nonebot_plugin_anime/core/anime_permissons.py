import json
from typing import List, Union

from ..config import GROUP_PERMISSION_JSON, PRIVATE_ALLOW

from nonebot import logger
from nonebot.adapters.onebot.v11 import PrivateMessageEvent, GroupMessageEvent


# ==================== 群组权限管理器 ====================
class GroupPermissionManager:
    """群组权限管理器"""

    def __init__(self):
        self.group_file = GROUP_PERMISSION_JSON
        self.allowed_groups = self.load_allowed_groups()

    def load_allowed_groups(self) -> List[str]:
        """加载允许的群组列表"""
        try:
            if self.group_file.exists():
                with open(self.group_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('allowed_groups', [])
            else:
                default_data = {'allowed_groups': []}
                self.group_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.group_file, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=2)
                return []
        except Exception:
            logger.opt(exception=True).error("加载群组权限失败")
            return []

    def save_allowed_groups(self) -> bool:
        """保存允许的群组列表"""
        try:
            data = {'allowed_groups': self.allowed_groups}
            with open(self.group_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            logger.opt(exception=True).error("保存群组权限失败")
            return False

    def add_group(self, group_id: str) -> bool:
        """添加群组到白名单"""
        if group_id not in self.allowed_groups:
            self.allowed_groups.append(group_id)
            return self.save_allowed_groups()
        return True

    def remove_group(self, group_id: str) -> bool:
        """从白名单移除群组"""
        if group_id in self.allowed_groups:
            self.allowed_groups.remove(group_id)
            return self.save_allowed_groups()
        return True

    def is_group_allowed(self, group_id: str) -> bool:
        """检查群组是否在允许列表中"""
        return group_id in self.allowed_groups

    def get_allowed_groups(self) -> List[str]:
        """获取所有允许的群组"""
        return self.allowed_groups.copy()


group_permission_manager = GroupPermissionManager()


# ==================== 权限检查函数 ====================
async def is_private_or_allowed_group(event: Union[PrivateMessageEvent, GroupMessageEvent]) -> bool:
    """检查白名单"""
    if isinstance(event, PrivateMessageEvent):
        if PRIVATE_ALLOW:
            return True
        else:
            return False
    return group_permission_manager.is_group_allowed(str(event.group_id))