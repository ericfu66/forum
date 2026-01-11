from flask import g, request
from flask_login import current_user


def inject_config():
    """注入配置到所有模板"""
    from flask import current_app

    config = current_app.config.get('JSON_CONFIG', {}).get('site', {})
    ai_config = current_app.config

    return {
        'site_name': config.get('name', 'AI Forum'),
        'site_description': config.get('description', ''),
        'ai_roast_enabled': ai_config.get('AI_ROAST_ENABLED', False),
        'ai_chat_enabled': ai_config.get('AI_CHAT_ENABLED', False),
        'ai_write_enabled': ai_config.get('AI_WRITE_ENABLED', False),
        'ai_image_enabled': ai_config.get('AI_IMAGE_ENABLED', False),
    }
