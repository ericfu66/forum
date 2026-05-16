"""
知识库异步任务
将帖子内容向量化并存入知识库
"""
import logging

logger = logging.getLogger(__name__)

# 延迟初始化celery实例，避免循环导入
_celery = None

def _get_celery():
    global _celery
    if _celery is None:
        from app.celery import make_celery
        _celery = make_celery()
    return _celery


def process_post_knowledge_task(post_id, title, content, board_name, author_name):
    """处理帖子知识入库（Celery任务包装）"""
    celery = _get_celery()

    @celery.task(bind=True, max_retries=3, default_retry_delay=60, name='tasks.process_post_knowledge')
    def _task(self, post_id, title, content, board_name, author_name):
        from app.models.post_knowledge import PostKnowledge
        from app.services.embedding_service import embed_text

        try:
            existing = PostKnowledge.find_by_post_id(post_id)
            if existing:
                return

            text_for_embedding = f"{title}\n{content}"
            embedding = None

            try:
                embedding = embed_text(text_for_embedding)
                if embedding:
                    logger.info(f'Generated embedding for post {post_id}')
                else:
                    logger.warning(f'Failed to generate embedding for post {post_id}')
            except Exception as e:
                logger.error(f'Error generating embedding for post {post_id}: {e}')

            PostKnowledge.create(
                post_id=post_id,
                title=title,
                content=content,
                board_name=board_name,
                author_name=author_name,
                embedding=embedding
            )
            logger.info(f'Post knowledge created for post {post_id}')

        except Exception as e:
            logger.error(f'Error processing post knowledge for post {post_id}: {e}')
            raise self.retry(exc=e)

    return _task.delay(post_id, title, content, board_name, author_name)
