from flask import g, request
from flask_login import current_user


def inject_config():
    """注入配置到所有模板"""
    from flask import current_app
    from app.models.board import Board

    config = current_app.config.get('JSON_CONFIG', {}).get('site', {})
    ai_config = current_app.config

    # Get boards for sidebar navigation
    try:
        boards = Board.find_all(active_only=True)
        boards_list = [b.to_dict() for b in boards]
    except:
        boards_list = []

    return {
        'site_name': config.get('name', 'AI Forum'),
        'site_description': config.get('description', ''),
        'ai_roast_enabled': ai_config.get('AI_ROAST_ENABLED', False),
        'ai_chat_enabled': ai_config.get('AI_CHAT_ENABLED', False),
        'ai_write_enabled': ai_config.get('AI_WRITE_ENABLED', False),
        'ai_image_enabled': ai_config.get('AI_IMAGE_ENABLED', False),
        'boards': boards_list,
    }
