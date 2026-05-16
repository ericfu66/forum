from app.extensions import db
from app.models.tag import post_tags
from datetime import datetime
import json


class Post(db.Model):
    """帖子模型"""
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    board_id = db.Column(db.Integer, db.ForeignKey('boards.id'), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_locked = db.Column(db.Boolean, default=False)
    is_ai_generated = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='published')  # draft, published, deleted
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    reply_count = db.Column(db.Integer, default=0)
    ai_reply_triggered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_reply_at = db.Column(db.DateTime)

    # 数据库索引优化
    __table_args__ = (
        db.Index('idx_post_status_board_created', 'status', 'board_id', 'created_at'),
        db.Index('idx_post_author_status', 'author_id', 'status'),
        db.Index('idx_post_pinned_status', 'is_pinned', 'status'),
        db.Index('idx_post_last_reply', 'last_reply_at'),
    )

    # 媒体附件字段
    images = db.Column(db.Text, default='[]')  # JSON数组存储图片URL列表
    audio_url = db.Column(db.String(500))  # 语音文件URL

    # AI摘要
    summary = db.Column(db.Text, nullable=True)

    # 关系
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    tags = db.relationship('Tag', secondary=post_tags, backref=db.backref('posts', lazy='dynamic'))

    def get_images(self):
        """获取图片列表"""
        try:
            return json.loads(self.images) if self.images else []
        except:
            return []
    
    def set_images(self, image_list):
        """设置图片列表"""
        self.images = json.dumps(image_list) if image_list else '[]'

    def to_dict(self, include_author=False, include_board=False):
        """转换为字典"""
        result = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'author_id': self.author_id,
            'board_id': self.board_id,
            'is_pinned': self.is_pinned,
            'is_locked': self.is_locked,
            'is_ai_generated': self.is_ai_generated,
            'status': self.status,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'reply_count': self.reply_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'images': self.get_images(),
            'audio_url': self.audio_url,
            'tags': [t.to_dict() for t in self.tags] if self.tags else [],
            'summary': self.summary,
        }

        if include_author and self.author:
            result['author'] = self.author.to_dict()

        if include_board and self.board:
            result['board'] = self.board.to_dict()

        return result

    @staticmethod
    def create(title, content, author_id, board_id, tags=None, is_ai_generated=False, images=None, audio_url=None):
        """创建新帖子"""
        post = Post(
            title=title,
            content=content,
            author_id=author_id,
            board_id=board_id,
            is_ai_generated=is_ai_generated,
            audio_url=audio_url
        )
        if images:
            post.set_images(images)
        db.session.add(post)
        db.session.flush()  # 获取post.id

        # 处理标签
        if tags:
            from app.models.tag import Tag
            for tag_name in tags:
                if isinstance(tag_name, str) and tag_name.strip():
                    tag = Tag.find_or_create(tag_name.strip())
                    if tag and tag not in post.tags:
                        post.tags.append(tag)
                        tag.post_count += 1

        db.session.commit()
        return post

    @staticmethod
    def find_by_id(post_id):
        """通过ID查找帖子"""
        return Post.query.get(post_id)

    @staticmethod
    def find_all(board_id=None, page=1, per_page=20, status='published'):
        """获取帖子列表（预加载作者和版块，避免N+1）"""
        from sqlalchemy.orm import joinedload
        query = Post.query.options(
            joinedload(Post.author),
            joinedload(Post.board)
        ).filter_by(status=status)

        if board_id:
            query = query.filter_by(board_id=board_id)

        # 排序：置顶优先，然后按时间倒序
        query = query.order_by(Post.is_pinned.desc(), Post.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return pagination.items, pagination.total

    def increment_view(self):
        """增加浏览次数"""
        self.view_count += 1
        db.session.commit()

    def increment_reply(self):
        """增加回复数"""
        self.reply_count += 1
        self.last_reply_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def set_ai_triggered(self):
        """标记AI已触发"""
        self.ai_reply_triggered = True
        db.session.commit()
