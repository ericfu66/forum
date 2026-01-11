from app.extensions import db
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime


class AIDialog(db.Model):
    """AI对话模型"""
    __tablename__ = 'ai_dialogs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), default='新对话')
    model = db.Column(db.String(50), default='deepseek-chat')
    messages = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'messages': self.messages or [],
            'model': self.model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def create(user_id, title='', model='deepseek-chat'):
        """创建新对话"""
        dialog = AIDialog(
            user_id=user_id,
            title=title or '新对话',
            model=model
        )
        db.session.add(dialog)
        db.session.commit()
        return dialog

    @staticmethod
    def find_by_id(dialog_id):
        """通过ID查找对话"""
        return AIDialog.query.get(dialog_id)

    @staticmethod
    def find_by_user(user_id, page=1, per_page=20):
        """获取用户的对话列表"""
        pagination = AIDialog.query.filter_by(user_id=user_id)\
            .order_by(AIDialog.updated_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    def add_message(self, role, content):
        """添加消息"""
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        }
        # 创建新列表以确保SQLAlchemy检测到变化
        if self.messages is None:
            self.messages = []
        new_messages = list(self.messages)
        new_messages.append(message)
        self.messages = new_messages
        self.updated_at = datetime.utcnow()

        # 更新标题（使用第一条用户消息）
        if role == 'user' and (not self.title or self.title == '新对话'):
            self.title = content[:30] + ('...' if len(content) > 30 else '')

        # 显式标记JSON字段已修改
        flag_modified(self, 'messages')
        db.session.commit()

    def get_messages_for_api(self):
        """获取用于API调用的消息格式"""
        return [{'role': m['role'], 'content': m['content']} for m in (self.messages or [])]

    def remove_last_assistant_message(self):
        """删除最后一条AI助手消息（用于重新生成）"""
        if not self.messages:
            return False
        
        # 从后往前找到最后一条assistant消息并删除
        new_messages = list(self.messages)
        for i in range(len(new_messages) - 1, -1, -1):
            if new_messages[i].get('role') == 'assistant':
                new_messages.pop(i)
                self.messages = new_messages
                self.updated_at = datetime.utcnow()
                flag_modified(self, 'messages')
                db.session.commit()
                return True
        return False
