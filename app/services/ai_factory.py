"""
AI服务工厂 - 根据模块创建对应配置的AI服务实例
支持OpenAI通用协议，处理模块配置继承逻辑
"""
import requests
import time
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass

from app.services.config_service import (
    get_ai_global_config,
    get_ai_module_config,
    get_effective_ai_config,
    validate_ai_config,
    ValidationResult,
    AI_MODULE_SPECIFIC_DEFAULTS
)


@dataclass
class ConnectionTestResult:
    """API连接测试结果"""
    success: bool
    message: str
    model_info: Dict[str, Any]
    response_time: float  # 毫秒


class AIServiceFactory:
    """AI服务工厂 - 根据模块创建对应配置的AI服务实例"""
    
    # 支持的模块列表
    SUPPORTED_MODULES = ['moderation', 'chat', 'write', 'roast', 'image', 'vision']
    
    @staticmethod
    def get_config(module: str) -> Dict[str, Any]:
        """
        获取指定模块的有效配置（处理use_global逻辑）
        
        Args:
            module: 模块名称 (moderation, chat, write, roast, image, vision)
            
        Returns:
            有效的配置字典
            
        Raises:
            ValueError: 如果模块名称无效
        """
        if module not in AIServiceFactory.SUPPORTED_MODULES:
            raise ValueError(f"不支持的AI模块: {module}. 支持的模块: {AIServiceFactory.SUPPORTED_MODULES}")
        
        return get_effective_ai_config(module)
    
    @staticmethod
    def get_module_config(module: str) -> Dict[str, Any]:
        """
        获取模块的原始配置（不处理use_global）
        
        Args:
            module: 模块名称
            
        Returns:
            模块配置字典
        """
        if module not in AIServiceFactory.SUPPORTED_MODULES:
            raise ValueError(f"不支持的AI模块: {module}")
        
        return get_ai_module_config(module)
    
    @staticmethod
    def get_global_config() -> Dict[str, Any]:
        """
        获取全局AI配置
        
        Returns:
            全局配置字典
        """
        return get_ai_global_config()
    
    @staticmethod
    def get_service(module: str):
        """
        获取指定模块的AI服务实例
        
        Args:
            module: 模块名称
            
        Returns:
            配置好的AIService实例
        """
        from app.services.ai_service import AIService
        import logging
        logger = logging.getLogger(__name__)
        
        config = AIServiceFactory.get_config(module)
        logger.info(f"AIServiceFactory.get_service({module}): api_base={config.get('api_base')}, model={config.get('model')}")
        return AIService(config)
    
    @staticmethod
    def validate_module_config(module: str, config: Dict[str, Any]) -> ValidationResult:
        """
        验证模块配置是否有效
        
        Args:
            module: 模块名称
            config: 配置字典
            
        Returns:
            ValidationResult: 验证结果
        """
        # 如果使用全局配置，不需要验证模块自身的必填字段
        if config.get('use_global', True):
            return ValidationResult(valid=True, field='')
        
        # 不使用全局配置时，验证必填字段
        return validate_ai_config(config, require_all=True)
    
    @staticmethod
    def test_connection(config: Dict[str, Any], timeout: int = 10) -> ConnectionTestResult:
        """
        测试API连接
        
        Args:
            config: API配置字典，包含api_base, api_key, model等
            timeout: 超时时间（秒）
            
        Returns:
            ConnectionTestResult: 测试结果
        """
        api_base = config.get('api_base', '').rstrip('/')
        api_key = config.get('api_key', '')
        model = config.get('model', '')
        
        # 基本验证
        if not api_base:
            return ConnectionTestResult(
                success=False,
                message='API地址不能为空',
                model_info={},
                response_time=0
            )
        
        if not api_key:
            return ConnectionTestResult(
                success=False,
                message='API密钥不能为空',
                model_info={},
                response_time=0
            )
        
        if not model:
            return ConnectionTestResult(
                success=False,
                message='模型名称不能为空',
                model_info={},
                response_time=0
            )
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # 发送简单的测试请求
        payload = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': 'Hi'}
            ],
            'max_tokens': 5,
            'temperature': 0
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f'{api_base}/chat/completions',
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            if response.status_code == 200:
                result = response.json()
                model_info = {
                    'model': result.get('model', model),
                    'id': result.get('id', ''),
                    'usage': result.get('usage', {}),
                }
                return ConnectionTestResult(
                    success=True,
                    message='连接成功',
                    model_info=model_info,
                    response_time=round(response_time, 2)
                )
            elif response.status_code == 401:
                return ConnectionTestResult(
                    success=False,
                    message='API密钥无效',
                    model_info={},
                    response_time=round(response_time, 2)
                )
            elif response.status_code == 404:
                return ConnectionTestResult(
                    success=False,
                    message='模型不存在或不可用',
                    model_info={},
                    response_time=round(response_time, 2)
                )
            elif response.status_code == 429:
                return ConnectionTestResult(
                    success=False,
                    message='请求过于频繁，请稍后再试',
                    model_info={},
                    response_time=round(response_time, 2)
                )
            else:
                error_msg = ''
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', '')
                except:
                    error_msg = response.text[:200] if response.text else ''
                
                return ConnectionTestResult(
                    success=False,
                    message=f'请求失败 ({response.status_code}): {error_msg}',
                    model_info={},
                    response_time=round(response_time, 2)
                )
                
        except requests.exceptions.Timeout:
            return ConnectionTestResult(
                success=False,
                message='连接超时，请检查API地址',
                model_info={},
                response_time=timeout * 1000
            )
        except requests.exceptions.ConnectionError:
            return ConnectionTestResult(
                success=False,
                message='无法连接到API服务器，请检查API地址',
                model_info={},
                response_time=0
            )
        except requests.exceptions.RequestException as e:
            return ConnectionTestResult(
                success=False,
                message=f'请求错误: {str(e)}',
                model_info={},
                response_time=0
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f'未知错误: {str(e)}',
                model_info={},
                response_time=0
            )
    
    @staticmethod
    def test_image_api(config: Dict[str, Any], timeout: int = 30) -> ConnectionTestResult:
        """
        测试图片生成API连接（SiliconFlow格式）
        
        Args:
            config: API配置字典
            timeout: 超时时间（秒）
            
        Returns:
            ConnectionTestResult: 测试结果
        """
        api_base = config.get('api_base', '').rstrip('/')
        api_key = config.get('api_key', '')
        model = config.get('model', '')
        
        if not api_base or not api_key or not model:
            return ConnectionTestResult(
                success=False,
                message='API地址、密钥和模型名称不能为空',
                model_info={},
                response_time=0
            )
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # 发送简单的测试请求（使用最小参数）
        payload = {
            'model': model,
            'prompt': 'test',
            'image_size': '512x512',
            'num_inference_steps': 1,  # 最少步数
        }
        
        start_time = time.time()
        
        try:
            # 只验证API是否可达，不实际生成图片
            # 通过发送一个会快速失败的请求来测试连接
            response = requests.post(
                f'{api_base}/images/generations',
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ConnectionTestResult(
                    success=True,
                    message='图片生成API连接成功',
                    model_info={'model': model},
                    response_time=round(response_time, 2)
                )
            elif response.status_code == 401:
                return ConnectionTestResult(
                    success=False,
                    message='API密钥无效',
                    model_info={},
                    response_time=round(response_time, 2)
                )
            elif response.status_code == 404:
                return ConnectionTestResult(
                    success=False,
                    message='模型不存在或API端点不正确',
                    model_info={},
                    response_time=round(response_time, 2)
                )
            else:
                error_msg = ''
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', '')
                except:
                    error_msg = response.text[:200] if response.text else ''
                
                return ConnectionTestResult(
                    success=False,
                    message=f'请求失败 ({response.status_code}): {error_msg}',
                    model_info={},
                    response_time=round(response_time, 2)
                )
                
        except requests.exceptions.Timeout:
            return ConnectionTestResult(
                success=False,
                message='连接超时',
                model_info={},
                response_time=timeout * 1000
            )
        except requests.exceptions.ConnectionError:
            return ConnectionTestResult(
                success=False,
                message='无法连接到API服务器',
                model_info={},
                response_time=0
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f'错误: {str(e)}',
                model_info={},
                response_time=0
            )
    
    @staticmethod
    def get_all_module_status() -> Dict[str, Dict[str, Any]]:
        """
        获取所有模块的配置状态
        
        Returns:
            各模块的配置状态字典
        """
        result = {}
        
        for module in AIServiceFactory.SUPPORTED_MODULES:
            try:
                module_config = get_ai_module_config(module)
                effective_config = get_effective_ai_config(module)
                
                result[module] = {
                    'use_global': module_config.get('use_global', True),
                    'has_custom_config': not module_config.get('use_global', True),
                    'model': effective_config.get('model', ''),
                    'api_base': effective_config.get('api_base', ''),
                    'is_configured': bool(effective_config.get('api_key')),
                }
            except Exception as e:
                result[module] = {
                    'use_global': True,
                    'has_custom_config': False,
                    'model': '',
                    'api_base': '',
                    'is_configured': False,
                    'error': str(e)
                }
        
        return result


def get_ai_factory() -> AIServiceFactory:
    """获取AI服务工厂实例"""
    return AIServiceFactory()
