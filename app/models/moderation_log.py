"""
AI内容审核日志模型
记录所有AI审核决策，用于审计和人工复核
"""
from app.extensions import db
from datetime import datetime
from typing import List, Optional


class ModerationLog(db.Model):
    """AI审核日志模型"""
    __tablename__ = 'moderation_logs'

    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(20), nullable=False)  # 'post', 'comment'
    content_id = db.Column(db.Integer, nullable=False)
    content_preview = db.Column(db.Text)  # 内容预览（前200字）
    
    # AI审核结果
    ai_action = db.Column(db.String(20), nullable=False)  # 'approve', 'hold', 'reject'
    ai_confidence = db.Column(db.Float, nullable=False)
    ai_reasons = db.Column(db.JSON)  # 审核原因列表
    ai_categories = db.Column(db.JSON)  # 触发的规则类别 ['spam', 'inappropriate', 'sensitive']
    
    # 人工审核
    final_action = db.Column(db.String(20))  # 最终处理结果
    moderator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    moderator_note = db.Column(db.Text)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    
    # 关联
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # 关系
    author = db.relationship('User', foreign_keys=[author_id], backref='moderation_logs')
    moderator = db.relationship('User', foreign_keys=[moderator_id])

    def to_dict(self, include_author=False) -> dict:
        """转换为字典"""
        result = {
            'id': self.id,
            'content_type': self.content_type,
            'content_id': self.content_id,
            'content_preview': self.content_preview,
            'ai_action': self.ai_action,
            'ai_confidence': self.ai_confidence,
            'ai_reasons': self.ai_reasons or [],
            'ai_categories': self.ai_categories or [],
            'final_action': self.final_action,
            'moderator_id': self.moderator_id,
            'moderator_note': self.moderator_note,
            'author_id': self.author_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
        }
        
        if include_author and self.author:
            result['author'] = {
                'id': self.author.id,
                'username': self.author.username,
                'avatar': self.author.avatar
            }
        
        return result

    @staticmethod
    def create(content_type: str, content_id: int, content_preview: str,
               ai_action: str, ai_confidence: float, ai_reasons: List[str],
               ai_categories: List[str], author_id: int = None,
               final_action: str = None) -> 'ModerationLog':
        """创建审核日志"""
        log = ModerationLog(
            content_type=content_type,
            content_id=content_id,
            content_preview=content_preview[:200] if content_preview else '',
            ai_action=ai_action,
            ai_confidence=ai_confidence,
            ai_reasons=ai_reasons,
            ai_categories=ai_categories,
            author_id=author_id,
            final_action=final_action if final_action else (ai_action if ai_action != 'hold' else None)
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
    def get_pending(page: int = 1, per_page: int = 20) -> tuple:
        """获取待审核队列"""
        query = ModerationLog.query.filter_by(ai_action='hold', final_action=None)
        query = query.order_by(ModerationLog.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    @staticmethod
    def get_by_content(content_type: str, content_id: int) -> Optional['ModerationLog']:
        """根据内容获取审核日志"""
        return ModerationLog.query.filter_by(
            content_type=content_type,
            content_id=content_id
        ).order_by(ModerationLog.created_at.desc()).first()

    @staticmethod
    def get_recent(limit: int = 50) -> List['ModerationLog']:
        """获取最近的审核日志"""
        return ModerationLog.query.order_by(
            ModerationLog.created_at.desc()
        ).limit(limit).all()

    def approve(self, moderator_id: int, note: str = '') -> bool:
        """人工批准"""
        self.final_action = 'approve'
        self.moderator_id = moderator_id
        self.moderator_note = note
        self.reviewed_at = datetime.utcnow()
        db.session.commit()
        return True

    def reject(self, moderator_id: int, note: str = '') -> bool:
        """人工拒绝"""
        self.final_action = 'reject'
        self.moderator_id = moderator_id
        self.moderator_note = note
        self.reviewed_at = datetime.utcnow()
        db.session.commit()
        return True
