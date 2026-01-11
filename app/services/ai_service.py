"""
AI服务 - 支持OpenAI通用协议
支持：AI吐槽、AI对话、AI写稿
"""
import requests
import os
import json
import time
from typing import Generator, Optional, Dict, Any
from flask import current_app


# 预设写作风格
WRITING_STYLES = {
    'formal': '正式严谨，用词规范，结构清晰',
    'casual': '轻松随意，口语化表达，亲切自然',
    'humorous': '幽默风趣，适当使用比喻和调侃',
    'academic': '学术严谨，引用规范，论证充分',
    'news': '新闻报道风格，客观简洁，倒金字塔结构'
}

# 预设写作语气
WRITING_TONES = {
    'professional': '专业权威，展现专业素养',
    'friendly': '友好亲切，拉近与读者距离',
    'serious': '严肃认真，强调重要性',
    'enthusiastic': '热情洋溢，充满感染力',
    'objective': '客观中立，不带个人情感'
}

# 字数限制常量
WORD_COUNT_MIN = 100
WORD_COUNT_MAX = 5000


def validate_word_count(word_count: int) -> tuple:
    """
    验证字数参数
    
    Args:
        word_count: 字数值
        
    Returns:
        (valid, message): 是否有效及错误信息
    """
    if word_count is None:
        return True, ''
    
    try:
        word_count = int(word_count)
    except (TypeError, ValueError):
        return False, '字数必须是整数'
    
    if word_count < WORD_COUNT_MIN:
        return False, f'字数不能少于{WORD_COUNT_MIN}字'
    if word_count > WORD_COUNT_MAX:
        return False, f'字数不能超过{WORD_COUNT_MAX}字'
    
    return True, ''


class AIService:
    """通用AI服务 - 支持OpenAI协议"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化AI服务
        
        Args:
            config: 配置字典，包含api_base, api_key, model, max_tokens, temperature
                   如果为None，则从Flask配置中读取（兼容旧代码）
        """
        if config:
            self.api_key = config.get('api_key', '')
            self.api_base = config.get('api_base', 'https://api.openai.com/v1').rstrip('/')
            self.model = config.get('model', 'gpt-4')
            self.max_tokens = config.get('max_tokens', 2000)
            self.temperature = config.get('temperature', 0.7)
        else:
            # 兼容旧代码：从Flask配置读取
            self.api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
            self.api_base = current_app.config.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com').rstrip('/')
            self.model = current_app.config.get('DEEPSEEK_MODEL', 'deepseek-chat')
            self.max_tokens = current_app.config.get('DEEPSEEK_MAX_TOKENS', 2000)
            self.temperature = current_app.config.get('DEEPSEEK_TEMPERATURE', 0.7)

    def _make_request(self, messages: list, stream: bool = False, **kwargs):
        """发起API请求（支持OpenAI通用协议）"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"AI Request: api_base={self.api_base}, model={self.model}")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        # 构建请求payload
        payload = {
            'model': self.model,
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
            'temperature': kwargs.get('temperature', self.temperature),
            'stream': stream
        }
        
        # 添加额外参数
        for key in ['top_p', 'frequency_penalty', 'presence_penalty', 'stop']:
            if key in kwargs:
                payload[key] = kwargs[key]

        response = requests.post(
            f'{self.api_base}/chat/completions',
            headers=headers,
            json=payload,
            stream=stream,
            timeout=kwargs.get('timeout', 60)
        )

        return response

    def generate_roast(self, post_content: str, post_title: str = '') -> str:
        """
        生成AI吐槽回复
        """
        system_prompt = current_app.config.get('AI_ROAST_SYSTEM_PROMPT',
            '你是一个幽默风趣的AI评论员，喜欢吐槽但保持友善。你的吐槽应该有趣但不冒犯他人。')

        user_prompt = f'请对这个帖子进行幽默吐槽（1-2句话）：\n'
        if post_title:
            user_prompt += f'标题：{post_title}\n'
        user_prompt += f'内容：{post_content}'

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

        try:
            response = self._make_request(messages, stream=False)
            response.raise_for_status()
            result = response.json()

            return result['choices'][0]['message']['content']
        except requests.RequestException as e:
            current_app.logger.error(f'AI roast error: {str(e)}')
            return '抱歉，AI吐槽功能暂时不可用。'

    def chat_stream(self, dialog_history: list, user_message: str, system_prompt: str = None) -> Generator[str, None, None]:
        """
        流式AI对话

        Args:
            dialog_history: 对话历史列表 [{'role': 'user/assistant', 'content': '...'}]
            user_message: 用户新消息
            system_prompt: 自定义系统提示词（可选，用于不同助手角色）

        Yields:
            str: 流式输出的文本片段
        """
        if not system_prompt:
            system_prompt = current_app.config.get('AI_CHAT_SYSTEM_PROMPT',
                '你是一个乐于助人的AI助手，能够回答各种问题并提供有用的建议。')

        messages = [
            {'role': 'system', 'content': system_prompt}
        ] + dialog_history + [
            {'role': 'user', 'content': user_message}
        ]

        try:
            response = self._make_request(messages, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            # 安全检查：确保 choices 存在且不为空
                            choices = chunk.get('choices', [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except requests.RequestException as e:
            current_app.logger.error(f'AI chat error: {str(e)}')
            yield '抱歉，AI回复出现问题。'

    def _build_article_messages(self, topic: str, keywords: list = None, 
                                 length: str = 'medium', style: str = None,
                                 tone: str = None, word_count: int = None) -> list:
        """
        构建写稿的消息列表
        
        Args:
            topic: 文章主题/写作任务
            keywords: 关键词列表
            length: 文章长度 'short', 'medium', 'long'（当word_count未指定时使用）
            style: 写作风格 (formal, casual, humorous, academic, news, 或自定义)
            tone: 写作语气 (professional, friendly, serious, enthusiastic, objective, 或自定义)
            word_count: 精确字数（100-5000）
        """
        system_prompt = current_app.config.get('AI_WRITE_SYSTEM_PROMPT', '''你是一位专业的中文写作助手，能够撰写各类文体，包括但不限于：

**文章类**：议论文、说明文、记叙文、散文、评论、新闻稿、博客文章等
**应用文**：通知、公告、启事（寻物/招领/寻人）、书信（感谢信/道歉信/邀请函/推荐信/求职信）、申请书、建议书、倡议书、检讨书、保证书、请假条、借条、收据、合同、协议、计划、总结、报告、简历等
**创意写作**：故事、小说片段、诗歌、剧本、广告文案、宣传语等

## 智能识别与格式适配
请根据用户的写作需求，自动识别文体类型并采用相应的格式规范：

### 应用文格式要点
- **标题**：居中，简明扼要说明文种（如"寻物启事"、"检讨书"）
- **称谓**：根据文体需要，顶格写收文对象
- **正文**：条理清晰，要素完整（时间、地点、人物、事件等）
- **落款**：署名和日期，右下角对齐
- **特殊要素**：如联系方式、有效期限等按需添加

### 文章类格式要点
- 使用 `##` 作为主要章节标题，`###` 作为子标题
- 段落之间空一行，逻辑清晰
- 适当使用 **粗体**、*斜体*、列表、引用等增强可读性

## 内容要求
- 语言流畅自然，符合文体特点
- 内容真实可信，避免空洞套话
- 格式规范得体，符合实际使用场景''')

        # 添加风格和语气要求到系统提示词
        style_tone_requirements = []
        
        if style:
            style_desc = WRITING_STYLES.get(style, style)  # 如果是自定义风格，直接使用
            style_tone_requirements.append(f'**写作风格**：{style_desc}')
        
        if tone:
            tone_desc = WRITING_TONES.get(tone, tone)  # 如果是自定义语气，直接使用
            style_tone_requirements.append(f'**写作语气**：{tone_desc}')
        
        if style_tone_requirements:
            system_prompt += '\n\n## 风格语气要求\n' + '\n'.join(style_tone_requirements)

        # 确定字数要求
        if word_count and 100 <= word_count <= 5000:
            length_desc = f'约{word_count}字（允许±10%浮动，即{int(word_count*0.9)}-{int(word_count*1.1)}字）'
        else:
            length_guide = {
                'short': '300-500字',
                'medium': '800-1200字',
                'long': '1500-2000字'
            }
            length_desc = length_guide.get(length, "800-1200字")

        user_prompt = f'''请根据以下需求进行写作：

**写作任务**：{topic}
**目标字数**：{length_desc}'''

        if keywords:
            user_prompt += f'\n**关键词/要点**：{", ".join(keywords)}'

        user_prompt += '''

**注意事项**：
- 请直接输出内容，不要输出"好的"、"以下是..."等开场白
- 自动识别文体类型，采用相应的格式规范
- 如果是应用文，请确保格式完整规范（标题、称谓、正文、落款等）
- 如果是文章，请使用Markdown格式排版
- 确保内容原创、实用、符合实际场景'''

        return [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

    def generate_article(self, topic: str, keywords: list = None, length: str = 'medium',
                        style: str = None, tone: str = None, word_count: int = None) -> str:
        """
        AI写稿（非流式）

        Args:
            topic: 文章主题
            keywords: 关键词列表
            length: 文章长度 'short', 'medium', 'long'
            style: 写作风格
            tone: 写作语气
            word_count: 精确字数（100-5000）

        Returns:
            str: 生成的文章内容（Markdown格式）
        """
        messages = self._build_article_messages(topic, keywords, length, style, tone, word_count)

        try:
            response = self._make_request(messages, stream=False)
            response.raise_for_status()
            result = response.json()

            return result['choices'][0]['message']['content']
        except requests.RequestException as e:
            current_app.logger.error(f'AI write error: {str(e)}')
            return '# 生成失败\n\n抱歉，AI写稿功能暂时不可用。'

    def generate_article_stream(self, topic: str, keywords: list = None, length: str = 'medium',
                                style: str = None, tone: str = None, word_count: int = None) -> Generator[str, None, None]:
        """
        AI写稿（流式）

        Args:
            topic: 文章主题
            keywords: 关键词列表
            length: 文章长度 'short', 'medium', 'long'
            style: 写作风格
            tone: 写作语气
            word_count: 精确字数（100-5000）

        Yields:
            str: 流式输出的文本片段
        """
        messages = self._build_article_messages(topic, keywords, length, style, tone, word_count)

        try:
            response = self._make_request(messages, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            # 安全检查：确保 choices 存在且不为空
                            choices = chunk.get('choices', [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except requests.RequestException as e:
            current_app.logger.error(f'AI write stream error: {str(e)}')
            yield '# 生成失败\n\n抱歉，AI写稿功能暂时不可用。'

    def revise_article_stream(self, original_content: str, revision_request: str,
                              style: str = None, tone: str = None, word_count: int = None) -> Generator[str, None, None]:
        """
        AI修改文章（流式）

        Args:
            original_content: 原始文章内容
            revision_request: 修改要求
            style: 写作风格
            tone: 写作语气
            word_count: 精确字数（100-5000）

        Yields:
            str: 流式输出的文本片段
        """
        system_prompt = '''你是一位专业的中文写作助手，擅长根据用户的要求修改和优化文章。

## 修改原则
- 理解用户的修改要求，精准调整内容
- 保持原文的核心思想和主要信息
- 改进表达方式，提升文章质量
- 确保修改后的文章连贯流畅

## 输出要求
- 直接输出修改后的完整文章
- 不要输出"好的"、"以下是修改后的内容"等开场白
- 保持原有的格式规范（如果是应用文，保持应用文格式；如果是文章，使用Markdown格式）'''

        # 添加风格和语气要求
        style_tone_requirements = []
        
        if style:
            style_desc = WRITING_STYLES.get(style, style)
            style_tone_requirements.append(f'**写作风格**：{style_desc}')
        
        if tone:
            tone_desc = WRITING_TONES.get(tone, tone)
            style_tone_requirements.append(f'**写作语气**：{tone_desc}')
        
        if style_tone_requirements:
            system_prompt += '\n\n## 风格语气要求\n' + '\n'.join(style_tone_requirements)

        # 构建用户提示
        user_prompt = f'''请根据以下要求修改文章：

**原始内容**：
{original_content}

**修改要求**：
{revision_request}'''

        if word_count and 100 <= word_count <= 5000:
            user_prompt += f'\n**目标字数**：约{word_count}字（允许±10%浮动）'

        user_prompt += '''

**注意事项**：
- 直接输出修改后的完整文章
- 确保修改符合用户要求
- 保持文章的连贯性和可读性'''

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]

        try:
            response = self._make_request(messages, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            choices = chunk.get('choices', [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except requests.RequestException as e:
            current_app.logger.error(f'AI revise stream error: {str(e)}')
            yield '# 修改失败\n\n抱歉，AI修改功能暂时不可用。'

    def log_api_call(self, user_id: Optional[int], endpoint: str, tokens_used: int,
                     response_time: float, status: str = 'success', error_message: str = ''):
        """记录API调用日志"""
        from app.models.api_log import APILog

        APILog.create(
            user_id=user_id,
            endpoint=endpoint,
            model=self.model,
            tokens_used=tokens_used,
            response_time=response_time,
            status=status,
            error_message=error_message
        )

    def check_rate_limit(self, user_id: int) -> tuple[bool, str]:
        """
        检查用户速率限制

        Returns:
            (allowed, message): 是否允许调用及提示信息
        """
        from app.models.api_log import APILog

        # 检查每小时限制
        hour_count = APILog.count_by_user(user_id, 'hour')
        hourly_limit = current_app.config.get('AI_RATE_LIMIT_PER_HOUR', 20)
        if hour_count >= hourly_limit:
            return False, f'每小时调用次数已达上限（{hourly_limit}次），请稍后再试。'

        # 检查每日限制
        day_count = APILog.count_by_user(user_id, 'day')
        daily_limit = current_app.config.get('AI_RATE_LIMIT_PER_DAY', 100)
        if day_count >= daily_limit:
            return False, f'每日调用次数已达上限（{daily_limit}次），请明天再试。'

        return True, ''

    def generate_simple(self, prompt: str) -> str:
        """
        简单的AI生成（非流式，用于短内容）

        Args:
            prompt: 提示词

        Returns:
            str: 生成的内容
        """
        messages = [
            {'role': 'user', 'content': prompt}
        ]

        try:
            response = self._make_request(messages, stream=False)
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        except requests.RequestException as e:
            current_app.logger.error(f'AI simple generate error: {str(e)}')
            raise e

    def chat_with_knowledge(self, user_message: str, knowledge_context: str, dialog_history: list = None, system_prompt: str = None) -> Generator[str, None, None]:
        """
        基于知识库的AI对话（流式）

        Args:
            user_message: 用户消息
            knowledge_context: 相关帖子知识上下文
            dialog_history: 对话历史
            system_prompt: 自定义系统提示词

        Yields:
            str: 流式输出的文本片段
        """
        if not system_prompt:
            system_prompt = '''你是一个智能论坛助手，可以回答用户关于论坛帖子内容的问题。
你会根据提供的帖子知识库来回答问题。如果问题与知识库内容相关，请基于知识库内容回答。
如果问题与知识库内容无关，你也可以用自己的知识来回答。

回答时请注意：
1. 如果引用帖子内容，请说明来源
2. 保持友善和专业的语气
3. 回答要准确、有帮助'''

        # 构建包含知识上下文的系统消息
        full_system = system_prompt
        if knowledge_context:
            full_system += f'\n\n===== 相关帖子知识库 =====\n{knowledge_context}\n===== 知识库结束 ====='

        messages = [{'role': 'system', 'content': full_system}]

        if dialog_history:
            messages.extend(dialog_history)

        messages.append({'role': 'user', 'content': user_message})

        try:
            response = self._make_request(messages, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            # 安全检查：确保 choices 存在且不为空
                            choices = chunk.get('choices', [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

        except requests.RequestException as e:
            current_app.logger.error(f'AI knowledge chat error: {str(e)}')
            yield '抱歉，AI回复出现问题。'

    def chat_with_tools(self, user_message: str, dialog_history: list = None, 
                        system_prompt: str = None, enable_search: bool = True,
                        knowledge_context: str = '') -> Generator[str, None, None]:
        """
        支持Function Calling的AI对话（流式）
        AI可以自主决定是否需要搜索互联网

        Args:
            user_message: 用户消息
            dialog_history: 对话历史
            system_prompt: 自定义系统提示词
            enable_search: 是否启用搜索工具
            knowledge_context: 额外的知识上下文

        Yields:
            str: 流式输出的文本片段
        """
        from app.services.search_service import get_search_service
        
        if not system_prompt:
            system_prompt = '''你是一个智能AI助手，能够回答各种问题并提供有用的建议。
当用户询问需要最新信息、实时数据、新闻事件或你不确定的事实时，你可以使用搜索工具获取信息。

回答时请注意：
1. 如果使用了搜索结果，请适当引用来源
2. 保持友善和专业的语气
3. 回答要准确、有帮助'''

        # 添加知识上下文
        if knowledge_context:
            system_prompt += f'\n\n===== 参考资料 =====\n{knowledge_context}\n===== 参考资料结束 ====='

        messages = [{'role': 'system', 'content': system_prompt}]
        if dialog_history:
            messages.extend(dialog_history)
        messages.append({'role': 'user', 'content': user_message})

        # 定义搜索工具
        tools = None
        if enable_search:
            tools = [{
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "搜索互联网获取最新信息。当用户询问最新新闻、实时数据、近期事件、或你不确定的事实时使用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词，应该简洁明确"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }]

        try:
            # 第一次请求：让AI决定是否需要搜索
            response = self._make_tool_request(messages, tools=tools, stream=False)
            response.raise_for_status()
            result = response.json()
            
            choice = result.get('choices', [{}])[0]
            message = choice.get('message', {})
            
            # 检查是否需要调用工具
            tool_calls = message.get('tool_calls', [])
            
            if tool_calls:
                # AI决定调用搜索工具
                search_service = get_search_service()
                
                # 处理工具调用
                messages.append(message)  # 添加assistant的tool_calls消息
                
                for tool_call in tool_calls:
                    if tool_call.get('function', {}).get('name') == 'web_search':
                        # 解析搜索参数
                        try:
                            args = json.loads(tool_call['function']['arguments'])
                            query = args.get('query', user_message)
                        except:
                            query = user_message
                        
                        # 执行搜索
                        yield f"🔍 正在搜索: {query}...\n\n"
                        
                        search_response = search_service.search(query, max_results=5)
                        
                        if search_response.success:
                            # 格式化搜索结果
                            search_context = search_service.format_results_for_context(
                                search_response.results,
                                search_response.answer
                            )
                            
                            # 添加工具结果到消息
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': tool_call['id'],
                                'content': search_context
                            })
                        else:
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': tool_call['id'],
                                'content': f'搜索失败: {search_response.message}'
                            })
                
                # 第二次请求：基于搜索结果生成回复（流式）
                final_response = self._make_request(messages, stream=True)
                final_response.raise_for_status()
                
                for line in final_response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                choices = chunk.get('choices', [])
                                if choices and len(choices) > 0:
                                    delta = choices[0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
            else:
                # AI不需要搜索，直接返回内容
                content = message.get('content', '')
                if content:
                    yield content

        except requests.RequestException as e:
            current_app.logger.error(f'AI chat with tools error: {str(e)}')
            yield '抱歉，AI回复出现问题。'
        except Exception as e:
            current_app.logger.error(f'AI chat with tools error: {str(e)}')
            yield f'抱歉，出现错误: {str(e)}'

    def _make_tool_request(self, messages: list, tools: list = None, stream: bool = False, **kwargs):
        """发起支持工具调用的API请求"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.model,
            'messages': messages,
            'max_tokens': kwargs.get('max_tokens', self.max_tokens),
            'temperature': kwargs.get('temperature', self.temperature),
            'stream': stream
        }
        
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'

        response = requests.post(
            f'{self.api_base}/chat/completions',
            headers=headers,
            json=payload,
            stream=stream,
            timeout=kwargs.get('timeout', 60)
        )

        return response


# 模块初始化时的AI服务实例获取函数
def get_ai_service(module: str = None):
    """
    获取AI服务实例
    
    Args:
        module: 模块名称，如果指定则使用对应模块的配置
               可选值: moderation, chat, write, roast, image, vision
               如果为None，使用全局配置
    
    Returns:
        AIService: 配置好的AI服务实例
    """
    if module:
        from app.services.ai_factory import AIServiceFactory
        return AIServiceFactory.get_service(module)
    else:
        # 使用全局配置
        from app.services.config_service import get_ai_global_config
        config = get_ai_global_config()
        return AIService(config)
