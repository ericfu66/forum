"""
用户设置服务
存储用户的个性化设置（如思维链显示偏好等）
"""
from typing import Dict, Any
from app.models.user_settings import UserSettings
from app.extensions import db


def get_thinking_visible(user_id: int) -> bool:
    """获取用户的思维链显示偏好"""
    return UserSettings.get_user_setting(user_id, 'thinking_visible', True)


def set_thinking_visible(user_id: int, visible: bool) -> None:
    """设置用户的思维链显示偏好"""
    UserSettings.set_user_setting(user_id, 'thinking_visible', visible)


def get_user_settings(user_id: int) -> Dict[str, Any]:
    """获取用户的所有设置"""
    settings = UserSettings.get_or_create(user_id)
    return settings.get_settings()


def update_user_settings(user_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """更新用户设置"""
    settings = UserSettings.get_or_create(user_id)
    settings.set_settings(updates)
    db.session.commit()
    return settings.get_settings()
