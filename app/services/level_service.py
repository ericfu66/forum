"""
用户等级与积分服务
"""
from flask import current_app
from app.extensions import db


def get_level_config(level):
    """获取等级配置"""
    config = current_app.config.get('LEVEL_CONFIG', {})
    return config.get(level, {'name': '未知', 'min_exp': 0})


def add_exp(user, action):
    """
    为用户增加经验值

    Args:
        user: User 实例
        action: 动作类型 ('post', 'comment', 'like_received', 'daily_login')

    Returns:
        (gained_exp, is_level_up): 获得的经验值和是否升级
    """
    rules = current_app.config.get('EXP_RULES', {})
    exp_gain = rules.get(action, 0)
    if exp_gain <= 0:
        return 0, False

    is_level_up = user.add_exp(exp_gain)
    db.session.commit()
    return exp_gain, is_level_up


def get_user_level_progress(user):
    """获取用户等级进度信息"""
    level_config = current_app.config.get('LEVEL_CONFIG', {})
    current = level_config.get(user.level, {'name': '未知', 'min_exp': 0})
    next_lvl = level_config.get(user.level + 1)

    progress = {
        'level': user.level,
        'name': current['name'],
        'current_exp': user.exp,
        'level_min_exp': current['min_exp'],
    }

    if next_lvl:
        progress['next_level'] = user.level + 1
        progress['next_name'] = next_lvl['name']
        progress['next_exp'] = next_lvl['min_exp']
        progress['percentage'] = round(
            (user.exp - current['min_exp']) /
            (next_lvl['min_exp'] - current['min_exp']) * 100, 1
        )
    else:
        progress['next_level'] = None
        progress['next_name'] = '已满级'
        progress['next_exp'] = None
        progress['percentage'] = 100

    return progress
