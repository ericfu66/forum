"""
猫娘自动回复异步任务
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


def auto_reply_task(user_id, user_message, message_id=None):
    """猫娘自动回复任务包装"""
    celery = _get_celery()

    @celery.task(bind=True, max_retries=2, default_retry_delay=10, name='tasks.cat_girl_auto_reply')
    def _task(self, user_id, user_message, message_id):
        try:
            from app.services.cat_girl_service import CatGirlService
            from app.models.message import Message
            from app.models.cat_girl import get_cat_girl_id

            service = CatGirlService()
            cat_girl_id = get_cat_girl_id()
            conversation_history = service._get_conversation_history(user_id, cat_girl_id)
            reply = service.generate_response(user_message, conversation_history)

            Message.create(
                sender_id=cat_girl_id,
                recipient_id=user_id,
                message_type='private',
                content=reply
            )

        except Exception as e:
            logger.error(f'Cat girl auto reply error: {e}')
            raise self.retry(exc=e)

    return _task.delay(user_id, user_message, message_id)
