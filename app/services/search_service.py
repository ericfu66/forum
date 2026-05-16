"""
搜索服务 - 支持Tavily搜索API
用于AI对话的联网搜索功能
"""
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from flask import current_app


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    content: str
    url: str
    score: float = 0.0


@dataclass
class SearchResponse:
    """搜索响应"""
    success: bool
    results: List[SearchResult]
    answer: str = ''  # Tavily的AI摘要答案
    message: str = ''


class SearchService:
    """Tavily搜索服务"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._get_api_key()
        self.api_base = 'https://api.tavily.com'
    
    def _get_api_key(self) -> str:
        """从配置获取API密钥"""
        try:
            json_config = current_app.config.get('JSON_CONFIG', {})
            search_config = json_config.get('search', {})
            return search_config.get('tavily_api_key', '')
        except:
            return ''
    
    def _get_config(self) -> dict:
        """获取搜索配置"""
        try:
            json_config = current_app.config.get('JSON_CONFIG', {})
            return json_config.get('search', {})
        except:
            return {}
    
    def search(self, query: str, max_results: int = 5, 
               include_answer: bool = True,
               search_depth: str = 'basic') -> SearchResponse:
        """
        执行Tavily搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数 (1-10)
            include_answer: 是否包含AI摘要答案
            search_depth: 搜索深度 'basic' 或 'advanced'
            
        Returns:
            SearchResponse: 搜索响应
        """
        if not self.api_key:
            return SearchResponse(
                success=False,
                results=[],
                message='搜索API密钥未配置'
            )
        
        try:
            response = requests.post(
                f'{self.api_base}/search',
                json={
                    'api_key': self.api_key,
                    'query': query,
                    'max_results': min(max_results, 10),
                    'include_answer': include_answer,
                    'search_depth': search_depth
                },
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                results = [
                    SearchResult(
                        title=r.get('title', ''),
                        content=r.get('content', ''),
                        url=r.get('url', ''),
                        score=r.get('score', 0.0)
                    )
                    for r in data.get('results', [])
                ]
                
                return SearchResponse(
                    success=True,
                    results=results,
                    answer=data.get('answer', '')
                )
            
            elif response.status_code == 401:
                return SearchResponse(
                    success=False,
                    results=[],
                    message='搜索API密钥无效'
                )
            else:
                error_msg = response.json().get('error', response.text[:200])
                return SearchResponse(
                    success=False,
                    results=[],
                    message=f'搜索失败: {error_msg}'
                )
                
        except requests.exceptions.Timeout:
            return SearchResponse(
                success=False,
                results=[],
                message='搜索超时，请稍后重试'
            )
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Search error: {str(e)}')
            return SearchResponse(
                success=False,
                results=[],
                message=f'搜索请求失败: {str(e)}'
            )
        except Exception as e:
            current_app.logger.error(f'Search error: {str(e)}')
            return SearchResponse(
                success=False,
                results=[],
                message=f'搜索错误: {str(e)}'
            )
    
    def format_results_for_context(self, results: List[SearchResult], 
                                   answer: str = '') -> str:
        """
        将搜索结果格式化为上下文字符串
        
        Args:
            results: 搜索结果列表
            answer: Tavily的AI摘要答案
            
        Returns:
            str: 格式化的上下文字符串
        """
        if not results and not answer:
            return ''
        
        context_parts = ['[网络搜索结果]']
        
        if answer:
            context_parts.append(f'摘要: {answer}\n')
        
        for i, r in enumerate(results, 1):
            context_parts.append(f'{i}. {r.title}')
            context_parts.append(f'   {r.content[:300]}...' if len(r.content) > 300 else f'   {r.content}')
            context_parts.append(f'   来源: {r.url}\n')
        
        context_parts.append('[搜索结果结束]')
        
        return '\n'.join(context_parts)


def get_search_service() -> SearchService:
    """获取搜索服务实例"""
    return SearchService()
