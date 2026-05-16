"""
自定义知识库模型
存储用户上传的自定义知识内容，供AI助手语义搜索使用
"""
import json
from typing import Optional, List
from app.extensions import db
from datetime import datetime


class CustomKnowledge(db.Model):
    """自定义知识库 - 支持文件上传和手动添加"""
    __tablename__ = 'custom_knowledge'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text)  # JSON 序列化的向量
    source_type = db.Column(db.String(20), default='manual')  # manual, file
    source_name = db.Column(db.String(200))  # 原始文件名
    category = db.Column(db.String(50))  # 分类标签
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # 关系
    creator = db.relationship('User', backref='custom_knowledge')

    def get_embedding_vector(self) -> Optional[List[float]]:
        """获取向量"""
        if not self.embedding:
            return None
        try:
            return json.loads(self.embedding)
        except (json.JSONDecodeError, TypeError):
            return None
    
    def set_embedding_vector(self, vector: Optional[List[float]]):
        """设置向量"""
        if vector is None:
            self.embedding = None
        else:
            self.embedding = json.dumps(vector)
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content[:500] + '...' if len(self.content) > 500 else self.content,
            'content_length': len(self.content),
            'has_embedding': self.embedding is not None,
            'source_type': self.source_type,
            'source_name': self.source_name,
            'category': self.category,
            'created_by': self.created_by,
            'creator_name': self.creator.username if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active,
        }

    def to_context(self):
        """转换为AI上下文格式"""
        context = f"【知识】{self.title}\n"
        if self.category:
            context += f"【分类】{self.category}\n"
        context += f"【内容】{self.content}\n"
        return context

    @staticmethod
    def create(title, content, source_type='manual', source_name=None, 
               category=None, created_by=None, embedding=None):
        """创建知识条目"""
        knowledge = CustomKnowledge(
            title=title,
            content=content,
            source_type=source_type,
            source_name=source_name,
            category=category,
            created_by=created_by,
        )
        if embedding:
            knowledge.set_embedding_vector(embedding)
        db.session.add(knowledge)
        db.session.commit()
        return knowledge

    @staticmethod
    def get_all_active_with_embeddings() -> List['CustomKnowledge']:
        """获取所有激活且有向量的条目"""
        return CustomKnowledge.query.filter(
            CustomKnowledge.is_active == True,
            CustomKnowledge.embedding.isnot(None),
            CustomKnowledge.embedding != ''
        ).all()

    @staticmethod
    def search(keyword, limit=5):
        """关键词搜索"""
        search_pattern = f'%{keyword}%'
        return CustomKnowledge.query.filter(
            CustomKnowledge.is_active == True,
            db.or_(
                CustomKnowledge.title.like(search_pattern),
                CustomKnowledge.content.like(search_pattern),
            )
        ).order_by(CustomKnowledge.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_stats() -> dict:
        """获取统计信息"""
        total = CustomKnowledge.query.filter_by(is_active=True).count()
        vectorized = CustomKnowledge.query.filter(
            CustomKnowledge.is_active == True,
            CustomKnowledge.embedding.isnot(None),
            CustomKnowledge.embedding != ''
        ).count()
        
        return {
            'custom_total': total,
            'custom_vectorized': vectorized,
            'custom_non_vectorized': total - vectorized,
        }
