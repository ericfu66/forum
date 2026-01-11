"""
消息服务
处理私信、系统通知和AI帮回消息功能
"""
from typing import List, Tuple, Optional
from flask import current_app

from app.models.message import Message
from app.models.user import User
from app.extensions import db


# 消息长度限制
MAX_MESSAGE_LENGTH = 2000


class MessageService:
    """消息服务"""
    
    def send_private_message(self, sender_id: int, recipient_id: int, 
                            content: str, subject: str = None) -> Tuple[bool, str, Optional[Message]]:
        """
        发送私信
        
        Args:
            sender_id: 发送者ID
            recipient_id: 接收者ID
            content: 消息内容
            subject: 主题（可选）
            
        Returns:
            (success, message, Message对象)
        """
        # 验证内容
        validation_result = self._validate_content(content)
        if not validation_result[0]:
            return validation_result[0], validation_result[1], None
        
        # 不能给自己发消息
        if sender_id == recipient_id:
            return False, '不能给自己发送消息', None
        
        # 检查接收者是否存在
        recipient = User.query.get(recipient_id)
        if not recipient:
            return False, '用户不存在', None
        
        try:
            message = Message.create(
                sender_id=sender_id,
                recipient_id=recipient_id,
                message_type='private',
                subject=subject,
                content=content
            )
            
            # 检查是否发送给猫娘，如果是则触发自动回复
            self._check_cat_girl_auto_reply(sender_id, recipient_id, content)
            
            return True, '消息发送成功', message
        except Exception as e:
            current_app.logger.error(f'Send message error: {str(e)}')
            return False, '消息发送失败', None
    
    def send_system_notification(self, recipient_id: int, content: str,
                                 subject: str = None, related_type: str = None,
                                 related_id: int = None) -> Tuple[bool, str, Optional[Message]]:
        """
        发送系统通知
        
        Args:
            recipient_id: 接收者ID
            content: 通知内容
            subject: 主题
            related_type: 关联内容类型
            related_id: 关联内容ID
            
        Returns:
            (success, message, Message对象)
        """
        try:
            message = Message.create(
                sender_id=None,  # 系统通知没有发送者
                recipient_id=recipient_id,
                message_type='system',
                subject=subject,
                content=content,
                related_content_type=related_type,
                related_content_id=related_id
            )
            return True, '通知发送成功', message
        except Exception as e:
            current_app.logger.error(f'Send notification error: {str(e)}')
            return False, '通知发送失败', None
    
    def send_moderation_notification(self, recipient_id: int, content: str,
                                     subject: str, content_type: str,
                                     content_id: int) -> Tuple[bool, str, Optional[Message]]:
        """
        发送审核通知
        
        Args:
            recipient_id: 接收者ID
            content: 通知内容
            subject: 主题
            content_type: 被审核内容类型
            content_id: 被审核内容ID
            
        Returns:
            (success, message, Message对象)
        """
        try:
            message = Message.create(
                sender_id=None,
                recipient_id=recipient_id,
                message_type='moderation',
                subject=subject,
                content=content,
                related_content_type=content_type,
                related_content_id=content_id
            )
            return True, '审核通知发送成功', message
        except Exception as e:
            current_app.logger.error(f'Send moderation notification error: {str(e)}')
            return False, '审核通知发送失败', None
    
    def get_inbox(self, user_id: int, page: int = 1, per_page: int = 20,
                  message_type: str = None) -> Tuple[List[dict], int]:
        """
        获取收件箱
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            message_type: 消息类型过滤
            
        Returns:
            (消息列表, 总数)
        """
        messages, total = Message.get_inbox(user_id, page, per_page, message_type)
        return [msg.to_dict(include_sender=True) for msg in messages], total
    
    def get_conversation(self, user_id: int, other_user_id: int,
                        page: int = 1, per_page: int = 50) -> Tuple[List[dict], int]:
        """
        获取与某用户的对话
        
        Args:
            user_id: 当前用户ID
            other_user_id: 对方用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            (消息列表, 总数)
        """
        messages, total = Message.get_conversation(user_id, other_user_id, page, per_page)
        return [msg.to_dict(include_sender=True, include_recipient=True) for msg in messages], total
    
    def get_conversation_list(self, user_id: int, page: int = 1, 
                              per_page: int = 20) -> Tuple[List[dict], int]:
        """
        获取对话列表
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            (对话列表, 总数)
        """
        return Message.get_conversation_list(user_id, page, per_page)
    
    def get_unread_count(self, user_id: int) -> int:
        """获取未读消息数量"""
        return Message.get_unread_count(user_id)
    
    def mark_as_read(self, message_id: int, user_id: int) -> Tuple[bool, str]:
        """
        标记消息为已读
        
        Args:
            message_id: 消息ID
            user_id: 用户ID（验证权限）
            
        Returns:
            (success, message)
        """
        message = Message.get_by_id(message_id)
        if not message:
            return False, '消息不存在'
        
        if message.recipient_id != user_id:
            return False, '无权操作此消息'
        
        message.mark_as_read()
        return True, '已标记为已读'
    
    def mark_conversation_as_read(self, user_id: int, other_user_id: int) -> int:
        """
        标记与某用户的所有对话为已读
        
        Args:
            user_id: 当前用户ID
            other_user_id: 对方用户ID
            
        Returns:
            标记的消息数量
        """
        count = Message.query.filter(
            Message.sender_id == other_user_id,
            Message.recipient_id == user_id,
            Message.is_read == False
        ).update({'is_read': True})
        db.session.commit()
        return count
    
    def delete_message(self, message_id: int, user_id: int) -> Tuple[bool, str]:
        """
        删除消息（软删除）
        
        Args:
            message_id: 消息ID
            user_id: 用户ID
            
        Returns:
            (success, message)
        """
        message = Message.get_by_id(message_id)
        if not message:
            return False, '消息不存在'
        
        if message.sender_id != user_id and message.recipient_id != user_id:
            return False, '无权操作此消息'
        
        message.delete_by_user(user_id)
        return True, '消息已删除'
    
    def _validate_content(self, content: str) -> Tuple[bool, str]:
        """验证消息内容"""
        if not content or not content.strip():
            return False, '消息内容不能为空'
        
        if len(content) > MAX_MESSAGE_LENGTH:
            return False, f'消息内容超过{MAX_MESSAGE_LENGTH}字符限制'
        
        return True, ''
    
    def _check_cat_girl_auto_reply(self, sender_id: int, recipient_id: int, content: str):
        """检查是否需要猫娘自动回复"""
        try:
            from app.models.cat_girl import is_cat_girl
            
            if is_cat_girl(recipient_id):
                from app.services.cat_girl_service import get_cat_girl_service
                cat_girl_service = get_cat_girl_service()
                cat_girl_service.auto_reply_async(sender_id, content)
        except Exception as e:
            current_app.logger.error(f'Cat girl auto reply check error: {str(e)}')
    
    def generate_ai_reply(self, user_id: int, other_user_id: int, 
                         style: str = 'friendly') -> Tuple[bool, str, str]:
        """
        生成AI回复建议
        
        Args:
            user_id: 当前用户ID
            other_user_id: 对方用户ID
            style: 回复风格 ('formal', 'friendly', 'brief')
            
        Returns:
            (success, message, 生成的回复)
        """
        try:
            from app.services.ai_service import get_ai_service
            
            # 获取最近的对话上下文
            messages, _ = Message.get_conversation(user_id, other_user_id, page=1, per_page=10)
            
            if not messages:
                return False, '没有对话记录', ''
            
            # 构建上下文
            context = self._build_conversation_context(messages, user_id)
            
            # 获取最后一条收到的消息
            last_received = None
            for msg in messages:
                if msg.sender_id == other_user_id:
                    last_received = msg
                    break
            
            if not last_received:
                return False, '没有收到对方的消息', ''
            
            # 生成回复 - 使用chat模块配置
            ai_service = get_ai_service('chat')
            
            style_prompts = {
                'formal': '请用正式、专业的语气回复，适合工作或正式场合。',
                'friendly': '请用友好、轻松的语气回复，像朋友之间的日常聊天。',
                'brief': '请用简短、直接的语气回复，言简意赅。'
            }
            
            prompt = f'''你是一个帮助用户回复私信的助手。请根据对话上下文，帮用户生成一条合适的回复。

{style_prompts.get(style, style_prompts['friendly'])}

对话上下文：
{context}

对方最新消息：{last_received.content}

请直接输出回复内容，不要有任何前缀或解释。回复应该自然、得体，长度适中（1-3句话）。'''

            reply = ai_service.generate_simple(prompt)
            
            return True, '回复生成成功', reply.strip()
            
        except Exception as e:
            current_app.logger.error(f'Generate AI reply error: {str(e)}')
            return False, 'AI回复生成失败', ''
    
    def _build_conversation_context(self, messages: List[Message], user_id: int) -> str:
        """构建对话上下文字符串"""
        # 按时间正序排列
        sorted_messages = sorted(messages, key=lambda m: m.created_at)
        
        context_lines = []
        for msg in sorted_messages[-5:]:  # 只取最近5条
            role = '我' if msg.sender_id == user_id else '对方'
            context_lines.append(f'{role}: {msg.content}')
        
        return '\n'.join(context_lines)


def get_message_service() -> MessageService:
    """获取消息服务实例"""
    return MessageService()
