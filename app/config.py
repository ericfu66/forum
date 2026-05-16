import os
from datetime import timedelta
from dotenv import load_dotenv

# override=True 确保 .env 文件中的值覆盖系统环境变量
load_dotenv(override=True)


class Config:
    """基础配置类"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    # 数据库配置
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI', f'sqlite:///{os.path.join(BASE_DIR, "forum.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # SQLAlchemy 连接池配置
    # 注意：SQLite 不支持这些参数，仅在 PostgreSQL 时使用
    # 当检测到 PostgreSQL 连接时，这些选项会在 app/__init__.py 中动态设置
    SQLALCHEMY_ENGINE_OPTIONS = {}

    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_API_BASE = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_MAX_TOKENS = int(os.getenv('DEEPSEEK_MAX_TOKENS', 2000))
    DEEPSEEK_TEMPERATURE = float(os.getenv('DEEPSEEK_TEMPERATURE', 0.7))

    # 图像生成API配置
    AI_IMAGE_API_KEY = os.getenv('AI_IMAGE_API_KEY', '')
    AI_IMAGE_API_BASE = os.getenv('AI_IMAGE_API_BASE', '')
    AI_IMAGE_FALLBACK_API_KEY = os.getenv('AI_IMAGE_FALLBACK_API_KEY', '')
    AI_IMAGE_FALLBACK_API_BASE = os.getenv('AI_IMAGE_FALLBACK_API_BASE', '')

    # 视觉理解API配置
    VISION_API_KEY = os.getenv('VISION_API_KEY', '')
    VISION_API_BASE = os.getenv('VISION_API_BASE', '')

    # Embedding向量化配置
    EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY', '')
    EMBEDDING_API_BASE = os.getenv('EMBEDDING_API_BASE', '')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-large-zh-v1.5')
    EMBEDDING_DIMENSIONS = int(os.getenv('EMBEDDING_DIMENSIONS', 1024))

    # 联网搜索配置
    TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '')

    # AI功能开关
    AI_ROAST_ENABLED = os.getenv('AI_ROAST_ENABLED', 'true').lower() == 'true'
    AI_ROAST_PROBABILITY = float(os.getenv('AI_ROAST_PROBABILITY', 0.1))
    AI_CHAT_ENABLED = os.getenv('AI_CHAT_ENABLED', 'true').lower() == 'true'
    AI_WRITE_ENABLED = os.getenv('AI_WRITE_ENABLED', 'true').lower() == 'true'
    AI_IMAGE_ENABLED = os.getenv('AI_IMAGE_ENABLED', 'true').lower() == 'true'

    # AI系统提示词
    AI_ROAST_SYSTEM_PROMPT = os.getenv(
        'AI_ROAST_SYSTEM_PROMPT',
        '你是一个幽默风趣的AI评论员，喜欢吐槽但保持友善。'
    )
    AI_CHAT_SYSTEM_PROMPT = os.getenv(
        'AI_CHAT_SYSTEM_PROMPT',
        '你是一个乐于助人的AI助手。'
    )
    AI_WRITE_SYSTEM_PROMPT = os.getenv(
        'AI_WRITE_SYSTEM_PROMPT',
        '你是一个专业的内容创作者。'
    )

    # 速率限制
    AI_RATE_LIMIT_PER_HOUR = int(os.getenv('AI_RATE_LIMIT_PER_HOUR', 20))
    AI_RATE_LIMIT_PER_DAY = int(os.getenv('AI_RATE_LIMIT_PER_DAY', 100))

    # 上传配置
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # 会话配置
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.getenv('PERMANENT_SESSION_LIFETIME', 604800)))

    # 分页配置
    POSTS_PER_PAGE = 20
    COMMENTS_PER_PAGE = 50
    USERS_PER_PAGE = 30

    # Redis 配置
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Celery 配置
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')

    # 对话摘要阈值
    DIALOG_SUMMARY_THRESHOLD = int(os.getenv('DIALOG_SUMMARY_THRESHOLD', 30))

    # CSRF配置
    WTF_CSRF_ENABLED = os.getenv('WTF_CSRF_ENABLED', 'True').lower() == 'true'
    WTF_CSRF_TIME_LIMIT = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))

    # SocketIO配置
    SOCKETIO_MESSAGE_QUEUE = os.getenv('SOCKETIO_MESSAGE_QUEUE', '')

    # 用户等级/积分配置
    LEVEL_CONFIG = {
        1: {'name': '初心者', 'min_exp': 0},
        2: {'name': '学徒', 'min_exp': 50},
        3: {'name': '探索者', 'min_exp': 150},
        4: {'name': '学者', 'min_exp': 300},
        5: {'name': 'Contributor', 'min_exp': 500},
        6: {'name': '达人', 'min_exp': 800},
        7: {'name': '专家', 'min_exp': 1200},
        8: {'name': '大师', 'min_exp': 1800},
        9: {'name': '传奇', 'min_exp': 2500},
        10: {'name': '神话', 'min_exp': 3500},
    }

    # 经验值获取规则
    EXP_RULES = {
        'post': 10,
        'comment': 5,
        'like_received': 2,
        'daily_login': 5,
    }


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
