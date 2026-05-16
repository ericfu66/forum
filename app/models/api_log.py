"""
API调用日志模型 - 用于AI服务的速率限制
"""
from datetime import datetime
from app.extensions import db


class APILog(db.Model):
    """API调用日志"""
    __tablename__ = 'api_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    endpoint = db.Column(db.String(100), nullable=False)  # 'chat', 'roast', 'write'
    model = db.Column(db.String(50), nullable=False)  # 'deepseek-chat'
    tokens_used = db.Column(db.Integer, default=0)
    response_time = db.Column(db.Float, default=0)  # 毫秒
    status = db.Column(db.String(20), default='success')  # 'success', 'error'
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    user = db.relationship('User', backref='api_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'endpoint': self.endpoint,
            'model': self.model,
            'tokens_used': self.tokens_used,
            'response_time': self.response_time,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def create(cls, user_id, endpoint, model, tokens_used=0, response_time=0,
               status='success', error_message=''):
        """创建API日志"""
        # 确保 user_id 是整数类型
        user_id = int(user_id) if user_id else None
        
        log = cls(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            tokens_used=tokens_used,
            response_time=response_time,
            status=status,
            error_message=error_message
        )
        db.session.add(log)
        db.session.commit()
        return log

    @classmethod
    def count_by_user(cls, user_id, time_range='hour'):
        """统计用户指定时间范围内的调用次数"""
        from datetime import timedelta

        now = datetime.utcnow()
        if time_range == 'hour':
            start_time = now - timedelta(hours=1)
        elif time_range == 'day':
            start_time = now - timedelta(days=1)
        else:
            start_time = now - timedelta(hours=1)

        # 确保 user_id 是整数类型
        user_id = int(user_id) if user_id else None

        return cls.query.filter(
            cls.user_id == user_id,
            cls.status == 'success',
            cls.created_at >= start_time
        ).count()
