from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_socketio import SocketIO
from flask import request, jsonify
import logging
import time

logger = logging.getLogger(__name__)

# SQLAlchemy数据库实例
db = SQLAlchemy()

# Flask-Login
login_manager = LoginManager()

# Flask-Migrate
migrate = Migrate()

# Flask-WTF CSRF
csrf = CSRFProtect()

# Flask-SocketIO
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

# Redis客户端（全局，由init_extensions初始化）
redis_client = None


class InMemoryCache:
    """Redis不可用时的内存缓存回退"""

    def __init__(self):
        self._store = {}
        self._ttls = {}

    def get(self, key):
        self._evict(key)
        val = self._store.get(key)
        return val if val is not None else None

    def set(self, key, value, ex=None):
        self._store[key] = value
        if ex:
            self._ttls[key] = time.time() + ex

    def delete(self, key):
        self._store.pop(key, None)
        self._ttls.pop(key, None)

    def incr(self, key):
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    def expire(self, key, seconds):
        self._ttls[key] = time.time() + seconds

    def ping(self):
        return True

    def _evict(self, key):
        if key in self._ttls and time.time() > self._ttls[key]:
            del self._store[key]
            del self._ttls[key]


def init_extensions(app):
    """初始化所有扩展"""
    global redis_client

    # 初始化SQLAlchemy
    db.init_app(app)

    # 初始化Flask-Migrate
    migrate.init_app(app, db)

    # 初始化Flask-WTF CSRF（豁免API路由）
    csrf.init_app(app)
    csrf.exempt_prefixes = ['/ai/api/', '/post/', '/messages/api/', '/admin/api/', '/auth/api/']

    # 初始化Flask-SocketIO
    socketio.init_app(app)

    # 初始化Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录'
    login_manager.login_message_category = 'info'

    # 设置user_loader回调
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        """处理未授权请求 - API请求返回JSON，页面请求重定向"""
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': '请先登录'}), 401
        from flask import redirect, url_for, flash
        flash('请先登录', 'info')
        return redirect(url_for('auth.login'))

    # 初始化Redis缓存
    try:
        import redis
        redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
        logger.info(f"Redis connected: {redis_url}")
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}), using in-memory cache fallback")
        redis_client = InMemoryCache()


def create_tables(app):
    """创建数据库表"""
    with app.app_context():
        db.create_all()
