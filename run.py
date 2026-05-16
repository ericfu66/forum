#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Forum - 应用入口文件
一个带有AI功能的现代化论坛系统
"""
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db, socketio
from app.models import Board
from app.models.user import User

# 创建Flask应用
app = create_app(os.getenv('FLASK_ENV', 'development'))

# 初始化Celery
from app.celery import make_celery
celery = make_celery(app)


@app.shell_context_processor
def make_shell_context():
    """Shell上下文：方便在 flask shell 中使用"""
    return {
        'app': app,
        'db': db,
        'User': User,
        'Board': Board,
    }


@app.cli.command()
def init_db():
    """初始化数据库 - 创建表和默认版块"""
    print("正在初始化数据库...")

    # 创建所有表
    from app.extensions import create_tables
    create_tables(app)

    # 检查是否已有版块
    existing = Board.query.count()
    if existing > 0:
        print(f"数据库已有 {existing} 个版块，跳过初始化。")
        return

    # 创建默认版块
    boards = [
        Board(name='💬 综合讨论', slug='general', description='畅所欲言，分享你的想法',
               icon='💬', color='#2196F3', order=1),
        Board(name='💻 技术交流', slug='tech', description='探讨编程、技术相关话题',
               icon='💻', color='#4CAF50', order=2),
        Board(name='🤖 AI专区', slug='ai', description='人工智能、机器学习相关讨论',
               icon='🤖', color='#9C27B0', order=3),
        Board(name='📮 建议反馈', slug='feedback', description='社区建议和问题反馈',
               icon='📮', color='#FF9800', order=4),
    ]

    for board in boards:
        db.session.add(board)

    db.session.commit()
    print("✓ 数据库初始化完成！")
    print(f"✓ 创建了 {len(boards)} 个版块")


@app.cli.command()
def create_admin():
    """创建管理员账户"""
    print("\n=== 创建管理员账户 ===")
    username = input("用户名: ").strip()
    email = input("邮箱: ").strip()
    password = input("密码: ").strip()

    if not username or not email or not password:
        print("❌ 输入不能为空")
        return

    # 检查是否已存在
    if User.find_by_username(username):
        print("❌ 用户名已存在")
        return

    if User.find_by_email(email):
        print("❌ 邮箱已被注册")
        return

    # 创建管理员
    user = User(username=username, email=email, role='admin')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    print(f"\n✓ 管理员账户创建成功！")
    print(f"  用户名: {username}")
    print(f"  邮箱: {email}")
    print(f"  ID: {user.id}")


@app.cli.command()
def routes():
    """显示所有路由"""
    from flask import current_app

    print("\n=== 路由列表 ===\n")
    for rule in current_app.url_map.iter_rules():
        methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
        print(f"{rule.rule:50s} {methods:20s} {rule.endpoint}")


if __name__ == '__main__':
    # 开发环境运行（使用SocketIO）
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
