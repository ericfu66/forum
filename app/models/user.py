from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from datetime import datetime
import base64


def generate_default_avatar():
    """生成默认emoji头像"""
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <rect width="100" height="100" fill="#8b5cf6"/>
        <text x="50" y="65" font-size="50" text-anchor="middle">😀</text>
    </svg>'''
    svg_base64 = base64.b64encode(svg.encode()).decode()
    return f'data:image/svg+xml;base64,{svg_base64}'


class User(UserMixin, db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(500), default=generate_default_avatar())
    role = db.Column(db.String(20), default='user')  # user, admin, moderator
    bio = db.Column(db.Text, default='')
    is_verified = db.Column(db.Boolean, default=True)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # 关系
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    ai_dialogs = db.relationship('AIDialog', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """是否管理员"""
        return self.role == 'admin'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'avatar': self.avatar,
            'role': self.role,
            'bio': self.bio,
            'is_verified': self.is_verified,
            'is_banned': self.is_banned,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create(username, email, password, role='user'):
        """创建新用户"""
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def find_by_username(username):
        """通过用户名查找"""
        return User.query.filter_by(username=username).first()

    @staticmethod
    def find_by_email(email):
        """通过邮箱查找"""
        return User.query.filter_by(email=email).first()
