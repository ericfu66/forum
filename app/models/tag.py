from app.extensions import db
from datetime import datetime


# 多对多关联表
post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True),
)


class Tag(db.Model):
    """标签模型"""
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    post_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'post_count': self.post_count,
        }

    @staticmethod
    def find_or_create(name):
        """查找或创建标签"""
        name = name.strip()[:50]
        if not name:
            return None
        slug = name.lower().replace(' ', '-').replace('_', '-')
        # 移除特殊字符生成slug
        import re
        slug = re.sub(r'[^\w一-鿿-]', '', slug)
        if not slug:
            slug = str(hash(name))

        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name, slug=slug)
            db.session.add(tag)
            db.session.flush()
        return tag

    @staticmethod
    def find_by_slug(slug):
        """通过slug查找标签"""
        return Tag.query.filter_by(slug=slug).first()

    @staticmethod
    def find_all(limit=50):
        """获取热门标签"""
        return Tag.query.order_by(Tag.post_count.desc()).limit(limit).all()
