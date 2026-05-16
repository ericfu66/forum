"""
视觉理解服务 - VLM API
支持Qwen2-VL、DeepseekVL2等视觉语言模型
"""
import requests
import base64
import re
import time
from typing import Dict, Any, List, Optional, Tuple, Generator
from dataclasses import dataclass
from flask import current_app

from app.services.config_service import get_ai_module_config


# 支持的detail参数值
VALID_DETAIL_VALUES = ['low', 'high', 'auto']

# 最大图片数量限制
MAX_IMAGES = 4

# Token估算（基于detail参数）
TOKEN_ESTIMATES = {
    'low': 85,      # 低精度模式
    'high': 765,    # 高精度模式（基于512x512切片）
    'auto': 425     # 自动模式（取中间值）
}


@dataclass
class VisionResult:
    """视觉理解结果"""
    success: bool
    message: str
    content: str
    tokens_used: int
    response_time: float  # 毫秒


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    message: str


def validate_detail_parameter(detail: str) -> ValidationResult:
    """
    验证detail参数是否有效
    
    Args:
        detail: detail参数值
        
    Returns:
        ValidationResult: 验证结果
    """
    if detail not in VALID_DETAIL_VALUES:
        return ValidationResult(
            valid=False,
            message=f'detail参数无效，只接受: {", ".join(VALID_DETAIL_VALUES)}'
        )
    return ValidationResult(valid=True, message='')


def validate_image_count(count: int) -> ValidationResult:
    """
    验证图片数量是否有效
    
    Args:
        count: 图片数量
        
    Returns:
        ValidationResult: 验证结果
    """
    if count < 1:
        return ValidationResult(
            valid=False,
            message='至少需要1张图片'
        )
    if count > MAX_IMAGES:
        return ValidationResult(
            valid=False,
            message=f'最多支持{MAX_IMAGES}张图片'
        )
    return ValidationResult(valid=True, message='')


def validate_image_input(image_input: str) -> ValidationResult:
    """
    验证图片输入格式是否有效
    
    Args:
        image_input: 图片URL或base64字符串
        
    Returns:
        ValidationResult: 验证结果
    """
    if not image_input:
        return ValidationResult(valid=False, message='图片输入不能为空')
    
    # 检查是否是URL
    if image_input.startswith('http://') or image_input.startswith('https://'):
        return ValidationResult(valid=True, message='')
    
    # 检查是否是base64
    if image_input.startswith('data:image/'):
        return ValidationResult(valid=True, message='')
    
    # 尝试检测是否是纯base64字符串
    try:
        # 简单检查是否是有效的base64
        if len(image_input) > 100:  # base64图片通常很长
            base64.b64decode(image_input[:100])  # 只检查前100个字符
            return ValidationResult(valid=True, message='')
    except:
        pass
    
    return ValidationResult(
        valid=False,
        message='图片格式无效，请提供URL（http://或https://）或base64编码'
    )


def estimate_tokens(image_input: str, detail: str = 'high') -> int:
    """
    估算图片消耗的token数
    
    Args:
        image_input: 图片输入
        detail: 精度参数
        
    Returns:
        int: 估算的token数
    """
    return TOKEN_ESTIMATES.get(detail, TOKEN_ESTIMATES['high'])


class VisionService:
    """视觉理解服务 - VLM API"""
    
    def __init__(self):
        """初始化视觉理解服务"""
        self.config = get_ai_module_config('vision')
        self.api_base = self.config.get('api_base', 'https://api.siliconflow.cn/v1').rstrip('/')
        self.api_key = self.config.get('api_key', '')
        self.model = self.config.get('model', 'Qwen/Qwen2-VL-72B-Instruct')
        self.default_detail = self.config.get('default_detail', 'high')
    
    def _build_image_content(self, image_input: str, detail: str = None) -> Dict[str, Any]:
        """
        构建图片内容对象
        
        Args:
            image_input: 图片URL或base64
            detail: 精度参数
            
        Returns:
            Dict: 图片内容对象
        """
        detail = detail or self.default_detail
        
        # 判断输入类型
        if image_input.startswith('http://') or image_input.startswith('https://'):
            # URL格式
            return {
                'type': 'image_url',
                'image_url': {
                    'url': image_input,
                    'detail': detail
                }
            }
        elif image_input.startswith('data:image/'):
            # 已经是完整的data URL格式
            return {
                'type': 'image_url',
                'image_url': {
                    'url': image_input,
                    'detail': detail
                }
            }
        else:
            # 假设是纯base64，添加前缀
            # 尝试检测图片类型
            if image_input.startswith('/9j/'):
                mime_type = 'image/jpeg'
            elif image_input.startswith('iVBOR'):
                mime_type = 'image/png'
            elif image_input.startswith('R0lGOD'):
                mime_type = 'image/gif'
            elif image_input.startswith('UklGR'):
                mime_type = 'image/webp'
            else:
                mime_type = 'image/png'  # 默认
            
            return {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:{mime_type};base64,{image_input}',
                    'detail': detail
                }
            }
    
    def understand_image(self, image_input: str, prompt: str,
                         detail: str = None) -> VisionResult:
        """
        理解单张图片
        
        Args:
            image_input: 图片URL或base64
            prompt: 用户问题/提示
            detail: 精度参数 ('low', 'high', 'auto')
            
        Returns:
            VisionResult: 理解结果
        """
        return self.understand_multiple_images([image_input], prompt, detail)
    
    def understand_multiple_images(self, images: List[str], prompt: str,
                                    detail: str = None) -> VisionResult:
        """
        理解多张图片
        
        Args:
            images: 图片列表（URL或base64）
            prompt: 用户问题/提示
            detail: 精度参数
            
        Returns:
            VisionResult: 理解结果
        """
        detail = detail or self.default_detail
        
        # 验证API配置
        if not self.api_key:
            return VisionResult(
                success=False,
                message='视觉理解API密钥未配置',
                content='',
                tokens_used=0,
                response_time=0
            )
        
        # 验证detail参数
        detail_result = validate_detail_parameter(detail)
        if not detail_result.valid:
            return VisionResult(
                success=False,
                message=detail_result.message,
                content='',
                tokens_used=0,
                response_time=0
            )
        
        # 验证图片数量
        count_result = validate_image_count(len(images))
        if not count_result.valid:
            return VisionResult(
                success=False,
                message=count_result.message,
                content='',
                tokens_used=0,
                response_time=0
            )
        
        # 验证每张图片
        for i, img in enumerate(images):
            img_result = validate_image_input(img)
            if not img_result.valid:
                return VisionResult(
                    success=False,
                    message=f'第{i+1}张图片: {img_result.message}',
                    content='',
                    tokens_used=0,
                    response_time=0
                )
        
        # 验证prompt
        if not prompt or not prompt.strip():
            return VisionResult(
                success=False,
                message='提示词不能为空',
                content='',
                tokens_used=0,
                response_time=0
            )
        
        # 构建消息内容
        content = []
        for img in images:
            content.append(self._build_image_content(img, detail))
        content.append({
            'type': 'text',
            'text': prompt.strip()
        })
        
        # 构建请求
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': content
                }
            ],
            'max_tokens': 2000
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload,
                timeout=60
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                result = response.json()
                content_text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                usage = result.get('usage', {})
                tokens_used = usage.get('total_tokens', 0)
                
                return VisionResult(
                    success=True,
                    message='理解成功',
                    content=content_text,
                    tokens_used=tokens_used,
                    response_time=round(response_time, 2)
                )
            
            elif response.status_code == 401:
                return VisionResult(
                    success=False,
                    message='API密钥无效',
                    content='',
                    tokens_used=0,
                    response_time=round(response_time, 2)
                )
            
            elif response.status_code == 429:
                return VisionResult(
                    success=False,
                    message='请求过于频繁，请稍后再试',
                    content='',
                    tokens_used=0,
                    response_time=round(response_time, 2)
                )
            
            else:
                error_msg = ''
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', '')
                    if not error_msg:
                        error_msg = error_data.get('message', '')
                except:
                    error_msg = response.text[:200] if response.text else ''
                
                return VisionResult(
                    success=False,
                    message=f'请求失败 ({response.status_code}): {error_msg}',
                    content='',
                    tokens_used=0,
                    response_time=round(response_time, 2)
                )
        
        except requests.exceptions.Timeout:
            return VisionResult(
                success=False,
                message='请求超时，请稍后重试',
                content='',
                tokens_used=0,
                response_time=60000
            )
        
        except requests.exceptions.ConnectionError:
            return VisionResult(
                success=False,
                message='无法连接到视觉理解服务',
                content='',
                tokens_used=0,
                response_time=0
            )
        
        except Exception as e:
            current_app.logger.error(f'Vision understanding error: {str(e)}')
            return VisionResult(
                success=False,
                message=f'理解失败: {str(e)}',
                content='',
                tokens_used=0,
                response_time=0
            )
    
    def understand_image_stream(self, image_input: str, prompt: str,
                                 detail: str = None) -> Generator[str, None, None]:
        """
        流式理解图片
        
        Args:
            image_input: 图片URL或base64
            prompt: 用户问题/提示
            detail: 精度参数
            
        Yields:
            str: 流式输出的文本片段
        """
        yield from self.understand_multiple_images_stream([image_input], prompt, detail)
    
    def understand_multiple_images_stream(self, images: List[str], prompt: str,
                                           detail: str = None) -> Generator[str, None, None]:
        """
        流式理解多张图片
        
        Args:
            images: 图片列表
            prompt: 用户问题/提示
            detail: 精度参数
            
        Yields:
            str: 流式输出的文本片段
        """
        import json
        
        detail = detail or self.default_detail
        
        # 验证
        if not self.api_key:
            yield '视觉理解API密钥未配置'
            return
        
        detail_result = validate_detail_parameter(detail)
        if not detail_result.valid:
            yield detail_result.message
            return
        
        count_result = validate_image_count(len(images))
        if not count_result.valid:
            yield count_result.message
            return
        
        for i, img in enumerate(images):
            img_result = validate_image_input(img)
            if not img_result.valid:
                yield f'第{i+1}张图片: {img_result.message}'
                return
        
        if not prompt or not prompt.strip():
            yield '提示词不能为空'
            return
        
        # 构建消息内容
        content = []
        for img in images:
            content.append(self._build_image_content(img, detail))
        content.append({
            'type': 'text',
            'text': prompt.strip()
        })
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': content
                }
            ],
            'max_tokens': 2000,
            'stream': True
        }
        
        try:
            response = requests.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload,
                stream=True,
                timeout=60
            )
            
            if response.status_code != 200:
                error_msg = ''
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', '')
                except:
                    error_msg = response.text[:200] if response.text else ''
                yield f'请求失败: {error_msg}'
                return
            
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
                                content_text = delta.get('content', '')
                                if content_text:
                                    yield content_text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        
        except requests.exceptions.Timeout:
            yield '请求超时'
        except requests.exceptions.ConnectionError:
            yield '无法连接到服务'
        except Exception as e:
            yield f'错误: {str(e)}'
    
    def estimate_tokens(self, images: List[str], detail: str = None) -> int:
        """
        估算图片消耗的token数
        
        Args:
            images: 图片列表
            detail: 精度参数
            
        Returns:
            int: 估算的总token数
        """
        detail = detail or self.default_detail
        per_image = TOKEN_ESTIMATES.get(detail, TOKEN_ESTIMATES['high'])
        return per_image * len(images)


def get_vision_service() -> VisionService:
    """获取视觉理解服务实例"""
    return VisionService()
