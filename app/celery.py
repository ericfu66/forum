"""
Celery应用工厂
Flask-Celery集成，支持应用上下文
"""
from celery import Celery


def make_celery(app=None):
    """创建Celery实例"""
    celery = Celery(__name__)
    celery.config_from_object('app.config', namespace='CELERY')

    if app:
        celery.conf.update(
            broker_url=app.config['CELERY_BROKER_URL'],
            result_backend=app.config['CELERY_RESULT_BACKEND'],
        )

        class ContextTask(celery.Task):
            """自动注入Flask应用上下文的Celery Task基类"""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask

    return celery
