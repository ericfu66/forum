"""
配置变更历史模型
"""
from datetime import datetime
from app.extensions import db


class ConfigHistory(db.Model):
    """配置变更历史"""
    __tablename__ = 'config_history'

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # 'flask', 'deepseek', 'ai_features', etc.
    changes = db.Column(db.JSON, nullable=False)  # {'key': 'value', ...}
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    user = db.relationship('User', backref='config_changes')

    def to_dict(self):
        return {
            'id': self.id,
            'category': self.category,
            'changes': self.changes,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def create(cls, category, changes, updated_by=None):
        """创建配置变更记录"""
        history = cls(
            category=category,
            changes=changes,
            updated_by=updated_by
        )
        db.session.add(history)
        db.session.commit()
        return history

    @classmethod
    def get_recent(cls, limit=50):
        """获取最近的配置变更历史"""
        return cls.query.order_by(cls.updated_at.desc()).limit(limit).all()
