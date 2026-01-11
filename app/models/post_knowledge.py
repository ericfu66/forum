"""
帖子知识库模型
存储帖子内容和向量表示，供AI助手语义搜索使用
"""
import json
from typing import Optional, List
from app.extensions import db
from datetime import datetime


class PostKnowledge(db.Model):
    """帖子知识库 - 支持向量存储的语义搜索"""
    __tablename__ = 'post_knowledge'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text)  # JSON 序列化的向量，可为空
    board_name = db.Column(db.String(50))
    author_name = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    post = db.relationship('Post', backref=db.backref('knowledge', uselist=False))

    def get_embedding_vector(self) -> Optional[List[float]]:
        """
        获取向量（反序列化）
        
        Returns:
            向量列表，如果没有向量则返回 None
        """
        if not self.embedding:
            return None
        try:
            return json.loads(self.embedding)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def set_embedding_vector(self, vector: Optional[List[float]]):
        """
        设置向量（序列化存储）
        
        Args:
            vector: 向量列表，如果为 None 则清除向量
        """
        if vector is None:
            self.embedding = None
        else:
            self.embedding = json.dumps(vector)
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'post_id': self.post_id,
            'title': self.title,
            'content': self.content,
            'has_embedding': self.embedding is not None,
            'board_name': self.board_name,
            'author_name': self.author_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_context(self):
        """转换为AI上下文格式"""
        context = f"【帖子】{self.title}\n"
        if self.board_name:
            context += f"【版块】{self.board_name}\n"
        if self.author_name:
            context += f"【作者】{self.author_name}\n"
        context += f"【内容】{self.content}\n"
        return context

    @staticmethod
    def create(post_id, title, content, board_name=None, author_name=None, 
               embedding: Optional[List[float]] = None):
        """
        创建知识条目
        
        Args:
            post_id: 帖子ID
            title: 标题
            content: 内容
            board_name: 版块名称
            author_name: 作者名称
            embedding: 向量（可选）
        """
        knowledge = PostKnowledge(
            post_id=post_id,
            title=title,
            content=content,
            board_name=board_name,
            author_name=author_name,
        )
        if embedding:
            knowledge.set_embedding_vector(embedding)
        db.session.add(knowledge)
        db.session.commit()
        return knowledge

    @staticmethod
    def find_by_post_id(post_id):
        """通过帖子ID查找"""
        return PostKnowledge.query.filter_by(post_id=post_id).first()

    @staticmethod
    def search(keyword, limit=5):
        """搜索相关帖子知识（关键词搜索）"""
        search_pattern = f'%{keyword}%'
        results = PostKnowledge.query.filter(
            db.or_(
                PostKnowledge.title.like(search_pattern),
                PostKnowledge.content.like(search_pattern),
            )
        ).order_by(PostKnowledge.created_at.desc()).limit(limit).all()
        return results

    @staticmethod
    def get_all_with_embeddings() -> List['PostKnowledge']:
        """获取所有有向量的条目"""
        return PostKnowledge.query.filter(
            PostKnowledge.embedding.isnot(None),
            PostKnowledge.embedding != ''
        ).all()
    
    @staticmethod
    def get_entries_without_embeddings() -> List['PostKnowledge']:
        """获取所有没有向量的条目"""
        return PostKnowledge.query.filter(
            db.or_(
                PostKnowledge.embedding.is_(None),
                PostKnowledge.embedding == ''
            )
        ).all()

    @staticmethod
    def get_recent(limit=10):
        """获取最近的知识条目"""
        return PostKnowledge.query.order_by(
            PostKnowledge.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def get_optimized_knowledge(time_limit=50, like_limit=10):
        """
        获取优化后的知识库内容
        - 按时间顺序的前N条帖子
        - 点赞数最高的前M条帖子
        去重后返回
        """
        from app.models.post import Post
        
        # 获取按时间排序的帖子ID
        recent_posts = Post.query.filter_by(status='published').order_by(
            Post.created_at.desc()
        ).limit(time_limit).all()
        recent_ids = {p.id for p in recent_posts}
        
        # 获取点赞最高的帖子ID
        top_liked_posts = Post.query.filter_by(status='published').order_by(
            Post.like_count.desc()
        ).limit(like_limit).all()
        liked_ids = {p.id for p in top_liked_posts}
        
        # 合并ID（去重）
        all_ids = recent_ids | liked_ids
        
        if not all_ids:
            return []
        
        # 获取对应的知识条目
        return PostKnowledge.query.filter(
            PostKnowledge.post_id.in_(all_ids)
        ).all()
    
    @staticmethod
    def get_stats() -> dict:
        """
        获取知识库统计信息
        
        Returns:
            包含统计信息的字典
        """
        total = PostKnowledge.query.count()
        vectorized = PostKnowledge.query.filter(
            PostKnowledge.embedding.isnot(None),
            PostKnowledge.embedding != ''
        ).count()
        
        return {
            'total_count': total,
            'vectorized_count': vectorized,
            'non_vectorized_count': total - vectorized,
        }
