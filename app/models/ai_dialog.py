from app.extensions import db
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
        """获取用于API调用的消息格式，支持摘要消息"""
        result = []
        for m in (self.messages or []):
            if m.get('is_summary'):
                result.append({'role': 'system', 'content': m['content']})
            else:
                result.append({'role': m['role'], 'content': m['content']})
        return result

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

    def summarize_dialog(self, threshold=None):
        """
        自动摘要旧消息
        当消息数超过阈值时，将旧消息压缩为摘要

        Args:
            threshold: 消息数阈值，默认从配置读取

        Returns:
            bool: 是否执行了摘要
        """
        from flask import current_app

        if threshold is None:
            threshold = current_app.config.get('DIALOG_SUMMARY_THRESHOLD', 30)

        messages = self.messages or []
        if len(messages) < threshold:
            return False

        keep_recent = 10
        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # 跳过已有的摘要消息
        old_messages = [m for m in old_messages if not m.get('is_summary')]
        if not old_messages:
            return False

        # 构建摘要提示
        conversation_text = ""
        for m in old_messages:
            role = "用户" if m['role'] == 'user' else "AI"
            content = m.get('content', '')[:200]
            conversation_text += f"{role}: {content}\n"

        try:
            from app.services.ai_service import get_ai_service
            ai = get_ai_service('write')
            summary = ai.generate_simple(
                f"请用中文简要总结以下对话的要点（不超过200字，直接输出总结内容）：\n\n{conversation_text}"
            )

            if not summary:
                return False

            summary_msg = {
                'role': 'system',
                'content': f'[对话历史摘要] {summary}',
                'timestamp': datetime.utcnow().isoformat(),
                'is_summary': True
            }

            self.messages = [summary_msg] + recent_messages
            self.updated_at = datetime.utcnow()
            flag_modified(self, 'messages')
            db.session.commit()

            logger.info(f'Dialog {self.id} summarized: {len(old_messages)} messages compressed')
            return True

        except Exception as e:
            logger.error(f'Dialog summarization failed for dialog {self.id}: {e}')
            return False
