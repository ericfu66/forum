from app.extensions import db
from datetime import datetime


class Like(db.Model):
    """点赞模型"""
    __tablename__ = 'likes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)  # 帖子或评论ID
    target_type = db.Column(db.String(20), nullable=False)  # 'post' or 'comment'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
