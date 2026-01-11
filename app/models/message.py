"""
消息模型
支持私信和系统通知
"""
from app.extensions import db
from datetime import datetime
from typing import List, Optional, Tuple


class Message(db.Model):
    """消息模型 - 支持私信和系统通知"""
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # 系统通知为None
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message_type = db.Column(db.String(20), nullable=False, default='private')  # 'private', 'system', 'moderation'
    subject = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_deleted_by_sender = db.Column(db.Boolean, default=False)
    is_deleted_by_recipient = db.Column(db.Boolean, default=False)
    related_content_type = db.Column(db.String(20), nullable=True)  # 'post', 'comment'
    related_content_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

    # 索引
    __table_args__ = (
        db.Index('idx_messages_recipient_read', 'recipient_id', 'is_read'),
        db.Index('idx_messages_sender_recipient', 'sender_id', 'recipient_id'),
        db.Index('idx_messages_created_at', 'created_at'),
    )

    def to_dict(self, include_sender=False, include_recipient=False) -> dict:
        """转换为字典"""
        result = {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'message_type': self.message_type,
            'subject': self.subject,
            'content': self.content,
            'is_read': self.is_read,
            'related_content_type': self.related_content_type,
            'related_content_id': self.related_content_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if include_sender and self.sender:
            result['sender'] = {
                'id': self.sender.id,
                'username': self.sender.username,
                'avatar': self.sender.avatar
            }
        elif self.sender_id is None:
            result['sender'] = {
                'id': None,
                'username': '系统',
                'avatar': None
            }

        if include_recipient and self.recipient:
            result['recipient'] = {
                'id': self.recipient.id,
                'username': self.recipient.username,
                'avatar': self.recipient.avatar
            }

        return result

    @staticmethod
    def create(recipient_id: int, content: str, message_type: str = 'private',
               sender_id: int = None, subject: str = None,
               related_content_type: str = None, related_content_id: int = None) -> 'Message':
        """创建消息"""
        message = Message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            subject=subject,
            content=content,
            related_content_type=related_content_type,
            related_content_id=related_content_id
        )
        db.session.add(message)
        db.session.commit()
        return message

    @staticmethod
    def get_by_id(message_id: int) -> Optional['Message']:
        """通过ID获取消息"""
        return Message.query.get(message_id)

    @staticmethod
    def get_inbox(user_id: int, page: int = 1, per_page: int = 20,
                  message_type: str = None) -> Tuple[List['Message'], int]:
        """获取用户收件箱"""
        query = Message.query.filter(
            Message.recipient_id == user_id,
            Message.is_deleted_by_recipient == False
        )

        if message_type:
            query = query.filter(Message.message_type == message_type)

        query = query.order_by(Message.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    @staticmethod
    def get_conversation(user_id: int, other_user_id: int,
                        page: int = 1, per_page: int = 50) -> Tuple[List['Message'], int]:
        """获取与某用户的对话"""
        query = Message.query.filter(
            Message.message_type == 'private',
            db.or_(
                db.and_(
                    Message.sender_id == user_id,
                    Message.recipient_id == other_user_id,
                    Message.is_deleted_by_sender == False
                ),
                db.and_(
                    Message.sender_id == other_user_id,
                    Message.recipient_id == user_id,
                    Message.is_deleted_by_recipient == False
                )
            )
        )

        query = query.order_by(Message.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """获取未读消息数量"""
        return Message.query.filter(
            Message.recipient_id == user_id,
            Message.is_read == False,
            Message.is_deleted_by_recipient == False
        ).count()

    def mark_as_read(self) -> bool:
        """标记为已读"""
        if not self.is_read:
            self.is_read = True
            db.session.commit()
        return True

    def delete_by_user(self, user_id: int) -> bool:
        """用户删除消息（软删除）"""
        if self.sender_id == user_id:
            self.is_deleted_by_sender = True
        if self.recipient_id == user_id:
            self.is_deleted_by_recipient = True
        db.session.commit()
        return True

    @staticmethod
    def get_conversation_list(user_id: int, page: int = 1, per_page: int = 20) -> Tuple[List[dict], int]:
        """获取对话列表（每个对话只显示最新一条）"""
        # 子查询：获取每个对话的最新消息ID
        from sqlalchemy import func, case
        
        # 获取所有与当前用户相关的私信
        subquery = db.session.query(
            func.max(Message.id).label('max_id'),
            case(
                (Message.sender_id == user_id, Message.recipient_id),
                else_=Message.sender_id
            ).label('other_user_id')
        ).filter(
            Message.message_type == 'private',
            db.or_(
                db.and_(Message.sender_id == user_id, Message.is_deleted_by_sender == False),
                db.and_(Message.recipient_id == user_id, Message.is_deleted_by_recipient == False)
            )
        ).group_by('other_user_id').subquery()

        # 获取这些最新消息
        query = Message.query.join(
            subquery, Message.id == subquery.c.max_id
        ).order_by(Message.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        result = []
        for msg in pagination.items:
            other_user_id = msg.recipient_id if msg.sender_id == user_id else msg.sender_id
            from app.models.user import User
            other_user = User.query.get(other_user_id)
            
            # 获取未读数量
            unread = Message.query.filter(
                Message.sender_id == other_user_id,
                Message.recipient_id == user_id,
                Message.is_read == False,
                Message.is_deleted_by_recipient == False
            ).count()
            
            result.append({
                'user': other_user.to_dict() if other_user else None,
                'last_message': msg.content,
                'last_message_time': msg.created_at.isoformat() if msg.created_at else None,
                'unread_count': unread
            })
        
        return result, pagination.total
