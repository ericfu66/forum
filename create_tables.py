#!/usr/bin/env python
"""创建缺失的数据库表并执行必要的迁移"""
from app import create_app
from app.extensions import db
import sqlite3
import os

app = create_app()

def get_db_path():
    """获取数据库文件路径（从app配置推导）"""
    uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///forum.db')
    # sqlite:///relative.db -> relative.db, sqlite:///C:/abs.db -> C:/abs.db
    path = uri.replace('sqlite:///', '')
    # Flask 默认将 SQLite 放在 instance/ 目录
    if not os.path.isabs(path):
        path = os.path.join(app.instance_path, path)
    return path

DB_PATH = get_db_path()

def migrate_comments_status():
    """为comments表添加status列（如果不存在）"""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查status列是否存在
    cursor.execute("PRAGMA table_info(comments)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'status' not in columns:
        print("添加 status 列到 comments 表...")
        cursor.execute("ALTER TABLE comments ADD COLUMN status VARCHAR(20) DEFAULT 'published'")
        conn.commit()
        print("✓ status 列添加成功！")
    
    conn.close()


def migrate_post_knowledge_to_vector():
    """
    迁移 post_knowledge 表以支持向量存储
    - 添加 embedding 列（如果不存在）
    - 移除 summary 和 is_summarized 列（SQLite 不支持直接删除列，需要重建表）
    """
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查 post_knowledge 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='post_knowledge'")
    if not cursor.fetchone():
        print("post_knowledge 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return
    
    # 获取当前列信息
    cursor.execute("PRAGMA table_info(post_knowledge)")
    columns = {col[1]: col for col in cursor.fetchall()}
    
    # 检查是否存在需要移除的旧列
    has_old_columns = 'summary' in columns or 'is_summarized' in columns
    has_embedding = 'embedding' in columns
    
    # 如果没有旧列，只需要添加 embedding 列（如果不存在）
    if not has_old_columns:
        if not has_embedding:
            print("添加 embedding 列到 post_knowledge 表...")
            cursor.execute("ALTER TABLE post_knowledge ADD COLUMN embedding TEXT")
            conn.commit()
            print("✓ embedding 列添加成功！")
        else:
            print("post_knowledge 表结构已是最新")
        conn.close()
        return
    
    # 需要重建表来移除旧列
    print("开始迁移 post_knowledge 表（移除旧列）...")
    
    try:
        # SQLite 不支持直接删除列，需要重建表
        # 1. 创建新表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_knowledge_new (
                id INTEGER PRIMARY KEY,
                post_id INTEGER NOT NULL UNIQUE,
                title VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                board_name VARCHAR(50),
                author_name VARCHAR(50),
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        """)
        
        # 2. 复制数据（包含 embedding 列，如果存在的话）
        if has_embedding:
            cursor.execute("""
                INSERT INTO post_knowledge_new (id, post_id, title, content, embedding, board_name, author_name, created_at, updated_at)
                SELECT id, post_id, title, content, embedding, board_name, author_name, created_at, updated_at
                FROM post_knowledge
            """)
            print("  - 保留现有 embedding 数据")
        else:
            cursor.execute("""
                INSERT INTO post_knowledge_new (id, post_id, title, content, board_name, author_name, created_at, updated_at)
                SELECT id, post_id, title, content, board_name, author_name, created_at, updated_at
                FROM post_knowledge
            """)
        
        # 3. 删除旧表
        cursor.execute("DROP TABLE post_knowledge")
        
        # 4. 重命名新表
        cursor.execute("ALTER TABLE post_knowledge_new RENAME TO post_knowledge")
        
        conn.commit()
        print("✓ post_knowledge 表迁移成功！")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ post_knowledge 表迁移失败: {e}")
    
    conn.close()


def migrate_novel_characters():
    """为 novel_characters 表添加新列（avatar_url, regex_rules）"""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novel_characters'")
    if not cursor.fetchone():
        print("novel_characters 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return
    
    # 获取当前列信息
    cursor.execute("PRAGMA table_info(novel_characters)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 添加 avatar_url 列
    if 'avatar_url' not in columns:
        print("添加 avatar_url 列到 novel_characters 表...")
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN avatar_url VARCHAR(500) DEFAULT ''")
        conn.commit()
        print("✓ avatar_url 列添加成功！")
    
    # 添加 regex_rules 列
    if 'regex_rules' not in columns:
        print("添加 regex_rules 列到 novel_characters 表...")
        cursor.execute("ALTER TABLE novel_characters ADD COLUMN regex_rules TEXT DEFAULT '[]'")
        conn.commit()
        print("✓ regex_rules 列添加成功！")
    
    conn.close()


def migrate_novel_user_presets():
    """为 novel_user_presets 表添加 is_override 列"""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novel_user_presets'")
    if not cursor.fetchone():
        print("novel_user_presets 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return
    
    # 获取当前列信息
    cursor.execute("PRAGMA table_info(novel_user_presets)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 添加 is_override 列
    if 'is_override' not in columns:
        print("添加 is_override 列到 novel_user_presets 表...")
        cursor.execute("ALTER TABLE novel_user_presets ADD COLUMN is_override BOOLEAN DEFAULT 0")
        conn.commit()
        print("✓ is_override 列添加成功！")
    
    conn.close()


def migrate_novel_preset_profiles():
    """为 novel_preset_profiles 表添加 regex_rules 列"""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novel_preset_profiles'")
    if not cursor.fetchone():
        print("novel_preset_profiles 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return
    
    # 获取当前列信息
    cursor.execute("PRAGMA table_info(novel_preset_profiles)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 添加 regex_rules 列
    if 'regex_rules' not in columns:
        print("添加 regex_rules 列到 novel_preset_profiles 表...")
        cursor.execute("ALTER TABLE novel_preset_profiles ADD COLUMN regex_rules TEXT DEFAULT '[]'")
        conn.commit()
        print("✓ regex_rules 列添加成功！")
    
    conn.close()


def migrate_posts_media_columns():
    """为 posts 表添加媒体附件列（images, audio_url）"""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
    if not cursor.fetchone():
        print("posts 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return
    
    # 获取当前列信息
    cursor.execute("PRAGMA table_info(posts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 添加 images 列
    if 'images' not in columns:
        print("添加 images 列到 posts 表...")
        cursor.execute("ALTER TABLE posts ADD COLUMN images TEXT DEFAULT '[]'")
        conn.commit()
        print("✓ images 列添加成功！")
    
    # 添加 audio_url 列
    if 'audio_url' not in columns:
        print("添加 audio_url 列到 posts 表...")
        cursor.execute("ALTER TABLE posts ADD COLUMN audio_url VARCHAR(500)")
        conn.commit()
        print("✓ audio_url 列添加成功！")
    
    conn.close()


def migrate_posts_add_summary():
    """为 posts 表添加 summary 列（帖子AI摘要）"""
    db_path = os.path.join('instance', 'forum.db')
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
    if not cursor.fetchone():
        print("posts 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return

    cursor.execute("PRAGMA table_info(posts)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'summary' not in columns:
        print("adding summary column to posts...")
        cursor.execute("ALTER TABLE posts ADD COLUMN summary TEXT")
        conn.commit()
        print("done: summary column added")

    conn.close()


def migrate_user_images_local_path():
    """为 user_images 表添加 local_path 列（用于本地存储图片）"""
    db_path = DB_PATH
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_images'")
    if not cursor.fetchone():
        print("user_images 表不存在，将由 SQLAlchemy 创建")
        conn.close()
        return
    
    # 获取当前列信息
    cursor.execute("PRAGMA table_info(user_images)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # 添加 local_path 列
    if 'local_path' not in columns:
        print("添加 local_path 列到 user_images 表...")
        cursor.execute("ALTER TABLE user_images ADD COLUMN local_path VARCHAR(200) DEFAULT ''")
        conn.commit()
        print("✓ local_path 列添加成功！")
    
    conn.close()


with app.app_context():
    # 执行迁移
    migrate_comments_status()
    migrate_post_knowledge_to_vector()
    migrate_novel_characters()
    migrate_novel_user_presets()
    migrate_novel_preset_profiles()
    migrate_posts_media_columns()
    migrate_posts_add_summary()
    migrate_user_images_local_path()
    # 创建新表
    db.create_all()
    print("[OK] database tables created")
    
    # 初始化默认小说角色
    from app.models.novel_dialog import NovelCharacter
    NovelCharacter.init_default_characters()
    print("[OK] default novel characters initialized")
