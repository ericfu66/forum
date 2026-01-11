"""
向量化服务
调用 SiliconFlow Embedding API 将文本转换为向量
"""
import json
import logging
import requests
from typing import Optional, List, Dict, Any
from flask import current_app


logger = logging.getLogger(__name__)


class EmbeddingService:
    """向量化服务 - 调用 SiliconFlow Embedding API"""
    
    # 默认配置
    DEFAULT_API_BASE = 'https://api.siliconflow.cn/v1'
    DEFAULT_MODEL = 'BAAI/bge-large-zh-v1.5'
    DEFAULT_DIMENSIONS = 1024
    DEFAULT_TIMEOUT = 15  # 降低超时时间，避免阻塞对话
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化向量化服务
        
        Args:
            config: 配置字典，包含 api_base, api_key, model, dimensions
                   如果为 None，则从应用配置中读取
        """
        self._config = config
        self._cached_config: Optional[Dict[str, Any]] = None
    
    def _get_config(self) -> Dict[str, Any]:
        """获取配置（带缓存）"""
        if self._config is not None:
            return self._config
        
        if self._cached_config is not None:
            return self._cached_config
        
        # 从应用配置中读取
        self._cached_config = self._load_config_from_app()
        return self._cached_config
    
    def _load_config_from_app(self) -> Dict[str, Any]:
        """从 Flask 应用配置中加载 embedding 配置"""
        config = {
            'api_base': self.DEFAULT_API_BASE,
            'api_key': '',
            'model': self.DEFAULT_MODEL,
            'dimensions': self.DEFAULT_DIMENSIONS,
            'timeout': self.DEFAULT_TIMEOUT,
        }
        
        try:
            # 尝试从 config.json 的 embedding 部分读取
            json_config = current_app.config.get('JSON_CONFIG', {})
            embedding_config = json_config.get('embedding', {})
            
            if embedding_config:
                config['api_base'] = embedding_config.get('api_base', config['api_base'])
                config['api_key'] = embedding_config.get('api_key', config['api_key'])
                config['model'] = embedding_config.get('model', config['model'])
                config['dimensions'] = embedding_config.get('dimensions', config['dimensions'])
                config['timeout'] = embedding_config.get('timeout', config['timeout'])
            
            # 如果 embedding 配置中没有 api_key，尝试使用 image 模块的 api_key（都是 SiliconFlow）
            if not config['api_key']:
                ai_modules = json_config.get('ai_modules', {})
                image_config = ai_modules.get('image', {})
                if image_config.get('api_key'):
                    config['api_key'] = image_config['api_key']
                    logger.info("Using image module API key for embedding service")
                    
        except RuntimeError:
            # 没有应用上下文时使用默认配置
            pass
        
        return config
    
    def clear_config_cache(self):
        """清除配置缓存（配置更新后调用）"""
        self._cached_config = None
    
    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表，失败返回 None
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        result = self.embed_texts([text])
        if result and result[0] is not None:
            return result[0]
        return None
    
    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量将文本转换为向量
        
        Args:
            texts: 输入文本列表
            
        Returns:
            向量列表的列表，单个失败项为 None
        """
        if not texts:
            return []
        
        config = self._get_config()
        api_key = config.get('api_key', '')
        
        if not api_key:
            logger.error("Embedding API key not configured")
            return [None] * len(texts)
        
        api_base = config.get('api_base', self.DEFAULT_API_BASE)
        model = config.get('model', self.DEFAULT_MODEL)
        timeout = config.get('timeout', self.DEFAULT_TIMEOUT)
        
        # 过滤空文本，记录原始索引
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
                valid_indices.append(i)
        
        if not valid_texts:
            logger.warning("No valid texts provided for embedding")
            return [None] * len(texts)
        
        # 调用 API
        url = f"{api_base.rstrip('/')}/embeddings"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': model,
            'input': valid_texts,
            'encoding_format': 'float',
        }
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            embeddings = data.get('data', [])
            
            # 构建结果列表
            results: List[Optional[List[float]]] = [None] * len(texts)
            for item in embeddings:
                idx = item.get('index', 0)
                embedding = item.get('embedding', [])
                if idx < len(valid_indices):
                    original_idx = valid_indices[idx]
                    results[original_idx] = embedding
            
            logger.info(f"Successfully embedded {len(valid_texts)} texts")
            return results
            
        except requests.exceptions.Timeout:
            logger.error(f"Embedding API timeout after {timeout}s")
            return [None] * len(texts)
        except requests.exceptions.HTTPError as e:
            logger.error(f"Embedding API HTTP error: {e.response.status_code} - {e.response.text}")
            return [None] * len(texts)
        except requests.exceptions.RequestException as e:
            logger.error(f"Embedding API request error: {e}")
            return [None] * len(texts)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Embedding API response parse error: {e}")
            return [None] * len(texts)
        except Exception as e:
            logger.error(f"Unexpected error in embedding: {e}")
            return [None] * len(texts)


# 全局服务实例（延迟初始化）
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取向量化服务实例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    else:
        # 清除配置缓存，确保使用最新配置
        _embedding_service.clear_config_cache()
    return _embedding_service


def embed_text(text: str) -> Optional[List[float]]:
    """便捷函数：将单个文本转换为向量"""
    return get_embedding_service().embed_text(text)


def embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """便捷函数：批量将文本转换为向量"""
    return get_embedding_service().embed_texts(texts)


def get_knowledge_config() -> Dict[str, Any]:
    """
    获取知识库搜索配置
    
    Returns:
        包含搜索配置的字典
    """
    config = {
        'search_limit': 5,
        'similarity_threshold': 0.5,
        'max_context_chars': 8000,
    }
    
    try:
        json_config = current_app.config.get('JSON_CONFIG', {})
        knowledge_config = json_config.get('knowledge', {})
        
        if knowledge_config:
            config['search_limit'] = knowledge_config.get('search_limit', config['search_limit'])
            config['similarity_threshold'] = knowledge_config.get('similarity_threshold', config['similarity_threshold'])
            config['max_context_chars'] = knowledge_config.get('max_context_chars', config['max_context_chars'])
    except RuntimeError:
        pass
    
    return config
