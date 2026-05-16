"""
时区处理工具
解决Linux服务器UTC时间与本地时间的差异问题
"""
from datetime import datetime, timezone, timedelta
import os

# 默认时区偏移（中国时区 UTC+8）
DEFAULT_TIMEZONE_OFFSET = 8

def get_timezone_offset():
    """获取配置的时区偏移量"""
    offset = os.getenv('TIMEZONE_OFFSET', str(DEFAULT_TIMEZONE_OFFSET))
    try:
        return int(offset)
    except ValueError:
        return DEFAULT_TIMEZONE_OFFSET

def get_local_timezone():
    """获取本地时区"""
    offset = get_timezone_offset()
    return timezone(timedelta(hours=offset))

def utc_now():
    """获取当前UTC时间"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def local_now():
    """获取当前本地时间"""
    offset = get_timezone_offset()
    return datetime.now(timezone.utc) + timedelta(hours=offset)

def utc_to_local(dt):
    """将UTC时间转换为本地时间"""
    if dt is None:
        return None
    offset = get_timezone_offset()
    return dt + timedelta(hours=offset)

def local_to_utc(dt):
    """将本地时间转换为UTC时间"""
    if dt is None:
        return None
    offset = get_timezone_offset()
    return dt - timedelta(hours=offset)

def format_local_datetime(dt, format='%Y-%m-%d %H:%M'):
    """格式化为本地时间字符串"""
    if not dt:
        return ''
    local_dt = utc_to_local(dt)
    return local_dt.strftime(format)

def time_ago_local(dt):
    """返回相对时间（基于本地时间）"""
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
