"""
装饰器工具
包含登录验证、权限验证等装饰器
"""
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin():
            flash('需要管理员权限', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def verified_required(f):
    """邮箱验证装饰器（预留）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_verified:
            flash('请先验证邮箱', 'warning')
            return redirect(url_for('auth.verify_email'))
        return f(*args, **kwargs)
    return decorated_function
