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

    # 经验值/等级系统
    exp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)

    # 关系
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    ai_dialogs = db.relationship('AIDialog', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    # 关注关系
    following = db.relationship(
        'User', secondary='follows',
        primaryjoin='User.id==follows.c.follower_id',
        secondaryjoin='User.id==follows.c.followed_id',
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """是否管理员"""
        return self.role == 'admin'

    def follow(self, user):
        """关注用户"""
        if not self.is_following(user):
            self.following.append(user)

    def unfollow(self, user):
        """取消关注"""
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        """是否已关注某用户"""
        return self.following.filter_by(id=user.id).first() is not None

    def add_exp(self, amount):
        """增加经验值并检查升级"""
        from flask import current_app
        self.exp += amount
        # 检查是否满足升级条件
        level_config = current_app.config.get('LEVEL_CONFIG', {})
        new_level = self.level
        for lvl in sorted(level_config.keys(), reverse=True):
            if self.exp >= level_config[lvl]['min_exp']:
                new_level = lvl
                break
        if new_level > self.level:
            self.level = new_level
        return new_level > self.level  # 返回是否升级

    def get_level_name(self):
        """获取当前等级名称"""
        from flask import current_app
        level_config = current_app.config.get('LEVEL_CONFIG', {})
        return level_config.get(self.level, {}).get('name', '未知')

    def get_next_level_exp(self):
        """获取下一级所需经验"""
        from flask import current_app
        level_config = current_app.config.get('LEVEL_CONFIG', {})
        next_level = level_config.get(self.level + 1)
        if next_level:
            return next_level['min_exp']
        return None  # 已满级

    def to_dict(self, include_stats=False):
        """转换为字典"""
        result = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'avatar': self.avatar,
            'role': self.role,
            'bio': self.bio,
            'is_verified': self.is_verified,
            'is_banned': self.is_banned,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'level': self.level,
            'level_name': self.get_level_name(),
            'exp': self.exp,
        }
        if include_stats:
            result['post_count'] = self.posts.count()
            result['comment_count'] = self.comments.count()
            result['follower_count'] = self.followers.count()
            result['following_count'] = self.following.count()
            next_exp = self.get_next_level_exp()
            result['next_level_exp'] = next_exp
            result['exp_progress'] = round(
                (self.exp / next_exp * 100), 1
            ) if next_exp else 100
        return result

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


# 关注关联表
class Follow(db.Model):
    """关注关系模型"""
    __tablename__ = 'follows'

    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 索引优化
    __table_args__ = (
        db.Index('idx_follow_follower', 'follower_id'),
        db.Index('idx_follow_followed', 'followed_id'),
    )
