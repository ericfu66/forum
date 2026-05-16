# 工具函数模块
from datetime import datetime
from app.utils.timezone import utc_to_local, local_now


def format_datetime(dt, format='%Y-%m-%d %H:%M'):
    """格式化日期时间（转换为本地时间）"""
    if not dt:
        return ''
    if isinstance(dt, datetime):
        local_dt = utc_to_local(dt)
        return local_dt.strftime(format)
    return str(dt)


def time_ago(dt):
    """返回相对时间（如"3小时前"）- 基于本地时间"""
    if not dt:
        return ''

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
        except ValueError:
            return str(dt)
    elif not isinstance(dt, datetime):
        return str(dt)

    # 使用本地时间计算差值
    now = local_now().replace(tzinfo=None)
    local_dt = utc_to_local(dt)
    diff = now - local_dt

    seconds = diff.total_seconds()

    if seconds < 0:
        return '刚刚'
    elif seconds < 60:
        return '刚刚'
    elif seconds < 3600:
        return f'{int(seconds / 60)}分钟前'
    elif seconds < 86400:
        return f'{int(seconds / 3600)}小时前'
    elif seconds < 2592000:
        return f'{int(seconds / 86400)}天前'
    else:
        return local_dt.strftime('%Y-%m-%d')
