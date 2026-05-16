from app.extensions import db
from datetime import datetime


class Board(db.Model):
    """版块模型"""
    __tablename__ = 'boards'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    icon = db.Column(db.String(10), default='📁')
    color = db.Column(db.String(20), default='#2196F3')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    posts = db.relationship('Post', backref='board', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def post_count(self):
        return self.posts.filter_by(status='published').count()

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'order': self.order,
            'is_active': self.is_active,
            'post_count': self.post_count,
        }

    @staticmethod
    def create(name, slug, description='', icon='📁', color='#2196F3', order=0):
        """创建新版块"""
        board = Board(
            name=name,
            slug=slug,
            description=description,
            icon=icon,
            color=color,
            order=order
        )
        db.session.add(board)
        db.session.commit()
        return board

    @staticmethod
    def find_all(active_only=True):
        """获取所有版块"""
        query = Board.query
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Board.order).all()

    @staticmethod
    def find_by_slug(slug):
        """通过slug查找版块"""
        return Board.query.filter_by(slug=slug).first()
