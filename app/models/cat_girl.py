"""
AI猫娘好友模型
系统内置的可爱AI聊天伙伴
"""
from app.extensions import db
from app.models.user import User
from datetime import datetime
import base64


# 猫娘角色配置（默认值）
DEFAULT_CAT_GIRL_CONFIG = {
    'username': '小樱',
    'email': 'sakura@system.local',
    'avatar': None,
    'bio': '喵~ 我是小樱，你的AI猫娘好友！有什么想聊的都可以告诉我哦~ (=^･ω･^=)',
    'role': 'system',
    'personality': {
        'name': '小樱',
        'name_en': 'Sakura',
        'traits': ['可爱', '活泼', '温柔', '偶尔傲娇'],
        'speech_patterns': [
            '句尾喜欢加"喵~"或"nya~"',
            '会用颜文字如 (=^･ω･^=)、(｡･ω･｡)、(◕ᴗ◕✿)',
            '偶尔撒娇或卖萌',
            '关心用户，会主动问候'
        ],
        'welcome_message': '''喵~ 欢迎来到论坛！我是小樱，你的AI猫娘好友~ (=^･ω･^=)

有什么想聊的都可以告诉我哦！无论是开心的事还是烦恼的事，小樱都会认真听的喵~

希望你在这里玩得开心！nya~ ✨'''
    }
}


def generate_cat_girl_avatar():
    """生成猫娘头像（可爱的猫耳SVG）"""
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
        <defs>
            <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#FFB6C1"/>
                <stop offset="100%" style="stop-color:#FF69B4"/>
            </linearGradient>
        </defs>
        <rect width="100" height="100" fill="url(#bg)" rx="50"/>
        <text x="50" y="65" font-size="45" text-anchor="middle">🐱</text>
    </svg>'''
    svg_base64 = base64.b64encode(svg.encode()).decode()
    return f'data:image/svg+xml;base64,{svg_base64}'


def get_cat_girl_config():
    """获取猫娘配置（从数据库或默认值）"""
    from flask import current_app
    
    # 尝试从JSON配置获取自定义名字
    json_config = current_app.config.get('JSON_CONFIG', {})
    cat_girl_config = json_config.get('cat_girl', {})
    
    config = DEFAULT_CAT_GIRL_CONFIG.copy()
    
    # 如果有自定义名字，更新配置
    if cat_girl_config.get('name'):
        custom_name = cat_girl_config['name']
        config['username'] = custom_name
        config['bio'] = f'喵~ 我是{custom_name}，你的AI猫娘好友！有什么想聊的都可以告诉我哦~ (=^･ω･^=)'
        config['personality']['name'] = custom_name
        config['personality']['welcome_message'] = f'''喵~ 欢迎来到论坛！我是{custom_name}，你的AI猫娘好友~ (=^･ω･^=)

有什么想聊的都可以告诉我哦！无论是开心的事还是烦恼的事，{custom_name}都会认真听的喵~

希望你在这里玩得开心！nya~ ✨'''
    
    return config


def get_or_create_cat_girl() -> User:
    """获取或创建猫娘系统用户"""
    config = get_cat_girl_config()
    
    # 先尝试通过role='system'查找猫娘
    cat_girl = User.query.filter_by(role='system', email='sakura@system.local').first()
    
    if not cat_girl:
        # 也尝试通过旧名字查找
        cat_girl = User.query.filter_by(username='小樱', role='system').first()
    
    if not cat_girl:
        # 创建猫娘用户
        cat_girl = User(
            username=config['username'],
            email='sakura@system.local',
            avatar=generate_cat_girl_avatar(),
            bio=config['bio'],
            role='system',
            is_verified=True,
            is_banned=False
        )
        import secrets
        cat_girl.set_password(secrets.token_hex(32))
        
        db.session.add(cat_girl)
        db.session.commit()
    else:
        # 更新猫娘名字（如果配置有变化）
        if cat_girl.username != config['username']:
            cat_girl.username = config['username']
            cat_girl.bio = config['bio']
            db.session.commit()
    
    return cat_girl


def update_cat_girl_name(new_name: str) -> bool:
    """更新猫娘名字（同时更新数据库和配置文件）"""
    if not new_name or len(new_name) > 20:
        return False
    
    from flask import current_app
    from app.services.config_service import ConfigService
    
    # 1. 更新数据库中的用户信息
    cat_girl = User.query.filter_by(role='system', email='sakura@system.local').first()
    if not cat_girl:
        cat_girl = User.query.filter_by(username='小樱', role='system').first()
    
    if cat_girl:
        cat_girl.username = new_name
        cat_girl.bio = f'喵~ 我是{new_name}，你的AI猫娘好友！有什么想聊的都可以告诉我哦~ (=^･ω･^=)'
        db.session.commit()
    else:
        return False
    
    # 2. 更新config.json配置文件
    try:
        config_service = ConfigService()
        config_service.update_json_config(
            updates={'name': new_name},
            section='cat_girl'
        )
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to update cat girl config: {str(e)}')
        # 即使配置文件更新失败，数据库已更新，返回True
        return True
        return True


def get_cat_girl_id() -> int:
    """获取猫娘用户ID"""
    cat_girl = get_or_create_cat_girl()
    return cat_girl.id


def is_cat_girl(user_id: int) -> bool:
    """检查是否是猫娘用户"""
    cat_girl = User.query.filter_by(role='system', email='sakura@system.local').first()
    if not cat_girl:
        cat_girl = User.query.filter_by(username='小樱', role='system').first()
    return cat_girl and cat_girl.id == user_id


def get_cat_girl_personality() -> dict:
    """获取猫娘人设配置"""
    config = get_cat_girl_config()
    return config['personality']


def get_welcome_message() -> str:
    """获取欢迎消息"""
    config = get_cat_girl_config()
    return config['personality']['welcome_message']
