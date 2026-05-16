"""
图片生成服务 - OpenAI兼容API
支持多种生图模型，包括DALL-E、Kolors、FLUX、SD等
支持参考图（图生图）功能
支持通过chat completions API生成图片的模型（如Gemini）
"""
import requests
import os
import uuid
import time
import base64
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from flask import current_app
from datetime import datetime

from app.services.ai_factory import AIServiceFactory
from app.services.config_service import get_ai_module_config


# 预设模型配置（可在管理后台自定义添加）
PRESET_MODELS = {
    'Kwai-Kolors/Kolors': {
        'name': 'Kolors',
        'provider': 'SiliconFlow',
        'api_type': 'images',  # 使用 /images/generations 端点
        'supports_image2image': True,
        'supports_negative_prompt': True,
        'sizes': ['1024x1024', '960x1280', '768x1024', '720x1280', '1280x720', '1024x768', '1280x960', '512x512'],
        'batch_size': (1, 4),
        'inference_steps': (1, 100),
        'guidance_scale': (0, 20)
    },
    'stabilityai/stable-diffusion-3-5-large': {
        'name': 'SD 3.5 Large',
        'provider': 'SiliconFlow',
        'api_type': 'images',
        'supports_image2image': True,
        'supports_negative_prompt': True,
        'sizes': ['1024x1024', '1024x576', '576x1024', '1536x1024', '1024x1536'],
        'batch_size': (1, 4),
        'inference_steps': (1, 50),
        'guidance_scale': (0, 20)
    },
    'black-forest-labs/FLUX.1-schnell': {
        'name': 'FLUX.1 Schnell',
        'provider': 'SiliconFlow',
        'api_type': 'images',
        'supports_image2image': False,
        'supports_negative_prompt': False,
        'sizes': ['1024x1024', '1024x576', '576x1024', '768x1024', '1024x768'],
        'batch_size': (1, 4),
        'inference_steps': (1, 50),
        'guidance_scale': (0, 20)
    },
    'dall-e-3': {
        'name': 'DALL-E 3',
        'provider': 'OpenAI',
        'api_type': 'images',
        'supports_image2image': False,
        'supports_negative_prompt': False,
        'sizes': ['1024x1024', '1792x1024', '1024x1792'],
        'batch_size': (1, 1),
        'inference_steps': None,
        'guidance_scale': None
    },
    'dall-e-2': {
        'name': 'DALL-E 2',
        'provider': 'OpenAI',
        'api_type': 'images',
        'supports_image2image': True,
        'supports_negative_prompt': False,
        'sizes': ['256x256', '512x512', '1024x1024'],
        'batch_size': (1, 10),
        'inference_steps': None,
        'guidance_scale': None
    },
    # Chat Completions API 生图模型
    'gemini-2.0-flash-exp-image-generation': {
        'name': 'Gemini 2.0 Flash Image',
        'provider': 'Google',
        'api_type': 'chat',  # 使用 /chat/completions 端点
        'supports_image2image': True,
        'supports_negative_prompt': False,
        'sizes': ['1024x1024'],
        'batch_size': (1, 1),
        'inference_steps': None,
        'guidance_scale': None
    },
    'gemini-3-pro-image-preview-1k': {
        'name': 'Gemini 3 Pro Image',
        'provider': 'Google',
        'api_type': 'chat',  # 使用 /chat/completions 端点
        'supports_image2image': True,
        'supports_negative_prompt': False,
        'sizes': ['1024x1024'],
        'batch_size': (1, 1),
        'inference_steps': None,
        'guidance_scale': None
    }
}

# 支持的图片尺寸（按模型分类）- 兼容旧代码
IMAGE_SIZES = {model: config['sizes'] for model, config in PRESET_MODELS.items()}
IMAGE_SIZES['default'] = ['1024x1024', '512x512', '768x1024', '1024x768']

# 批量生成限制
BATCH_SIZE_LIMITS = {model: config['batch_size'] for model, config in PRESET_MODELS.items() if config['batch_size']}
BATCH_SIZE_LIMITS['default'] = (1, 4)

# 推理步数限制
INFERENCE_STEPS_LIMITS = {model: config['inference_steps'] for model, config in PRESET_MODELS.items() if config['inference_steps']}
INFERENCE_STEPS_LIMITS['default'] = (1, 100)

# 引导系数限制
GUIDANCE_SCALE_LIMITS = {model: config['guidance_scale'] for model, config in PRESET_MODELS.items() if config['guidance_scale']}
GUIDANCE_SCALE_LIMITS['default'] = (0, 20)


@dataclass
class ImageGenerationResult:
    """图片生成结果"""
    success: bool
    message: str
    images: List[Dict[str, Any]]  # [{'url': '...', 'seed': 123}, ...]
    seed: Optional[int]
    inference_time: float  # 毫秒

@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    message: str


def validate_image_size(model: str, image_size: str) -> ValidationResult:
    """
    验证图片尺寸是否有效
    
    Args:
        model: 模型名称
        image_size: 图片尺寸
        
    Returns:
        ValidationResult: 验证结果
    """
    valid_sizes = IMAGE_SIZES.get(model, IMAGE_SIZES['default'])
    
    if image_size not in valid_sizes:
        return ValidationResult(
            valid=False,
            message=f'不支持的图片尺寸: {image_size}。支持的尺寸: {", ".join(valid_sizes)}'
        )
    
    return ValidationResult(valid=True, message='')


def validate_batch_size(model: str, batch_size: int) -> ValidationResult:
    """
    验证批量生成数量是否有效
    
    Args:
        model: 模型名称
        batch_size: 批量数量
        
    Returns:
        ValidationResult: 验证结果
    """
    min_size, max_size = BATCH_SIZE_LIMITS.get(model, BATCH_SIZE_LIMITS['default'])
    
    if batch_size < min_size or batch_size > max_size:
        return ValidationResult(
            valid=False,
            message=f'批量数量必须在 {min_size}-{max_size} 之间'
        )
    
    return ValidationResult(valid=True, message='')


def validate_inference_steps(model: str, steps: int) -> ValidationResult:
    """
    验证推理步数是否有效
    
    Args:
        model: 模型名称
        steps: 推理步数
        
    Returns:
        ValidationResult: 验证结果
    """
    min_steps, max_steps = INFERENCE_STEPS_LIMITS.get(model, INFERENCE_STEPS_LIMITS['default'])
    
    if steps < min_steps or steps > max_steps:
        return ValidationResult(
            valid=False,
            message=f'推理步数必须在 {min_steps}-{max_steps} 之间'
        )
    
    return ValidationResult(valid=True, message='')


def validate_guidance_scale(model: str, scale: float) -> ValidationResult:
    """
    验证引导系数是否有效
    
    Args:
        model: 模型名称
        scale: 引导系数
        
    Returns:
        ValidationResult: 验证结果
    """
    min_scale, max_scale = GUIDANCE_SCALE_LIMITS.get(model, GUIDANCE_SCALE_LIMITS['default'])
    
    if scale < min_scale or scale > max_scale:
        return ValidationResult(
            valid=False,
            message=f'引导系数必须在 {min_scale}-{max_scale} 之间'
        )
    
    return ValidationResult(valid=True, message='')


class ImageService:
    """图片生成服务 - OpenAI兼容API，支持双API和表情包生成"""
    
    def __init__(self):
        """初始化图片生成服务"""
        self.config = get_ai_module_config('image')
        # 主API配置
        self.api_base = self.config.get('api_base', 'https://api.siliconflow.cn/v1').rstrip('/')
        self.api_key = self.config.get('api_key', '')
        self.default_model = self.config.get('model', 'Kwai-Kolors/Kolors')
        self.default_size = self.config.get('default_size', '1024x1024')
        self.default_steps = self.config.get('num_inference_steps', 20)
        self.default_guidance = self.config.get('guidance_scale', 7.5)
        
        # 备用API配置（SiliconFlow Kolors）
        self.fallback_api_base = self.config.get('fallback_api_base', 'https://api.siliconflow.cn/v1').rstrip('/')
        self.fallback_api_key = self.config.get('fallback_api_key', '')
        self.fallback_model = self.config.get('fallback_model', 'Kwai-Kolors/Kolors')
        
        # 每日限制
        self.daily_limit = self.config.get('daily_limit', 5)
        
        # 从配置读取可用模型列表
        available_models_str = self.config.get('available_models', '')
        if available_models_str:
            self.configured_models = [m.strip() for m in available_models_str.split('\n') if m.strip()]
        else:
            self.configured_models = []
        # 自定义模型列表（从配置读取）
        self.custom_models = self.config.get('custom_models', [])
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取所有可用的生图模型列表
        
        Returns:
            List[Dict]: 模型列表，包含id、name、provider等信息
        """
        models = []
        added_ids = set()
        
        # 优先添加配置中指定的模型
        for model_id in self.configured_models:
            if model_id in added_ids:
                continue
            added_ids.add(model_id)
            
            # 检查是否是预设模型
            if model_id in PRESET_MODELS:
                config = PRESET_MODELS[model_id]
                models.append({
                    'id': model_id,
                    'name': config['name'],
                    'provider': config['provider'],
                    'supports_image2image': config['supports_image2image'],
                    'supports_negative_prompt': config['supports_negative_prompt'],
                    'sizes': config['sizes'],
                    'is_custom': False
                })
            else:
                # 自定义模型
                models.append({
                    'id': model_id,
                    'name': model_id.split('/')[-1] if '/' in model_id else model_id,
                    'provider': 'Custom',
                    'supports_image2image': True,
                    'supports_negative_prompt': True,
                    'sizes': IMAGE_SIZES['default'],
                    'is_custom': True
                })
        
        # 如果配置为空，添加预设模型
        if not models:
            for model_id, config in PRESET_MODELS.items():
                models.append({
                    'id': model_id,
                    'name': config['name'],
                    'provider': config['provider'],
                    'supports_image2image': config['supports_image2image'],
                    'supports_negative_prompt': config['supports_negative_prompt'],
                    'sizes': config['sizes'],
                    'is_custom': False
                })
        
        return models
    
    def get_model_config(self, model: str) -> Dict[str, Any]:
        """
        获取指定模型的配置
        
        Args:
            model: 模型ID
            
        Returns:
            Dict: 模型配置
        """
        # 先检查预设模型
        if model in PRESET_MODELS:
            return PRESET_MODELS[model]
        
        # 检查自定义模型
        for custom in self.custom_models:
            if custom.get('id') == model or custom.get('model') == model:
                return {
                    'name': custom.get('name', model),
                    'provider': custom.get('provider', 'Custom'),
                    'supports_image2image': custom.get('supports_image2image', True),
                    'supports_negative_prompt': custom.get('supports_negative_prompt', True),
                    'sizes': custom.get('sizes', IMAGE_SIZES['default']),
                    'batch_size': custom.get('batch_size', (1, 4)),
                    'inference_steps': custom.get('inference_steps', (1, 100)),
                    'guidance_scale': custom.get('guidance_scale', (0, 20))
                }
        
        # 返回默认配置 - 自定义模型默认使用chat API（更通用）
        return {
            'name': model,
            'provider': 'Custom',
            'api_type': 'chat',  # 默认使用chat API，因为更通用
            'supports_image2image': True,
            'supports_negative_prompt': False,
            'sizes': IMAGE_SIZES['default'],
            'batch_size': BATCH_SIZE_LIMITS['default'],
            'inference_steps': INFERENCE_STEPS_LIMITS['default'],
            'guidance_scale': GUIDANCE_SCALE_LIMITS['default']
        }
    
    def _encode_image_to_base64(self, image_data: bytes) -> str:
        """将图片数据编码为base64"""
        return base64.b64encode(image_data).decode('utf-8')
    
    def _prepare_reference_image(self, reference_image: str) -> Optional[str]:
        """
        准备参考图数据
        
        Args:
            reference_image: 可以是URL、base64字符串或文件路径
            
        Returns:
            str: base64编码的图片数据，或None
        """
        if not reference_image:
            return None
        
        try:
            # 如果已经是base64
            if reference_image.startswith('data:image'):
                # 提取base64部分
                return reference_image.split(',')[1] if ',' in reference_image else reference_image
            
            # 如果是URL
            if reference_image.startswith('http://') or reference_image.startswith('https://'):
                response = requests.get(reference_image, timeout=30)
                if response.status_code == 200:
                    return self._encode_image_to_base64(response.content)
                return None
            
            # 如果是本地文件路径
            if os.path.exists(reference_image):
                with open(reference_image, 'rb') as f:
                    return self._encode_image_to_base64(f.read())
            
            # 假设是纯base64字符串
            return reference_image
            
        except Exception as e:
            current_app.logger.error(f'Failed to prepare reference image: {e}')
            return None
    
    def generate_image(self, prompt: str, negative_prompt: str = None,
                       model: str = None, image_size: str = None,
                       batch_size: int = 1, seed: int = None,
                       num_inference_steps: int = None,
                       guidance_scale: float = None,
                       reference_image: str = None,
                       image_strength: float = 0.65) -> ImageGenerationResult:
        """
        生成图片
        
        Args:
            prompt: 图片描述提示词
            negative_prompt: 负面提示词（排除元素）
            model: 模型名称（默认使用配置中的模型）
            image_size: 图片尺寸（默认使用配置中的尺寸）
            batch_size: 批量生成数量（1-4）
            seed: 随机种子（可选）
            num_inference_steps: 推理步数（1-100）
            guidance_scale: 引导系数（0-20）
            reference_image: 参考图（URL、base64或文件路径）
            image_strength: 参考图强度（0-1，越高越接近参考图）
            
        Returns:
            ImageGenerationResult: 生成结果
        """
        # 使用默认值
        model = model or self.default_model
        image_size = image_size or self.default_size
        num_inference_steps = num_inference_steps if num_inference_steps is not None else self.default_steps
        guidance_scale = guidance_scale if guidance_scale is not None else self.default_guidance
        
        # 获取模型配置
        model_config = self.get_model_config(model)
        api_type = model_config.get('api_type', 'images')
        
        # 验证参数
        if not prompt or not prompt.strip():
            return ImageGenerationResult(
                success=False,
                message='提示词不能为空',
                images=[],
                seed=None,
                inference_time=0
            )
        
        if not self.api_key:
            return ImageGenerationResult(
                success=False,
                message='图片生成API密钥未配置',
                images=[],
                seed=None,
                inference_time=0
            )
        
        # 检查是否支持图生图
        if reference_image and not model_config.get('supports_image2image', True):
            return ImageGenerationResult(
                success=False,
                message=f'模型 {model_config.get("name", model)} 不支持参考图功能',
                images=[],
                seed=None,
                inference_time=0
            )
        
        # 根据API类型选择不同的生成方式
        if api_type == 'chat':
            return self._generate_via_chat_api(
                prompt=prompt,
                model=model,
                reference_image=reference_image,
                image_size=image_size
            )
        else:
            return self._generate_via_images_api(
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=model,
                model_config=model_config,
                image_size=image_size,
                batch_size=batch_size,
                seed=seed,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                reference_image=reference_image,
                image_strength=image_strength
            )
    
    def _generate_via_chat_api(self, prompt: str, model: str,
                                reference_image: str = None,
                                image_size: str = '1024x1024') -> ImageGenerationResult:
        """
        通过 Chat Completions API 生成图片（适用于Gemini等模型）
        
        Args:
            prompt: 图片描述
            model: 模型名称
            reference_image: 参考图（可选）
            image_size: 图片尺寸
            
        Returns:
            ImageGenerationResult: 生成结果
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # 构建消息内容
        content = []
        
        # 如果有参考图，添加到消息中
        if reference_image:
            ref_image_base64 = self._prepare_reference_image(reference_image)
            if ref_image_base64:
                # 确定图片类型
                if ref_image_base64.startswith('/9j/'):
                    mime_type = 'image/jpeg'
                elif ref_image_base64.startswith('iVBOR'):
                    mime_type = 'image/png'
                else:
                    mime_type = 'image/png'
                
                content.append({
                    'type': 'image_url',
                    'image_url': {
                        'url': f'data:{mime_type};base64,{ref_image_base64}'
                    }
                })
        
        # 添加文本提示
        generation_prompt = f"请根据以下描述生成一张图片：{prompt}"
        if reference_image:
            generation_prompt = f"请参考这张图片，根据以下描述生成一张新图片：{prompt}"
        
        content.append({
            'type': 'text',
            'text': generation_prompt
        })
        
        payload = {
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': content
                }
            ],
            'max_tokens': 4096
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload,
                timeout=180  # Chat API生图可能需要更长时间
            )
            
            inference_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    return ImageGenerationResult(
                        success=False,
                        message=f'API返回无效JSON: {response.text[:200] if response.text else "空响应"}',
                        images=[],
                        seed=None,
                        inference_time=round(inference_time, 2)
                    )
                images = []
                
                # 解析响应，提取图片
                choices = result.get('choices', [])
                for choice in choices:
                    message = choice.get('message', {})
                    msg_content = message.get('content', '')
                    
                    # 检查content是否是列表（多模态响应）
                    if isinstance(msg_content, list):
                        for item in msg_content:
                            if isinstance(item, dict):
                                # 检查是否是图片类型
                                if item.get('type') == 'image_url':
                                    image_url = item.get('image_url', {})
                                    url = image_url.get('url', '')
                                    if url:
                                        images.append({'url': url})
                                # 有些API返回inline_data
                                elif item.get('type') == 'image':
                                    # base64图片数据
                                    b64_data = item.get('data', item.get('image', ''))
                                    if b64_data:
                                        # 保存为临时文件并返回URL
                                        saved_url = self._save_base64_image(b64_data)
                                        if saved_url:
                                            images.append({'url': saved_url})
                    elif isinstance(msg_content, str):
                        # 尝试从文本中提取base64图片
                        extracted = self._extract_images_from_text(msg_content)
                        images.extend(extracted)
                
                if images:
                    return ImageGenerationResult(
                        success=True,
                        message='图片生成成功',
                        images=images,
                        seed=None,
                        inference_time=round(inference_time, 2)
                    )
                else:
                    # 没有找到图片，可能模型返回了文本
                    text_response = ''
                    if choices:
                        msg = choices[0].get('message', {})
                        text_response = msg.get('content', '')[:200] if isinstance(msg.get('content'), str) else ''
                    
                    return ImageGenerationResult(
                        success=False,
                        message=f'模型未返回图片。响应: {text_response}',
                        images=[],
                        seed=None,
                        inference_time=round(inference_time, 2)
                    )
            
            elif response.status_code == 401:
                return ImageGenerationResult(
                    success=False,
                    message='API密钥无效',
                    images=[],
                    seed=None,
                    inference_time=round((time.time() - start_time) * 1000, 2)
                )
            
            else:
                error_msg = ''
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', '')
                    if not error_msg:
                        error_msg = error_data.get('message', str(error_data))
                except:
                    error_msg = response.text[:300] if response.text else ''
                
                return ImageGenerationResult(
                    success=False,
                    message=f'生成失败 ({response.status_code}): {error_msg}',
                    images=[],
                    seed=None,
                    inference_time=round((time.time() - start_time) * 1000, 2)
                )
        
        except requests.exceptions.Timeout:
            return ImageGenerationResult(
                success=False,
                message='请求超时，请稍后重试',
                images=[],
                seed=None,
                inference_time=180000
            )
        
        except Exception as e:
            current_app.logger.error(f'Chat API image generation error: {str(e)}')
            return ImageGenerationResult(
                success=False,
                message=f'生成失败: {str(e)}',
                images=[],
                seed=None,
                inference_time=0
            )
    
    def _save_base64_image(self, base64_data: str) -> Optional[str]:
        """将base64图片数据保存为文件并返回URL"""
        try:
            # 移除可能的data URL前缀
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            # 解码
            image_data = base64.b64decode(base64_data)
            
            # 确定扩展名
            if base64_data.startswith('/9j/'):
                ext = '.jpg'
            else:
                ext = '.png'
            
            # 生成文件名
            filename = f'chat_gen_{uuid.uuid4().hex[:8]}{ext}'
            
            # 确保目录存在
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ai_images')
            os.makedirs(upload_dir, exist_ok=True)
            
            # 保存文件
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            return f'/static/uploads/ai_images/{filename}'
        except Exception as e:
            current_app.logger.error(f'Failed to save base64 image: {e}')
            return None
    
    def _extract_images_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本响应中提取图片（base64或URL）"""
        images = []
        
        # 尝试提取base64图片
        base64_pattern = r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)'
        matches = re.findall(base64_pattern, text)
        for match in matches:
            saved_url = self._save_base64_image(match)
            if saved_url:
                images.append({'url': saved_url})
        
        # 尝试提取图片URL
        url_pattern = r'https?://[^\s<>"\']+\.(?:png|jpg|jpeg|gif|webp)'
        url_matches = re.findall(url_pattern, text, re.IGNORECASE)
        for url in url_matches:
            images.append({'url': url})
        
        return images
    
    def _generate_via_images_api(self, prompt: str, negative_prompt: str,
                                  model: str, model_config: Dict,
                                  image_size: str, batch_size: int,
                                  seed: int, num_inference_steps: int,
                                  guidance_scale: float, reference_image: str,
                                  image_strength: float) -> ImageGenerationResult:
        """
        通过 Images API 生成图片（传统方式）
        """
        # 验证图片尺寸
        size_result = validate_image_size(model, image_size)
        if not size_result.valid:
            if model not in PRESET_MODELS:
                image_size = '1024x1024'
            else:
                return ImageGenerationResult(
                    success=False,
                    message=size_result.message,
                    images=[],
                    seed=None,
                    inference_time=0
                )
        
        # 验证批量数量
        batch_result = validate_batch_size(model, batch_size)
        if not batch_result.valid:
            return ImageGenerationResult(
                success=False,
                message=batch_result.message,
                images=[],
                seed=None,
                inference_time=0
            )
        
        # 验证推理步数
        steps_result = validate_inference_steps(model, num_inference_steps)
        if not steps_result.valid:
            return ImageGenerationResult(
                success=False,
                message=steps_result.message,
                images=[],
                seed=None,
                inference_time=0
            )
        
        # 验证引导系数
        guidance_result = validate_guidance_scale(model, guidance_scale)
        if not guidance_result.valid:
            return ImageGenerationResult(
                success=False,
                message=guidance_result.message,
                images=[],
                seed=None,
                inference_time=0
            )
        
        # 构建请求
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'prompt': prompt.strip(),
            'image_size': image_size,
            'batch_size': batch_size,
            'num_inference_steps': num_inference_steps,
            'guidance_scale': guidance_scale
        }
        
        if negative_prompt and model_config.get('supports_negative_prompt', True):
            payload['negative_prompt'] = negative_prompt.strip()
        
        if seed is not None:
            payload['seed'] = seed
        
        # 处理参考图（图生图）
        ref_image_base64 = None
        if reference_image:
            ref_image_base64 = self._prepare_reference_image(reference_image)
            if ref_image_base64:
                payload['image'] = ref_image_base64
                payload['strength'] = max(0.0, min(1.0, image_strength))
        
        start_time = time.time()
        
        # 根据是否有参考图选择不同的API端点
        if ref_image_base64:
            api_endpoint = f'{self.api_base}/images/edits'
        else:
            api_endpoint = f'{self.api_base}/images/generations'
        
        try:
            response = requests.post(
                api_endpoint,
                headers=headers,
                json=payload,
                timeout=120
            )
            
            inference_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    return ImageGenerationResult(
                        success=False,
                        message=f'API返回无效JSON: {response.text[:200] if response.text else "空响应"}',
                        images=[],
                        seed=None,
                        inference_time=round(inference_time, 2)
                    )
                images = []
                
                for img_data in result.get('images', result.get('data', [])):
                    image_info = {'url': img_data.get('url', '')}
                    if 'seed' in img_data:
                        image_info['seed'] = img_data['seed']
                    images.append(image_info)
                
                result_seed = result.get('seed')
                if not result_seed and images and 'seed' in images[0]:
                    result_seed = images[0]['seed']
                
                return ImageGenerationResult(
                    success=True,
                    message='图片生成成功',
                    images=images,
                    seed=result_seed,
                    inference_time=round(inference_time, 2)
                )
            
            elif response.status_code == 401:
                return ImageGenerationResult(
                    success=False,
                    message='API密钥无效',
                    images=[],
                    seed=None,
                    inference_time=round(inference_time, 2)
                )
            
            elif response.status_code == 429:
                return ImageGenerationResult(
                    success=False,
                    message='请求过于频繁，请稍后再试',
                    images=[],
                    seed=None,
                    inference_time=round(inference_time, 2)
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
                
                return ImageGenerationResult(
                    success=False,
                    message=f'生成失败 ({response.status_code}): {error_msg}',
                    images=[],
                    seed=None,
                    inference_time=round(inference_time, 2)
                )
        
        except requests.exceptions.Timeout:
            return ImageGenerationResult(
                success=False,
                message='请求超时，请稍后重试',
                images=[],
                seed=None,
                inference_time=120000
            )
        
        except requests.exceptions.ConnectionError:
            return ImageGenerationResult(
                success=False,
                message='无法连接到图片生成服务',
                images=[],
                seed=None,
                inference_time=0
            )
        
        except Exception as e:
            current_app.logger.error(f'Image generation error: {str(e)}')
            return ImageGenerationResult(
                success=False,
                message=f'生成失败: {str(e)}',
                images=[],
                seed=None,
                inference_time=0
            )
    
    def download_and_save(self, image_url: str, user_id: int,
                          prompt: str = '', negative_prompt: str = '',
                          model: str = '', image_size: str = '',
                          seed: int = None) -> Tuple[bool, str, Optional['UserImage']]:
        """
        下载图片并保存到用户图库
        
        Args:
            image_url: 图片URL
            user_id: 用户ID
            prompt: 生成提示词
            negative_prompt: 负面提示词
            model: 使用的模型
            image_size: 图片尺寸
            seed: 生成种子
            
        Returns:
            Tuple[bool, str, Optional[UserImage]]: (成功, 消息, 图片记录)
        """
        from app.models.user_image import UserImage
        
        try:
            # 下载图片
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                return False, '图片下载失败', None
            
            # 确定文件扩展名
            content_type = response.headers.get('Content-Type', '')
            if 'png' in content_type:
                ext = '.png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'webp' in content_type:
                ext = '.webp'
            else:
                ext = '.png'  # 默认
            
            # 生成文件名
            filename = f'{user_id}_{uuid.uuid4().hex[:8]}{ext}'
            
            # 确保目录存在
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ai_images')
            os.makedirs(upload_dir, exist_ok=True)
            
            # 保存文件
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # 相对路径（用于URL访问）
            local_path = f'/static/uploads/ai_images/{filename}'
            
            # 创建数据库记录
            user_image = UserImage.create(
                user_id=user_id,
                image_url=image_url,
                local_path=local_path,
                prompt=prompt,
                negative_prompt=negative_prompt,
                model=model,
                image_type='generated',
                image_size=image_size,
                seed=seed
            )
            
            return True, '保存成功', user_image
        
        except requests.exceptions.Timeout:
            return False, '图片下载超时', None
        except requests.exceptions.RequestException as e:
            return False, f'图片下载失败: {str(e)}', None
        except Exception as e:
            current_app.logger.error(f'Save image error: {str(e)}')
            return False, f'保存失败: {str(e)}', None
    
    def save_to_gallery(self, user_id: int, image_url: str, prompt: str,
                        negative_prompt: str = '', model: str = '',
                        image_size: str = '', seed: int = None) -> Tuple[bool, str, Optional['UserImage']]:
        """
        保存图片到用户图库（下载并存储）
        
        Args:
            user_id: 用户ID
            image_url: 图片URL
            prompt: 生成提示词
            negative_prompt: 负面提示词
            model: 使用的模型
            image_size: 图片尺寸
            seed: 生成种子
            
        Returns:
            Tuple[bool, str, Optional[UserImage]]: (成功, 消息, 图片记录)
        """
        return self.download_and_save(
            image_url=image_url,
            user_id=user_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            image_size=image_size,
            seed=seed
        )
    
    def get_supported_sizes(self, model: str = None) -> List[str]:
        """
        获取模型支持的图片尺寸列表
        
        Args:
            model: 模型名称
            
        Returns:
            List[str]: 支持的尺寸列表
        """
        model = model or self.default_model
        return IMAGE_SIZES.get(model, IMAGE_SIZES['default'])
    
    def get_model_limits(self, model: str = None) -> Dict[str, Any]:
        """
        获取模型的参数限制
        
        Args:
            model: 模型名称
            
        Returns:
            Dict: 参数限制信息
        """
        model = model or self.default_model
        model_config = self.get_model_config(model)
        
        batch_limits = model_config.get('batch_size') or BATCH_SIZE_LIMITS.get(model, BATCH_SIZE_LIMITS['default'])
        steps_limits = model_config.get('inference_steps') or INFERENCE_STEPS_LIMITS.get(model, INFERENCE_STEPS_LIMITS['default'])
        guidance_limits = model_config.get('guidance_scale') or GUIDANCE_SCALE_LIMITS.get(model, GUIDANCE_SCALE_LIMITS['default'])
        
        batch_min, batch_max = batch_limits if batch_limits else (1, 4)
        steps_min, steps_max = steps_limits if steps_limits else (1, 100)
        guidance_min, guidance_max = guidance_limits if guidance_limits else (0, 20)
        
        return {
            'batch_size': {'min': batch_min, 'max': batch_max},
            'num_inference_steps': {'min': steps_min, 'max': steps_max},
            'guidance_scale': {'min': guidance_min, 'max': guidance_max},
            'image_sizes': model_config.get('sizes', IMAGE_SIZES.get(model, IMAGE_SIZES['default'])),
            'supports_image2image': model_config.get('supports_image2image', True),
            'supports_negative_prompt': model_config.get('supports_negative_prompt', True)
        }


def get_image_service() -> ImageService:
    """获取图片生成服务实例"""
    return ImageService()


def get_preset_models() -> Dict[str, Any]:
    """获取预设模型配置"""
    return PRESET_MODELS


def generate_prompt_with_ai(user_input: str, style: str = None) -> Tuple[bool, str, str]:
    """
    使用AI生成/优化绘图提示词
    
    Args:
        user_input: 用户输入的简单描述
        style: 风格偏好（可选）
        
    Returns:
        Tuple[bool, str, str]: (成功, 生成的提示词, 错误信息)
    """
    from app.services.config_service import get_ai_global_config
    
    config = get_ai_global_config()
    api_base = config.get('api_base', '').rstrip('/')
    api_key = config.get('api_key', '')
    model = config.get('model', 'gpt-4')
    
    if not api_key:
        return False, '', 'AI配置未设置'
    
    style_hint = f'风格偏好: {style}' if style else ''
    
    system_prompt = """你是一个专业的AI绘图提示词专家。用户会给你一个简单的描述，你需要将其扩展为详细的、高质量的绘图提示词。

要求：
1. 提示词应该是英文的
2. 包含主体描述、场景、光线、风格、细节等元素
3. 使用逗号分隔不同的描述元素
4. 添加质量相关的标签如 "masterpiece, best quality, highly detailed"
5. 根据内容适当添加艺术风格标签
6. 直接输出提示词，不要有任何解释或前缀"""

    user_prompt = f"请将以下描述转换为高质量的绘图提示词：\n{user_input}\n{style_hint}"
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'max_tokens': 500,
            'temperature': 0.7
        }
        
        response = requests.post(
            f'{api_base}/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            generated_prompt = result['choices'][0]['message']['content'].strip()
            
            # 处理思维链模型的输出（如DeepSeek-R1）
            from app.utils.think_parser import ThinkModelParser
            parse_result = ThinkModelParser.parse(generated_prompt)
            if parse_result.has_thinking:
                # 使用移除思维链后的响应内容
                generated_prompt = parse_result.response
            
            # 清理可能的引号
            generated_prompt = generated_prompt.strip('"\'')
            
            # 确保返回的提示词不为空
            if not generated_prompt:
                return False, '', 'AI返回的提示词为空，请重试'
            
            return True, generated_prompt, ''
        else:
            return False, '', f'API错误: {response.status_code}'
            
    except Exception as e:
        return False, '', f'生成失败: {str(e)}'


def _download_and_save_image(image_url: str, user_id: int, prompt: str = '',
                              model: str = '', image_type: str = 'generated',
                              image_size: str = '', negative_prompt: str = '',
                              seed: int = None) -> Optional[str]:
    """
    下载图片并保存到本地，返回本地URL
    
    Args:
        image_url: 外部图片URL
        user_id: 用户ID
        prompt: 提示词
        model: 模型名称
        image_type: 图片类型
        image_size: 图片尺寸
        negative_prompt: 负面提示词
        seed: 随机种子
        
    Returns:
        str: 本地图片URL，失败返回None
    """
    from app.models.user_image import UserImage
    
    try:
        # 下载图片
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            return None
        
        # 确定文件扩展名
        content_type = response.headers.get('Content-Type', '')
        if 'png' in content_type:
            ext = '.png'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            ext = '.jpg'
        elif 'webp' in content_type:
            ext = '.webp'
        else:
            ext = '.png'  # 默认
        
        # 生成文件名
        filename = f'{user_id}_{uuid.uuid4().hex[:8]}{ext}'
        
        # 确保目录存在
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'ai_images')
        os.makedirs(upload_dir, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        # 相对路径（用于URL访问）
        local_path = f'/static/uploads/ai_images/{filename}'
        
        # 创建数据库记录
        UserImage.create(
            user_id=user_id,
            image_url=image_url,
            local_path=local_path,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            image_type=image_type,
            image_size=image_size,
            seed=seed
        )
        
        return local_path
        
    except Exception as e:
        current_app.logger.error(f'Failed to download and save image: {e}')
        return None


def generate_sticker(prompt: str, user_id: int = None) -> Tuple[bool, str, str]:
    """
    生成表情包图片（使用备用API的Kolors模型）
    
    Args:
        prompt: 表情包描述
        user_id: 用户ID（可选，用于保存记录）
        
    Returns:
        Tuple[bool, str, str]: (成功, 图片URL, 错误信息)
    """
    service = get_image_service()
    
    # 表情包专用提示词增强
    sticker_prompt = f"cute chibi sticker style, {prompt}, simple background, white background, emoji style, kawaii, expressive face, bold outlines, vibrant colors"
    negative_prompt = "realistic, photo, complex background, text, watermark, signature"
    
    # 使用备用API（SiliconFlow Kolors）生成表情包
    headers = {
        'Authorization': f'Bearer {service.fallback_api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': service.fallback_model,
        'prompt': sticker_prompt,
        'negative_prompt': negative_prompt,
        'image_size': '512x512',  # 表情包使用较小尺寸
        'batch_size': 1,
        'num_inference_steps': 20,
        'guidance_scale': 7.5
    }
    
    try:
        response = requests.post(
            f'{service.fallback_api_base}/images/generations',
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            try:
                result = response.json()
            except json.JSONDecodeError:
                return False, '', f'API返回无效JSON: {response.text[:100] if response.text else "空响应"}'
            images = result.get('images', result.get('data', []))
            if images:
                image_url = images[0].get('url', '')
                if image_url:
                    # 下载并保存到本地（避免外部URL过期）
                    if user_id:
                        try:
                            local_url = _download_and_save_image(
                                image_url=image_url,
                                user_id=user_id,
                                prompt=prompt,
                                model=service.fallback_model,
                                image_type='sticker',
                                image_size='512x512'
                            )
                            if local_url:
                                return True, local_url, ''
                        except Exception as e:
                            current_app.logger.warning(f'Failed to save sticker locally: {e}')
                    return True, image_url, ''
            return False, '', '未返回图片'
        else:
            error_msg = ''
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', str(error_data))
            except:
                error_msg = response.text[:200]
            return False, '', f'生成失败: {error_msg}'
            
    except Exception as e:
        return False, '', f'生成失败: {str(e)}'


def generate_with_fallback(prompt: str, user_id: int, 
                           negative_prompt: str = None,
                           image_size: str = '1024x1024',
                           use_fallback: bool = False) -> ImageGenerationResult:
    """
    带备用API的图片生成（主API次数用完后自动切换）
    
    Args:
        prompt: 提示词
        user_id: 用户ID
        negative_prompt: 负面提示词
        image_size: 图片尺寸
        use_fallback: 是否强制使用备用API
        
    Returns:
        ImageGenerationResult: 生成结果
    """
    service = get_image_service()
    
    # 检查是否需要使用备用API
    if use_fallback:
        return _generate_with_fallback_api(service, prompt, negative_prompt, image_size)
    
    # 尝试主API
    result = service.generate_image(
        prompt=prompt,
        negative_prompt=negative_prompt,
        image_size=image_size,
        batch_size=1
    )
    
    # 如果主API失败，尝试备用API
    if not result.success and service.fallback_api_key:
        current_app.logger.info(f'Primary API failed, trying fallback: {result.message}')
        return _generate_with_fallback_api(service, prompt, negative_prompt, image_size)
    
    return result


def _generate_with_fallback_api(service: ImageService, prompt: str, 
                                 negative_prompt: str, image_size: str) -> ImageGenerationResult:
    """使用备用API生成图片"""
    headers = {
        'Authorization': f'Bearer {service.fallback_api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': service.fallback_model,
        'prompt': prompt,
        'image_size': image_size,
        'batch_size': 1,
        'num_inference_steps': 20,
        'guidance_scale': 7.5
    }
    
    if negative_prompt:
        payload['negative_prompt'] = negative_prompt
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f'{service.fallback_api_base}/images/generations',
            headers=headers,
            json=payload,
            timeout=120
        )
        
        inference_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            try:
                result = response.json()
            except json.JSONDecodeError:
                return ImageGenerationResult(
                    success=False,
                    message=f'API返回无效JSON: {response.text[:200] if response.text else "空响应"}',
                    images=[],
                    seed=None,
                    inference_time=round(inference_time, 2)
                )
            images = []
            
            for img_data in result.get('images', result.get('data', [])):
                image_info = {'url': img_data.get('url', '')}
                if 'seed' in img_data:
                    image_info['seed'] = img_data['seed']
                images.append(image_info)
            
            return ImageGenerationResult(
                success=True,
                message='图片生成成功（备用API）',
                images=images,
                seed=result.get('seed'),
                inference_time=round(inference_time, 2)
            )
        else:
            error_msg = ''
            try:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', '')
            except:
                error_msg = response.text[:200]
            
            return ImageGenerationResult(
                success=False,
                message=f'备用API生成失败: {error_msg}',
                images=[],
                seed=None,
                inference_time=round(inference_time, 2)
            )
            
    except Exception as e:
        return ImageGenerationResult(
            success=False,
            message=f'备用API错误: {str(e)}',
            images=[],
            seed=None,
            inference_time=0
        )
