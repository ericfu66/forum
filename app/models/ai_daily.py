"""
AI每日内容模型
存储每日生成的序言、运势等内容
"""
from app.extensions import db
from datetime import datetime, date


class AIDailyContent(db.Model):
    """AI每日内容"""
    __tablename__ = 'ai_daily_content'

    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), nullable=False)  # quote, fortune_xxx, writing_prompt
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    date_key = db.Column(db.Date, default=date.today)

    @staticmethod
    def create(content_type, content):
        """创建新的每日内容"""
        daily = AIDailyContent(
            content_type=content_type,
            content=content,
            date_key=date.today()
        )
        db.session.add(daily)
        db.session.commit()
        return daily

    @staticmethod
    def get_today(content_type):
        """获取今日的内容"""
        today = date.today()
        return AIDailyContent.query.filter_by(
            content_type=content_type,
            date_key=today
        ).first()

    @staticmethod
    def cleanup_old(days=7):
        """清理旧数据"""
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=days)
        AIDailyContent.query.filter(AIDailyContent.date_key < cutoff).delete()
        db.session.commit()
