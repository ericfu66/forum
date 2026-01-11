from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# SQLAlchemy数据库实例
db = SQLAlchemy()

# Flask-Login
login_manager = LoginManager()


def init_extensions(app):
    """初始化所有扩展"""

    # 初始化SQLAlchemy
    db.init_app(app)

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


def create_tables(app):
    """创建数据库表"""
    with app.app_context():
        db.create_all()
