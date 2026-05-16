from app.extensions import db
from datetime import datetime


class Comment(db.Model):
    """评论模型"""
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # AI评论可为空
    content = db.Column(db.Text, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'))
    is_ai_generated = db.Column(db.Boolean, default=False)
    like_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='published')  # pending, published, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 自引用关系（用于嵌套回复）
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    # 数据库索引优化
    __table_args__ = (
        db.Index('idx_comment_post_status_created', 'post_id', 'status', 'created_at'),
        db.Index('idx_comment_author', 'author_id'),
        db.Index('idx_comment_parent', 'parent_id'),
    )

    def to_dict(self, include_author=False):
        """转换为字典"""
        result = {
            'id': self.id,
            'post_id': self.post_id,
            'author_id': self.author_id,
            'content': self.content,
            'parent_id': self.parent_id,
            'is_ai_generated': self.is_ai_generated,
            'like_count': self.like_count,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if include_author:
            if self.author:
                result['author'] = self.author.to_dict()
            elif self.is_ai_generated:
                result['author'] = {
                    'username': 'AI助手',
                    'avatar': '/static/images/ai-avatar.png',
                    'is_ai': True
                }

        return result

    @staticmethod
    def create(post_id, author_id, content, parent_id=None, is_ai_generated=False, status='published'):
        """创建新评论"""
        from app.models.post import Post  # 延迟导入避免循环引用

        comment = Comment(
            post_id=post_id,
            author_id=author_id,
            content=content,
            parent_id=parent_id,
            is_ai_generated=is_ai_generated,
            status=status
        )
        db.session.add(comment)
        db.session.commit()

        # 只有已发布的评论才更新帖子回复数
        if status == 'published':
            post = Post.query.get(post_id)
            if post:
                post.increment_reply()

        return comment

    @staticmethod
    def find_by_post(post_id, page=1, per_page=50):
        """获取帖子的评论列表（只显示已发布的）"""
        query = Comment.query.filter_by(post_id=post_id, parent_id=None, status='published')
        pagination = query.order_by(Comment.created_at.asc()).paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total
