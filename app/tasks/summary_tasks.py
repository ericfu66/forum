"""
帖子摘要异步任务
为帖子生成AI摘要
"""
import logging
import threading

logger = logging.getLogger(__name__)

_celery = None

def _get_celery():
    global _celery
    if _celery is None:
        from app.celery import make_celery
        _celery = make_celery()
    return _celery


def generate_post_summary_async(post_id):
    """触发异步摘要生成，带线程回退"""
    try:
        celery = _get_celery()

        @celery.task(bind=True, max_retries=2, default_retry_delay=30, name='tasks.generate_post_summary')
        def _task(self, post_id):
            from app.models.post import Post
            from app.services.ai_service import get_ai_service
            from app.extensions import db

            post = Post.query.get(post_id)
            if not post or post.summary:
                return

            ai = get_ai_service('write')
            content_preview = post.content[:2000]
            summary = ai.generate_simple(
                f"请用中文为以下帖子生成一个简洁的摘要（2-3句话，不超过150字）：\n\n"
                f"标题：{post.title}\n内容：{content_preview}"
            )

            if summary:
                post.summary = summary
                db.session.commit()

        _task.delay(post_id)

    except Exception:
        # Celery不可用时回退到线程
        from flask import current_app
        app = current_app._get_current_object()

        def _do():
            with app.app_context():
                try:
                    from app.models.post import Post
                    from app.services.ai_service import get_ai_service
                    from app.extensions import db

                    post = Post.query.get(post_id)
                    if not post or post.summary:
                        return

                    ai = get_ai_service('write')
                    summary = ai.generate_simple(
                        f"请用中文为以下帖子生成摘要（2-3句话，不超过150字）：\n"
                        f"标题：{post.title}\n内容：{post.content[:2000]}"
                    )
                    if summary:
                        post.summary = summary
                        db.session.commit()
                except Exception as e:
                    logger.error(f'Post summary generation failed: {e}')

        thread = threading.Thread(target=_do, daemon=True)
        thread.start()
