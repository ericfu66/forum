"""
用户设置模型
存储用户的个性化设置（如思维链显示偏好等）
"""
import json
from typing import Dict, Any
from app.extensions import db
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified


class UserSettings(db.Model):
    """用户设置模型"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    settings_json = db.Column(db.Text, default='{}')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = db.relationship('User', backref=db.backref('settings', uselist=False))
    
    # 默认设置
    DEFAULT_SETTINGS = {
        'thinking_visible': True,  # 是否显示思维链
        'theme': 'auto',           # 主题：auto, light, dark
        'ai_greeting_enabled': True,  # 是否显示AI问候
        'cat_girl_background': 'default',  # 猫娘聊天背景
        'novel_preset_config': {},  # 小说区预设配置
        'novel_user_persona': '',   # 小说区用户Persona
        'novel_regex_rules': [],    # 小说区正则表达式规则
    }
    
    # 猫娘聊天背景预设
    CAT_GIRL_BACKGROUNDS = {
        'default': {
            'name': '默认粉色',
            'preview': '🌸',
            'css': 'linear-gradient(180deg, color-mix(in srgb, var(--bg-primary) 95%, #FFB6C1 5%) 0%, var(--bg-primary) 100%)'
        },
        'sakura': {
            'name': '樱花飘落',
            'preview': '🌸',
            'css': 'linear-gradient(135deg, #ffeef8 0%, #fff5f8 50%, #ffe8f0 100%)'
        },
        'night_sky': {
            'name': '星空夜色',
            'preview': '🌙',
            'css': 'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)'
        },
        'ocean': {
            'name': '海洋蓝',
            'preview': '🌊',
            'css': 'linear-gradient(180deg, #e0f7fa 0%, #b2ebf2 50%, #80deea 100%)'
        },
        'sunset': {
            'name': '日落黄昏',
            'preview': '🌅',
            'css': 'linear-gradient(180deg, #fff3e0 0%, #ffe0b2 50%, #ffcc80 100%)'
        },
        'forest': {
            'name': '森林绿意',
            'preview': '🌲',
            'css': 'linear-gradient(180deg, #e8f5e9 0%, #c8e6c9 50%, #a5d6a7 100%)'
        },
        'lavender': {
            'name': '薰衣草紫',
            'preview': '💜',
            'css': 'linear-gradient(180deg, #f3e5f5 0%, #e1bee7 50%, #ce93d8 100%)'
        },
        'pure_white': {
            'name': '纯净白',
            'preview': '⬜',
            'css': 'var(--bg-primary)'
        }
    }
    
    def get_settings(self) -> Dict[str, Any]:
        """获取设置字典"""
        try:
            settings = json.loads(self.settings_json or '{}')
        except json.JSONDecodeError:
            settings = {}
        
        # 合并默认值
        result = dict(self.DEFAULT_SETTINGS)
        result.update(settings)
        return result
    
    def set_settings(self, settings: Dict[str, Any]) -> None:
        """设置配置"""
        current = self.get_settings()
        current.update(settings)
        self.settings_json = json.dumps(current, ensure_ascii=False)
        flag_modified(self, 'settings_json')
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取单个设置"""
        settings = self.get_settings()
        return settings.get(key, default if default is not None else self.DEFAULT_SETTINGS.get(key))
    
    def set_setting(self, key: str, value: Any) -> None:
        """设置单个配置"""
        settings = self.get_settings()
        settings[key] = value
        self.settings_json = json.dumps(settings, ensure_ascii=False)
        flag_modified(self, 'settings_json')
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'settings': self.get_settings(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @staticmethod
    def get_or_create(user_id: int) -> 'UserSettings':
        """获取或创建用户设置"""
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
    
    @staticmethod
    def get_user_setting(user_id: int, key: str, default: Any = None) -> Any:
        """便捷方法：获取用户的某个设置"""
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            return default if default is not None else UserSettings.DEFAULT_SETTINGS.get(key)
        return settings.get_setting(key, default)
    
    @staticmethod
    def set_user_setting(user_id: int, key: str, value: Any) -> None:
        """便捷方法：设置用户的某个配置"""
        settings = UserSettings.get_or_create(user_id)
        settings.set_setting(key, value)
        db.session.commit()
    
    @classmethod
    def get_cat_girl_backgrounds(cls) -> dict:
        """获取所有猫娘背景预设"""
        return cls.CAT_GIRL_BACKGROUNDS
    
    @classmethod
    def get_cat_girl_background_css(cls, background_key: str) -> str:
        """获取指定背景的CSS"""
        bg = cls.CAT_GIRL_BACKGROUNDS.get(background_key, cls.CAT_GIRL_BACKGROUNDS['default'])
        return bg['css']
