"""
AI随机触发器
用于在发帖/回复时随机触发AI吐槽功能
"""
import random
from flask import current_app


def ai_roast_trigger(func):
    """
    装饰器：在发帖/回复时随机触发AI吐槽

    使用方式：
    @ai_roast_trigger
    def create_post(...):
        # 创建帖子的逻辑
        ...
    """
    from functools import wraps
    from threading import Thread

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 执行原函数
        result = func(*args, **kwargs)

        # 检查是否启用AI吐槽
        if not current_app.config.get('AI_ROAST_ENABLED', False):
            return result

        # 获取触发概率
        probability = current_app.config.get('AI_ROAST_PROBABILITY', 0.1)

        # 随机决定是否触发
        if random.random() < probability:
            # 异步触发AI吐槽（避免阻塞主流程）
            thread = Thread(target=_trigger_ai_roast, args=(result,))
            thread.daemon = True
            thread.start()

        return result

    return wrapper


def _trigger_ai_roast(post_data):
    """
    实际的AI吐槽触发逻辑（在后台线程中执行）
    """
    try:
        from app.services.ai_service import get_ai_service
        from app.models.post import Post
        from app.models.comment import Comment
        from app.extensions import db

        # 使用roast模块配置
        ai_service = get_ai_service('roast')

        # 获取帖子信息
        if isinstance(post_data, dict):
            post_id = post_data.get('id')
        else:
            post_id = post_data.id

        if not post_id:
            return

        post = Post.query.get(post_id)
        if not post or post.ai_reply_triggered:
            return

        # 生成AI吐槽内容
        roast_content = ai_service.generate_roast(
            post_content=post.content,
            post_title=post.title
        )

        # 创建AI评论（无author_id，标识为AI生成）
        Comment.create(
            post_id=post_id,
            author_id=None,  # AI无真实用户ID
            content=roast_content,
            is_ai_generated=True
        )

        # 标记帖子已触发AI回复
        post.set_ai_triggered()

        current_app.logger.info(f'AI roast triggered for post {post_id}')

    except Exception as e:
        current_app.logger.error(f'AI roast trigger failed: {str(e)}')


def should_trigger_ai_roast(post_content: str, user_id: int = None) -> bool:
    """
    判断是否应该触发AI吐槽（更精细的控制逻辑）

    Args:
        post_content: 帖子内容
        user_id: 用户ID

    Returns:
        bool: 是否触发
    """
    # 检查全局开关
    if not current_app.config.get('AI_ROAST_ENABLED', False):
        return False

    # 检查内容长度（太短的内容不触发）
    min_length = 50
    if len(post_content) < min_length:
        return False

    # 随机概率判断
    probability = current_app.config.get('AI_ROAST_PROBABILITY', 0.1)
    return random.random() < probability


def trigger_ai_roast_manual(post_id: int) -> bool:
    """
    手动触发AI吐槽

    Args:
        post_id: 帖子ID

    Returns:
        bool: 是否成功触发
    """
    try:
        from app.models.post import Post
        from app.services.ai_service import get_ai_service
        from app.models.comment import Comment

        post = Post.query.get(post_id)
        if not post:
            return False

        # 使用roast模块配置
        ai_service = get_ai_service('roast')
        roast_content = ai_service.generate_roast(
            post_content=post.content,
            post_title=post.title
        )

        Comment.create(
            post_id=post_id,
            author_id=None,
            content=roast_content,
            is_ai_generated=True
        )

        post.set_ai_triggered()
        return True

    except Exception as e:
        current_app.logger.error(f'Manual AI roast failed: {str(e)}')
        return False
