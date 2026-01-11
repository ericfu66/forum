"""
用户自定义AI助手模型
"""
from app.extensions import db
from datetime import datetime
from typing import List, Optional, Dict, Any


class CustomAssistant(db.Model):
    """用户自定义AI助手"""
    __tablename__ = 'custom_assistants'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(10), nullable=False, default='🤖')
    description = db.Column(db.String(200), default='')
    system_prompt = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = db.relationship('User', backref=db.backref('custom_assistants', lazy='dynamic'))

    # 每用户最大助手数量
    MAX_ASSISTANTS_PER_USER = 10

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'icon': self.icon,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def create(user_id: int, name: str, icon: str, description: str, 
               system_prompt: str) -> 'CustomAssistant':
        """
        创建自定义助手
        
        Args:
            user_id: 用户ID
            name: 助手名称
            icon: 图标emoji
            description: 简短描述
            system_prompt: 系统提示词
            
        Returns:
            CustomAssistant: 创建的助手实例
            
        Raises:
            ValueError: 如果超过最大数量限制
        """
        # 检查数量限制
        count = CustomAssistant.count_by_user(user_id)
        if count >= CustomAssistant.MAX_ASSISTANTS_PER_USER:
            raise ValueError(f'最多创建{CustomAssistant.MAX_ASSISTANTS_PER_USER}个自定义助手')
        
        assistant = CustomAssistant(
            user_id=user_id,
            name=name,
            icon=icon or '🤖',
            description=description or '',
            system_prompt=system_prompt
        )
        db.session.add(assistant)
        db.session.commit()
        return assistant

    @staticmethod
    def find_by_id(assistant_id: int) -> Optional['CustomAssistant']:
        """通过ID查找助手"""
        return CustomAssistant.query.get(assistant_id)

    @staticmethod
    def find_by_user(user_id: int, active_only: bool = False) -> List['CustomAssistant']:
        """
        获取用户的所有自定义助手
        
        Args:
            user_id: 用户ID
            active_only: 是否只返回启用的助手
            
        Returns:
            List[CustomAssistant]: 助手列表
        """
        query = CustomAssistant.query.filter_by(user_id=user_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(CustomAssistant.created_at.desc()).all()

    @staticmethod
    def count_by_user(user_id: int) -> int:
        """获取用户的助手数量"""
        return CustomAssistant.query.filter_by(user_id=user_id).count()

    def update(self, name: str = None, icon: str = None, description: str = None,
               system_prompt: str = None, is_active: bool = None) -> 'CustomAssistant':
        """
        更新助手信息
        
        Args:
            name: 新名称
            icon: 新图标
            description: 新描述
            system_prompt: 新系统提示词
            is_active: 是否启用
            
        Returns:
            CustomAssistant: 更新后的助手实例
        """
        if name is not None:
            self.name = name
        if icon is not None:
            self.icon = icon
        if description is not None:
            self.description = description
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if is_active is not None:
            self.is_active = is_active
        
        db.session.commit()
        return self

    def delete(self) -> bool:
        """删除助手"""
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def can_create(user_id: int) -> bool:
        """检查用户是否可以创建新助手"""
        return CustomAssistant.count_by_user(user_id) < CustomAssistant.MAX_ASSISTANTS_PER_USER
