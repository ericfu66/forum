"""
用户图片库模型
"""
from app.extensions import db
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple


class UserImage(db.Model):
    """用户图片库"""
    __tablename__ = 'user_images'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    image_url = db.Column(db.String(500), default='')  # 原始URL（可能过期）
    local_path = db.Column(db.String(200), default='')  # 本地存储路径
    prompt = db.Column(db.Text, default='')  # 生成提示词
    negative_prompt = db.Column(db.Text, default='')  # 负面提示词
    model = db.Column(db.String(100), default='')  # 使用的模型
    image_type = db.Column(db.String(20), nullable=False, default='generated')  # 'generated' | 'uploaded'
    image_size = db.Column(db.String(20), default='')  # 图片尺寸，如 '1024x1024'
    seed = db.Column(db.Integer)  # 生成种子
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # 关系
    user = db.relationship('User', backref=db.backref('images', lazy='dynamic'))

    # 创建复合索引
    __table_args__ = (
        db.Index('idx_user_images_user_created', 'user_id', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'image_url': self.image_url,
            'local_path': self.local_path,
            'prompt': self.prompt,
            'negative_prompt': self.negative_prompt,
            'model': self.model,
            'image_type': self.image_type,
            'image_size': self.image_size,
            'seed': self.seed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create(user_id: int, image_url: str = '', local_path: str = '',
               prompt: str = '', negative_prompt: str = '', model: str = '',
               image_type: str = 'generated', image_size: str = '',
               seed: int = None) -> 'UserImage':
        """
        创建图片记录
        
        Args:
            user_id: 用户ID
            image_url: 原始图片URL
            local_path: 本地存储路径
            prompt: 生成提示词
            negative_prompt: 负面提示词
            model: 使用的模型
            image_type: 图片类型 ('generated' | 'uploaded')
            image_size: 图片尺寸
            seed: 生成种子
            
        Returns:
            UserImage: 创建的图片记录
        """
        image = UserImage(
            user_id=user_id,
            image_url=image_url,
            local_path=local_path,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            image_type=image_type,
            image_size=image_size,
            seed=seed
        )
        db.session.add(image)
        db.session.commit()
        return image

    @staticmethod
    def find_by_id(image_id: int) -> Optional['UserImage']:
        """通过ID查找图片"""
        return UserImage.query.get(image_id)

    @staticmethod
    def find_by_user(user_id: int, page: int = 1, per_page: int = 20,
                     image_type: str = None) -> Tuple[List['UserImage'], int]:
        """
        获取用户的图片列表（分页）
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            image_type: 图片类型筛选
            
        Returns:
            Tuple[List[UserImage], int]: (图片列表, 总数)
        """
        query = UserImage.query.filter_by(user_id=user_id)
        if image_type:
            query = query.filter_by(image_type=image_type)
        
        query = query.order_by(UserImage.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return pagination.items, pagination.total

    @staticmethod
    def count_by_user(user_id: int) -> int:
        """获取用户的图片数量"""
        return UserImage.query.filter_by(user_id=user_id).count()

    def update_local_path(self, local_path: str) -> 'UserImage':
        """更新本地存储路径"""
        self.local_path = local_path
        db.session.commit()
        return self

    def delete(self) -> bool:
        """删除图片记录"""
        try:
            db.session.delete(self)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def get_recent(user_id: int, limit: int = 10) -> List['UserImage']:
        """获取用户最近的图片"""
        return UserImage.query.filter_by(user_id=user_id)\
            .order_by(UserImage.created_at.desc())\
            .limit(limit)\
            .all()

    @staticmethod
    def count_today_generated(user_id: int) -> int:
        """
        统计用户今日生成的图片数量
        
        Args:
            user_id: 用户ID
            
        Returns:
            int: 今日生成的图片数量
        """
        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        return UserImage.query.filter(
            UserImage.user_id == user_id,
            UserImage.image_type == 'generated',
            UserImage.created_at >= today_start
        ).count()
