"""
标签服务
AI智能标签生成和管理
"""
import json
import logging

logger = logging.getLogger(__name__)


def generate_tags_ai(title, content, max_tags=5):
    """
    使用AI生成帖子标签

    Args:
        title: 帖子标题
        content: 帖子内容
        max_tags: 最大标签数

    Returns:
        list: 标签列表
    """
    from app.services.ai_service import get_ai_service

    ai = get_ai_service('write')
    prompt = f"""请为以下帖子生成{max_tags}个最相关的中文标签。

标题：{title}
内容：{content[:1000]}

要求：
- 标签应简洁（2-4个字）
- 能准确反映帖子主题
- 直接输出JSON数组格式，如：["标签1", "标签2", "标签3"]
- 不要输出其他内容"""

    try:
        result = ai.generate_simple(prompt)
        result = result.strip()
        # 清理可能的markdown代码块标记
        if result.startswith('```'):
            lines = result.split('\n')
            result = '\n'.join(lines[1:-1])
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        result = result.strip()

        tags = json.loads(result)
        if isinstance(tags, list):
            return [str(t).strip() for t in tags if t and str(t).strip()][:max_tags]
        return []
    except Exception as e:
        logger.warning(f'AI tag generation failed: {e}')
        return []


def merge_tags(user_tags, ai_tags, max_total=8):
    """
    合并用户标签和AI标签，去重

    Args:
        user_tags: 用户提供的标签列表
        ai_tags: AI生成的标签列表
        max_total: 最大标签总数

    Returns:
        list: 合并后的标签列表
    """
    seen = set()
    merged = []
    for tag in user_tags + ai_tags:
        tag = tag.strip() if isinstance(tag, str) else str(tag).strip()
        if tag and tag not in seen:
            seen.add(tag)
            merged.append(tag)
    return merged[:max_total]
