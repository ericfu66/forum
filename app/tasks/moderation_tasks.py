"""
内容审核异步任务
使用AI对用户发布的内容进行自动审核
"""
import logging

logger = logging.getLogger(__name__)

_celery = None

def _get_celery():
    global _celery
    if _celery is None:
        from app.celery import make_celery
        _celery = make_celery()
    return _celery


def moderate_content_task(content, content_type, content_id, title, author_id):
    """内容审核任务包装"""
    celery = _get_celery()

    @celery.task(bind=True, max_retries=2, default_retry_delay=30, name='tasks.moderate_content')
    def _task(self, content, content_type, content_id, title, author_id):
        from app.services.moderation_service import ModerationService

        try:
            service = ModerationService()
            result = service.moderate_content(content, content_type, title, author_id)

            service.log_moderation(
                content_type=content_type,
                content_id=content_id,
                content_preview=content[:200] if content else '',
                result=result,
                author_id=author_id
            )

            service._process_moderation_result(content_type, content_id, result, author_id)

        except Exception as e:
            logger.error(f'Async moderation error: {e}')
            # 失败时设置为待人工审核
            try:
                service = ModerationService()
                service._set_content_pending(content_type, content_id)
            except Exception:
                pass
            raise self.retry(exc=e)

    return _task.delay(content, content_type, content_id, title, author_id)
