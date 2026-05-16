"""
思维链解析器 - Think Model Parser
支持解析DeepSeek-R1、o1等模型的思维链内容
"""
import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ThinkingParseResult:
    """思维链解析结果"""
    has_thinking: bool
    thinking: str
    response: str
    pattern_type: str  # 'deepseek', 'generic', 'chinese', 'none'


# 思维链标签模式
THINK_PATTERNS = [
    # DeepSeek-R1 格式
    (r'<think>(.*?)</think>', 'deepseek'),
    # 通用格式
    (r'<thinking>(.*?)</thinking>', 'generic'),
    # 中文格式
    (r'\[思考\](.*?)\[/思考\]', 'chinese'),
    # 其他可能的格式
    (r'<thought>(.*?)</thought>', 'thought'),
    (r'\[thinking\](.*?)\[/thinking\]', 'bracket'),
]


class ThinkModelParser:
    """思维链解析器"""
    
    @staticmethod
    def parse(content: str) -> ThinkingParseResult:
        """
        解析思维链内容
        
        Args:
            content: AI响应内容
            
        Returns:
            ThinkingParseResult: 解析结果
        """
        if not content:
            return ThinkingParseResult(
                has_thinking=False,
                thinking='',
                response='',
                pattern_type='none'
            )
        
        # 尝试匹配各种模式
        for pattern, pattern_type in THINK_PATTERNS:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                thinking = match.group(1).strip()
                # 移除思维链部分，获取主要响应
                response = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE).strip()
                
                return ThinkingParseResult(
                    has_thinking=True,
                    thinking=thinking,
                    response=response,
                    pattern_type=pattern_type
                )
        
        # 没有找到思维链标签
        return ThinkingParseResult(
            has_thinking=False,
            thinking='',
            response=content.strip(),
            pattern_type='none'
        )
    
    @staticmethod
    def parse_streaming(content: str) -> Tuple[bool, str, str, bool]:
        """
        解析流式内容中的思维链（用于实时检测）
        
        Args:
            content: 当前累积的内容
            
        Returns:
            Tuple[bool, str, str, bool]: (是否有思维链, 思维链内容, 响应内容, 是否思维链完成)
        """
        # 检查是否有开始标签
        start_patterns = [
            ('<think>', '</think>', 'deepseek'),
            ('<thinking>', '</thinking>', 'generic'),
            ('[思考]', '[/思考]', 'chinese'),
            ('<thought>', '</thought>', 'thought'),
        ]
        
        for start_tag, end_tag, pattern_type in start_patterns:
            start_idx = content.lower().find(start_tag.lower())
            if start_idx != -1:
                end_idx = content.lower().find(end_tag.lower())
                
                if end_idx != -1:
                    # 思维链已完成
                    thinking = content[start_idx + len(start_tag):end_idx].strip()
                    response = (content[:start_idx] + content[end_idx + len(end_tag):]).strip()
                    return True, thinking, response, True
                else:
                    # 思维链进行中
                    thinking = content[start_idx + len(start_tag):].strip()
                    response = content[:start_idx].strip()
                    return True, thinking, response, False
        
        # 没有思维链
        return False, '', content, True
    
    @staticmethod
    def format_for_display(thinking: str, response: str, 
                           show_thinking: bool = True) -> str:
        """
        格式化显示内容
        
        Args:
            thinking: 思维链内容
            response: 主要响应
            show_thinking: 是否显示思维链
            
        Returns:
            str: 格式化后的内容
        """
        if not thinking or not show_thinking:
            return response
        
        # 格式化思维链（使用引用块样式）
        formatted_thinking = '\n'.join(f'> {line}' for line in thinking.split('\n'))
        
        return f"**💭 思考过程：**\n{formatted_thinking}\n\n**📝 回答：**\n{response}"
    
    @staticmethod
    def has_thinking_tags(content: str) -> bool:
        """
        检查内容是否包含思维链标签
        
        Args:
            content: 内容
            
        Returns:
            bool: 是否包含思维链标签
        """
        for pattern, _ in THINK_PATTERNS:
            if re.search(pattern, content, re.DOTALL | re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def extract_thinking_only(content: str) -> str:
        """
        仅提取思维链内容
        
        Args:
            content: AI响应内容
            
        Returns:
            str: 思维链内容（如果有）
        """
        result = ThinkModelParser.parse(content)
        return result.thinking
    
    @staticmethod
    def extract_response_only(content: str) -> str:
        """
        仅提取响应内容（移除思维链）
        
        Args:
            content: AI响应内容
            
        Returns:
            str: 响应内容
        """
        result = ThinkModelParser.parse(content)
        return result.response
    
    @staticmethod
    def to_dict(content: str) -> Dict[str, Any]:
        """
        解析并返回字典格式
        
        Args:
            content: AI响应内容
            
        Returns:
            Dict: 包含解析结果的字典
        """
        result = ThinkModelParser.parse(content)
        return {
            'has_thinking': result.has_thinking,
            'thinking': result.thinking,
            'response': result.response,
            'pattern_type': result.pattern_type
        }


def parse_thinking_content(content: str) -> Dict[str, Any]:
    """
    便捷函数：解析思维链内容
    
    Args:
        content: AI响应内容
        
    Returns:
        Dict: 解析结果
    """
    return ThinkModelParser.to_dict(content)


def has_thinking(content: str) -> bool:
    """
    便捷函数：检查是否有思维链
    
    Args:
        content: AI响应内容
        
    Returns:
        bool: 是否有思维链
    """
    return ThinkModelParser.has_thinking_tags(content)


def separate_thinking(content: str) -> Tuple[str, str]:
    """
    便捷函数：分离思维链和响应
    
    Args:
        content: AI响应内容
        
    Returns:
        Tuple[str, str]: (思维链, 响应)
    """
    result = ThinkModelParser.parse(content)
    return result.thinking, result.response
