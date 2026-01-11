import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """基础配置类"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    # SQLite数据库配置
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI', f'sqlite:///{os.path.join(BASE_DIR, "forum.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_API_BASE = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com')
    DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
    DEEPSEEK_MAX_TOKENS = int(os.getenv('DEEPSEEK_MAX_TOKENS', 2000))
    DEEPSEEK_TEMPERATURE = float(os.getenv('DEEPSEEK_TEMPERATURE', 0.7))

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


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
