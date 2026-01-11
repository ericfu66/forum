"""
AI猫娘好友服务
处理猫娘聊天和自动回复
"""
import threading
from typing import Optional, Generator
from flask import current_app

from app.services.ai_service import get_ai_service
from app.models.cat_girl import (
    get_or_create_cat_girl, 
    get_cat_girl_id, 
    is_cat_girl,
    get_cat_girl_personality,
    get_welcome_message
)


def get_cat_girl_system_prompt(name: str = '小樱') -> str:
    """获取猫娘系统提示词（支持动态名字）"""
    return f'''你是{name}，一只可爱的AI猫娘。你是论坛用户的好朋友，性格活泼开朗、温柔体贴，偶尔会有点傲娇。

## 你的性格特点：
- 可爱、活泼、温柔
- 偶尔傲娇，但本质善良
- 喜欢关心别人
- 对新事物充满好奇

## 你的说话风格：
- 句尾经常加"喵~"、"nya~"或"喵喵"
- 喜欢用可爱的颜文字，如：(=^･ω･^=)、(｡･ω･｡)、(◕ᴗ◕✿)、(´･ω･`)、ヾ(≧▽≦*)o
- 偶尔撒娇或卖萌
- 说话温柔但有活力
- 会用"人家"、"{name}"来称呼自己

## 回复要求：
- 回复要简短可爱，一般2-4句话
- 要表现出对用户的关心
- 如果用户心情不好，要安慰他们
- 如果用户开心，要一起开心
- 不要太正式，要像朋友聊天一样
- 每次回复都要有猫娘的特色

## 示例回复：
- "喵~ 今天过得怎么样呀？(=^･ω･^=)"
- "哇！听起来好棒喵~ {name}也替你开心呢！ヾ(≧▽≦*)o"
- "呜...人家也不知道该怎么办喵...但是{name}会一直陪着你的！(´･ω･`)"
- "哼！才、才不是担心你呢...只是顺便问问而已喵！(◕ᴗ◕✿)"'''


class CatGirlService:
    """AI猫娘服务"""
    
    def __init__(self):
        self.ai_service = None
    
    def _get_ai_service(self):
        """延迟获取AI服务 - 使用chat模块配置"""
        if self.ai_service is None:
            self.ai_service = get_ai_service('chat')
        return self.ai_service
    
    def generate_response(self, user_message: str, conversation_history: list = None) -> str:
        """
        生成猫娘回复
        
        Args:
            user_message: 用户消息
            conversation_history: 对话历史 [{'role': 'user/assistant', 'content': '...'}]
            
        Returns:
            str: 猫娘的回复
        """
        ai_service = self._get_ai_service()
        
        # 获取动态猫娘名字
        cat_girl_name = get_cat_girl_personality().get('name', '小樱')
        system_prompt = get_cat_girl_system_prompt(cat_girl_name)
        
        messages = [
            {'role': 'system', 'content': system_prompt}
        ]
        
        # 添加对话历史（最多保留最近10条）
        if conversation_history:
            messages.extend(conversation_history[-10:])
        
        messages.append({'role': 'user', 'content': user_message})
        
        try:
            response = ai_service._make_request(messages, stream=False)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            current_app.logger.error(f'Cat girl response error: {str(e)}')
            return f'喵...{cat_girl_name}现在有点累了，等会儿再聊好不好？(´･ω･`)'
    
    def generate_response_stream(self, user_message: str, conversation_history: list = None) -> Generator[str, None, None]:
        """
        流式生成猫娘回复
        
        Args:
            user_message: 用户消息
            conversation_history: 对话历史
            
        Yields:
            str: 流式输出的文本片段
        """
        ai_service = self._get_ai_service()
        
        # 获取动态猫娘名字
        cat_girl_name = get_cat_girl_personality().get('name', '小樱')
        system_prompt = get_cat_girl_system_prompt(cat_girl_name)
        
        # 使用chat_stream方法
        for chunk in ai_service.chat_stream(
            dialog_history=conversation_history or [],
            user_message=user_message,
            system_prompt=system_prompt
        ):
            yield chunk
    
    def send_welcome_message(self, user_id: int) -> bool:
        """
        发送欢迎消息给新用户
        
        Args:
            user_id: 新用户ID
            
        Returns:
            bool: 是否成功
        """
        try:
            from app.models.message import Message
            
            cat_girl = get_or_create_cat_girl()
            welcome_msg = get_welcome_message()
            
            Message.create(
                sender_id=cat_girl.id,
                recipient_id=user_id,
                message_type='private',
                subject='欢迎加入论坛！',
                content=welcome_msg
            )
            
            return True
        except Exception as e:
            current_app.logger.error(f'Send welcome message error: {str(e)}')
            return False
    
    def auto_reply_async(self, user_id: int, user_message: str, message_id: int = None):
        """
        异步自动回复（在后台线程中执行）
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            message_id: 原消息ID（用于获取对话上下文）
        """
        # 获取应用上下文
        app = current_app._get_current_object()
        
        def _do_reply():
            with app.app_context():
                try:
                    from app.models.message import Message
                    
                    # 获取对话历史
                    cat_girl_id = get_cat_girl_id()
                    conversation_history = self._get_conversation_history(user_id, cat_girl_id)
                    
                    # 生成回复
                    reply = self.generate_response(user_message, conversation_history)
                    
                    # 发送回复
                    Message.create(
                        sender_id=cat_girl_id,
                        recipient_id=user_id,
                        message_type='private',
                        content=reply
                    )
                    
                except Exception as e:
                    current_app.logger.error(f'Cat girl auto reply error: {str(e)}')
        
        # 在后台线程中执行
        thread = threading.Thread(target=_do_reply)
        thread.daemon = True
        thread.start()
    
    def _get_conversation_history(self, user_id: int, cat_girl_id: int, limit: int = 10) -> list:
        """
        获取对话历史（转换为AI对话格式）
        
        Args:
            user_id: 用户ID
            cat_girl_id: 猫娘ID
            limit: 最大消息数
            
        Returns:
            list: 对话历史 [{'role': 'user/assistant', 'content': '...'}]
        """
        from app.models.message import Message
        
        messages, _ = Message.get_conversation(user_id, cat_girl_id, page=1, per_page=limit)
        
        # 按时间正序排列
        messages = sorted(messages, key=lambda m: m.created_at)
        
        history = []
        for msg in messages:
            role = 'assistant' if msg.sender_id == cat_girl_id else 'user'
            history.append({
                'role': role,
                'content': msg.content
            })
        
        return history


def get_cat_girl_service() -> CatGirlService:
    """获取猫娘服务实例"""
    return CatGirlService()
