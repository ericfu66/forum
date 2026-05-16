"""
AI小说区控制器
处理小说RP对话功能
"""
from flask import Blueprint, render_template, request, jsonify, Response, stream_with_context, current_app, abort
from flask_login import login_required, current_user
from app.services.novel_service import get_novel_service, NOVEL_PRESET_PROMPTS, PRESET_ORDER
from app.models.novel_dialog import NovelDialog, NovelCharacter, NovelUserPreset, NovelPresetProfile
from app.models.user_settings import UserSettings
from app.extensions import db
from werkzeug.utils import secure_filename
import os
import time
import uuid
import re

novel_bp = Blueprint('novel', __name__)


def is_novel_enabled():
    """检查AI小说功能是否启用"""
    json_config = current_app.config.get('JSON_CONFIG', {})
    features = json_config.get('features', {})
    # 检查AI总开关和小说开关
    ai_enabled = features.get('ai_features_enabled', True)
    novel_enabled = features.get('ai_novel_enabled', True)
    return ai_enabled and novel_enabled


# ============ 页面路由 ============

@novel_bp.route('/')
@login_required
def index():
    """AI小说区主页"""
    # 获取用户的对话列表
    dialogs, _ = NovelDialog.find_by_user(current_user.id, page=1, per_page=20)
    
    # 获取可用角色
    system_characters = NovelCharacter.get_system_characters()
    user_characters = NovelCharacter.get_user_characters(current_user.id)
    
    # 获取用户级别的预设配置
    user_settings = UserSettings.get_or_create(current_user.id)
    user_preset_config = user_settings.get_setting('novel_preset_config', {})
    user_persona = user_settings.get_setting('novel_user_persona', '')
    user_regex_rules = user_settings.get_setting('novel_regex_rules', [])
    current_profile_id = user_settings.get_setting('novel_current_profile_id', None)
    include_system_presets = user_settings.get_setting('novel_include_system_presets', True)
    
    # 获取预设配置文件列表
    preset_profiles = NovelPresetProfile.get_user_profiles(current_user.id)
    
    # 获取预设条目
    preset_prompts = {}
    preset_order = []
    
    # 只有当 include_system_presets 为 True 时才加载系统预设
    if include_system_presets:
        preset_order = list(PRESET_ORDER)
        
        # 加载用户对系统预设的覆盖
        user_overrides = {p.key: p for p in NovelUserPreset.get_user_overrides(current_user.id)}
        
        # 合并系统预设和用户覆盖
        for key, prompt in NOVEL_PRESET_PROMPTS.items():
            if key in user_overrides:
                # 用户有覆盖，使用覆盖的内容
                override = user_overrides[key]
                preset_prompts[key] = {
                    **prompt,
                    'content': override.content,
                    'name': override.name,
                    'role': override.role,
                    'is_overridden': True,
                    'override_id': override.id
                }
            else:
                preset_prompts[key] = {**prompt, 'is_overridden': False}
    
    # 加载用户自定义预设
    user_presets = NovelUserPreset.get_user_presets(current_user.id)
    for up in user_presets:
        preset_prompts[up.key] = up.to_dict()
        if up.key not in preset_order:
            preset_order.append(up.key)
    
    return render_template('ai/novel.html',
                          dialogs=[d.to_dict() for d in dialogs],
                          system_characters=[c.to_dict() for c in system_characters],
                          user_characters=[c.to_dict() for c in user_characters],
                          preset_prompts=preset_prompts,
                          preset_order=preset_order,
                          user_preset_config=user_preset_config,
                          user_persona=user_persona,
                          user_regex_rules=user_regex_rules,
                          preset_profiles=[p.to_dict() for p in preset_profiles],
                          current_profile_id=current_profile_id,
                          include_system_presets=include_system_presets)


# ============ 功能开关检查 ============

@novel_bp.before_request
def check_novel_enabled():
    """在每个请求前检查AI小说功能是否启用"""
    if not is_novel_enabled():
        # 对于API请求返回JSON错误
        if request.path.startswith('/novel/api/'):
            return jsonify({'success': False, 'message': 'AI小说功能已关闭'}), 403
        # 对于页面请求返回403
        abort(403, description='AI小说功能已关闭')


# ============ 对话API ============

@novel_bp.route('/api/dialogs', methods=['POST'])
@login_required
def create_dialog():
    """创建新对话"""
    data = request.json or {}
    title = data.get('title', '新故事')
    character_id = data.get('character_id')
    preset_config = data.get('preset_config', {})
    user_persona = data.get('user_persona', '')
    
    dialog = NovelDialog.create(
        user_id=current_user.id,
        title=title,
        character_id=character_id,
        preset_config=preset_config,
        user_persona=user_persona
    )
    
    # 如果有角色，添加开场白
    if character_id:
        character = NovelCharacter.query.get(character_id)
        if character and character.first_message:
            novel_service = get_novel_service()
            first_msg = novel_service.generate_first_message(character)
            if first_msg:
                dialog.add_message('assistant', first_msg)
    
    return jsonify({'success': True, 'dialog': dialog.to_dict()})


@novel_bp.route('/api/dialogs/<int:dialog_id>', methods=['GET'])
@login_required
def get_dialog(dialog_id):
    """获取对话详情"""
    dialog = NovelDialog.query.get(dialog_id)
    
    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404
    
    return jsonify({'success': True, 'dialog': dialog.to_dict()})


@novel_bp.route('/api/dialogs', methods=['GET'])
@login_required
def list_dialogs():
    """获取对话列表"""
    page = int(request.args.get('page', 1))
    dialogs, total = NovelDialog.find_by_user(current_user.id, page=page, per_page=20)
    
    return jsonify({
        'success': True,
        'dialogs': [d.to_dict() for d in dialogs],
        'total': total
    })


@novel_bp.route('/api/dialogs/<int:dialog_id>/message', methods=['POST'])
@login_required
def send_message(dialog_id):
    """发送消息（支持流式和非流式响应）"""
    dialog = NovelDialog.query.get(dialog_id)
    
    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404
    
    user_message = request.json.get('message', '').strip()
    regenerate = request.json.get('regenerate', False)
    stream = request.json.get('stream', True)  # 默认流式
    
    if not user_message and not regenerate:
        return jsonify({'success': False, 'message': '消息不能为空'}), 400
    
    # 获取角色
    character = dialog.character
    
    # 如果是重新生成，删除最后一条AI消息
    if regenerate:
        dialog.remove_last_assistant_message()
    else:
        # 添加用户消息
        dialog.add_message('user', user_message)
    
    novel_service = get_novel_service()
    
    # 获取用户级别的预设配置和persona
    user_settings = UserSettings.get_or_create(current_user.id)
    user_preset_config = user_settings.get_setting('novel_preset_config', {})
    user_persona = user_settings.get_setting('novel_user_persona', '')
    include_system_presets = user_settings.get_setting('novel_include_system_presets', True)
    
    # 非流式模式
    if not stream:
        try:
            full_response = ''
            for chunk in novel_service.chat_stream(
                character=character,
                user_persona=user_persona,
                dialog_history=dialog.get_messages_for_api()[:-1] if not regenerate else dialog.get_messages_for_api(),
                preset_config=user_preset_config,
                user_message=user_message if not regenerate else '',
                include_system_presets=include_system_presets
            ):
                full_response += chunk
            
            # 添加AI回复到对话历史
            dialog.add_message('assistant', full_response)
            
            return jsonify({
                'success': True,
                'content': full_response
            })
        except Exception as e:
            current_app.logger.error(f'Novel message error: {str(e)}')
            return jsonify({'success': False, 'message': f'生成失败: {str(e)}'}), 500
    
    # 流式模式
    def generate():
        try:
            full_response = ''
            
            for chunk in novel_service.chat_stream(
                character=character,
                user_persona=user_persona,
                dialog_history=dialog.get_messages_for_api()[:-1] if not regenerate else dialog.get_messages_for_api(),
                preset_config=user_preset_config,
                user_message=user_message if not regenerate else '',
                include_system_presets=include_system_presets
            ):
                full_response += chunk
                escaped_chunk = chunk.replace('\n', '\\n')
                yield f"data: {escaped_chunk}\n\n"
            
            # 添加AI回复到对话历史
            dialog.add_message('assistant', full_response)
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            current_app.logger.error(f'Novel message error: {str(e)}')
            yield f"data: *系统错误: {str(e)}*\n\n"
            yield "data: [DONE]\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@novel_bp.route('/api/dialogs/<int:dialog_id>/delete', methods=['POST'])
@login_required
def delete_dialog(dialog_id):
    """删除对话"""
    dialog = NovelDialog.query.get(dialog_id)
    
    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404
    
    db.session.delete(dialog)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '对话已删除'})


@novel_bp.route('/api/dialogs/<int:dialog_id>/preset', methods=['POST'])
@login_required
def update_preset(dialog_id):
    """更新对话的预设配置（已废弃，保留兼容）"""
    # 现在预设配置保存在用户级别，这个API保留兼容性
    preset_config = request.json.get('preset_config', {})
    
    # 保存到用户设置
    user_settings = UserSettings.get_or_create(current_user.id)
    user_settings.set_setting('novel_preset_config', preset_config)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '预设已更新'})


@novel_bp.route('/api/dialogs/<int:dialog_id>/persona', methods=['POST'])
@login_required
def update_persona(dialog_id):
    """更新用户persona（已废弃，保留兼容）"""
    user_persona = request.json.get('user_persona', '')
    
    # 保存到用户设置
    user_settings = UserSettings.get_or_create(current_user.id)
    user_settings.set_setting('novel_user_persona', user_persona)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Persona已更新'})


# ============ 用户级别预设配置API ============

@novel_bp.route('/api/settings/preset-config', methods=['GET'])
@login_required
def get_preset_config():
    """获取用户的预设配置"""
    user_settings = UserSettings.get_or_create(current_user.id)
    preset_config = user_settings.get_setting('novel_preset_config', {})
    user_persona = user_settings.get_setting('novel_user_persona', '')
    
    return jsonify({
        'success': True,
        'preset_config': preset_config,
        'user_persona': user_persona
    })


@novel_bp.route('/api/settings/preset-config', methods=['POST'])
@login_required
def save_preset_config():
    """保存用户的预设配置（用户级别，不依赖故事）"""
    data = request.json or {}
    preset_config = data.get('preset_config', {})
    
    user_settings = UserSettings.get_or_create(current_user.id)
    user_settings.set_setting('novel_preset_config', preset_config)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '预设配置已保存'})


@novel_bp.route('/api/settings/reset-to-default', methods=['POST'])
@login_required
def reset_to_default_profile():
    """重置为默认配置（捌预设）"""
    try:
        user_settings = UserSettings.get_or_create(current_user.id)
        
        # 重置所有相关设置
        user_settings.set_setting('novel_preset_config', {})
        user_settings.set_setting('novel_current_profile_id', None)
        user_settings.set_setting('novel_include_system_presets', True)  # 恢复系统预设
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '已恢复默认配置'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Reset to default error: {str(e)}')
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'}), 500


@novel_bp.route('/api/settings/persona', methods=['POST'])
@login_required
def save_persona():
    """保存用户的Persona（用户级别，不依赖故事）"""
    data = request.json or {}
    user_persona = data.get('user_persona', '')
    
    user_settings = UserSettings.get_or_create(current_user.id)
    user_settings.set_setting('novel_user_persona', user_persona)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Persona已保存'})


@novel_bp.route('/api/settings/regex-rules', methods=['GET'])
@login_required
def get_regex_rules():
    """获取用户的正则表达式规则"""
    user_settings = UserSettings.get_or_create(current_user.id)
    regex_rules = user_settings.get_setting('novel_regex_rules', [])
    
    return jsonify({
        'success': True,
        'regex_rules': regex_rules
    })


@novel_bp.route('/api/settings/regex-rules', methods=['POST'])
@login_required
def save_regex_rules():
    """保存用户的正则表达式规则"""
    data = request.json or {}
    regex_rules = data.get('regex_rules', [])
    
    # 验证正则表达式格式
    validated_rules = []
    for rule in regex_rules:
        if not isinstance(rule, dict):
            continue
        
        pattern = rule.get('pattern', '')
        replacement = rule.get('replacement', '')
        name = rule.get('name', '未命名规则')
        enabled = rule.get('enabled', True)
        apply_to = rule.get('apply_to', 'output')
        
        # 验证正则表达式是否有效
        try:
            re.compile(pattern)
        except re.error:
            continue
        
        validated_rules.append({
            'name': name,
            'pattern': pattern,
            'replacement': replacement,
            'enabled': enabled,
            'apply_to': apply_to
        })
    
    user_settings = UserSettings.get_or_create(current_user.id)
    user_settings.set_setting('novel_regex_rules', validated_rules)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'regex_rules': validated_rules,
        'message': '正则规则已保存'
    })


@novel_bp.route('/api/settings/reset-all', methods=['POST'])
@login_required
def reset_all_presets():
    """一键清空所有预设（重置为默认）"""
    try:
        # 1. 清空用户的预设配置
        user_settings = UserSettings.get_or_create(current_user.id)
        user_settings.set_setting('novel_preset_config', {})
        user_settings.set_setting('novel_regex_rules', [])  # 同时清空正则规则
        
        # 2. 删除所有用户自定义预设（软删除）
        NovelUserPreset.query.filter_by(
            user_id=current_user.id, 
            is_override=False,
            is_active=True
        ).update({'is_active': False}, synchronize_session='fetch')
        
        # 3. 删除所有用户对系统预设的覆盖（软删除）
        NovelUserPreset.query.filter_by(
            user_id=current_user.id, 
            is_override=True,
            is_active=True
        ).update({'is_active': False}, synchronize_session='fetch')
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '所有预设已重置为默认'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Reset presets error: {str(e)}')
        return jsonify({'success': False, 'message': f'重置失败: {str(e)}'}), 500


# ============ 预设配置文件API ============

@novel_bp.route('/api/profiles', methods=['GET'])
@login_required
def list_preset_profiles():
    """获取用户的预设配置文件列表"""
    profiles = NovelPresetProfile.get_user_profiles(current_user.id)
    
    # 获取当前使用的配置文件ID
    user_settings = UserSettings.get_or_create(current_user.id)
    current_profile_id = user_settings.get_setting('novel_current_profile_id', None)
    
    return jsonify({
        'success': True,
        'profiles': [p.to_dict() for p in profiles],
        'current_profile_id': current_profile_id
    })


@novel_bp.route('/api/profiles', methods=['POST'])
@login_required
def create_preset_profile():
    """创建新的预设配置文件"""
    data = request.json or {}
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '配置文件名称不能为空'}), 400
    
    description = data.get('description', '')
    preset_config = data.get('preset_config', {})
    custom_presets = data.get('custom_presets', [])
    include_system_presets = data.get('include_system_presets', True)
    
    try:
        profile = NovelPresetProfile.create(
            user_id=current_user.id,
            name=name,
            description=description,
            preset_config=preset_config,
            custom_presets=custom_presets,
            include_system_presets=include_system_presets
        )
        
        return jsonify({'success': True, 'profile': profile.to_dict(), 'message': '配置文件已创建'})
    except Exception as e:
        current_app.logger.error(f'Create profile error: {str(e)}')
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'}), 500


@novel_bp.route('/api/profiles/<int:profile_id>', methods=['PUT'])
@login_required
def update_preset_profile(profile_id):
    """更新预设配置文件"""
    profile = NovelPresetProfile.query.get(profile_id)
    
    if not profile or profile.user_id != current_user.id:
        return jsonify({'success': False, 'message': '配置文件不存在'}), 404
    
    data = request.json or {}
    
    if 'name' in data:
        profile.name = data['name']
    if 'description' in data:
        profile.description = data['description']
    if 'preset_config' in data:
        profile.set_preset_config(data['preset_config'])
    if 'custom_presets' in data:
        profile.set_custom_presets(data['custom_presets'])
    if 'include_system_presets' in data:
        profile.include_system_presets = data['include_system_presets']
    
    profile.updated_at = db.func.now()
    db.session.commit()
    
    return jsonify({'success': True, 'profile': profile.to_dict(), 'message': '配置文件已更新'})


@novel_bp.route('/api/profiles/<int:profile_id>', methods=['DELETE'])
@login_required
def delete_preset_profile(profile_id):
    """删除预设配置文件"""
    profile = NovelPresetProfile.query.get(profile_id)
    
    if not profile or profile.user_id != current_user.id:
        return jsonify({'success': False, 'message': '配置文件不存在'}), 404
    
    profile.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': '配置文件已删除'})


@novel_bp.route('/api/profiles/<int:profile_id>/activate', methods=['POST'])
@login_required
def activate_preset_profile(profile_id):
    """激活（切换到）指定的预设配置文件"""
    profile = NovelPresetProfile.query.get(profile_id)
    
    if not profile or profile.user_id != current_user.id:
        return jsonify({'success': False, 'message': '配置文件不存在'}), 404
    
    try:
        user_settings = UserSettings.get_or_create(current_user.id)
        
        # 保存当前配置文件ID
        user_settings.set_setting('novel_current_profile_id', profile_id)
        
        # 应用配置文件的预设配置
        user_settings.set_setting('novel_preset_config', profile.get_preset_config())
        
        # 应用配置文件的正则规则
        user_settings.set_setting('novel_regex_rules', profile.get_regex_rules())
        
        # 如果配置文件不包含系统预设，设置一个标记
        user_settings.set_setting('novel_include_system_presets', profile.include_system_presets)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'已切换到配置文件: {profile.name}',
            'profile': profile.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Activate profile error: {str(e)}')
        return jsonify({'success': False, 'message': f'切换失败: {str(e)}'}), 500


@novel_bp.route('/api/profiles/save-current', methods=['POST'])
@login_required
def save_current_as_profile():
    """将当前预设配置保存为新的配置文件"""
    data = request.json or {}
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '配置文件名称不能为空'}), 400
    
    description = data.get('description', '')
    include_system_presets = data.get('include_system_presets', True)
    
    try:
        # 获取当前的预设配置
        user_settings = UserSettings.get_or_create(current_user.id)
        current_preset_config = user_settings.get_setting('novel_preset_config', {})
        current_regex_rules = user_settings.get_setting('novel_regex_rules', [])
        
        # 获取用户自定义预设
        user_presets = NovelUserPreset.get_user_presets(current_user.id)
        custom_presets = [p.to_dict() for p in user_presets]
        
        # 创建配置文件
        profile = NovelPresetProfile.create(
            user_id=current_user.id,
            name=name,
            description=description,
            preset_config=current_preset_config,
            custom_presets=custom_presets,
            regex_rules=current_regex_rules,
            include_system_presets=include_system_presets
        )
        
        return jsonify({'success': True, 'profile': profile.to_dict(), 'message': '配置文件已保存'})
    except Exception as e:
        current_app.logger.error(f'Save profile error: {str(e)}')
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500


@novel_bp.route('/api/profiles/new-empty', methods=['POST'])
@login_required
def create_empty_profile():
    """创建空白预设配置（清空所有系统预设）"""
    data = request.json or {}
    
    name = data.get('name', '新预设配置').strip()
    description = data.get('description', '')
    
    try:
        # 创建一个不包含系统预设的空配置
        profile = NovelPresetProfile.create(
            user_id=current_user.id,
            name=name,
            description=description,
            preset_config={},  # 空配置
            custom_presets=[],  # 无自定义预设
            include_system_presets=False  # 不包含系统预设
        )
        
        # 立即激活这个配置
        user_settings = UserSettings.get_or_create(current_user.id)
        user_settings.set_setting('novel_current_profile_id', profile.id)
        user_settings.set_setting('novel_preset_config', {})
        user_settings.set_setting('novel_include_system_presets', False)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'profile': profile.to_dict(), 
            'message': '已创建空白配置并激活'
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Create empty profile error: {str(e)}')
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'}), 500


# ============ 角色API ============

@novel_bp.route('/api/characters', methods=['GET'])
@login_required
def list_characters():
    """获取角色列表"""
    system_characters = NovelCharacter.get_system_characters()
    user_characters = NovelCharacter.get_user_characters(current_user.id)
    
    return jsonify({
        'success': True,
        'system_characters': [c.to_dict() for c in system_characters],
        'user_characters': [c.to_dict() for c in user_characters]
    })


@novel_bp.route('/api/characters', methods=['POST'])
@login_required
def create_character():
    """创建自定义角色"""
    data = request.json or {}
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '角色名称不能为空'}), 400
    
    character = NovelCharacter.create(
        name=name,
        avatar=data.get('avatar', '👤'),
        description=data.get('description', ''),
        personality=data.get('personality', ''),
        scenario=data.get('scenario', ''),
        first_message=data.get('first_message', ''),
        example_dialogs=data.get('example_dialogs', ''),
        is_system=False,
        created_by=current_user.id
    )
    
    return jsonify({'success': True, 'character': character.to_dict()})


@novel_bp.route('/api/characters/<int:character_id>', methods=['PUT'])
@login_required
def update_character(character_id):
    """更新自定义角色"""
    character = NovelCharacter.query.get(character_id)
    
    if not character:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    
    # 只能编辑自己创建的角色
    if character.created_by != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权编辑此角色'}), 403
    
    data = request.json or {}
    
    if 'name' in data:
        character.name = data['name']
    if 'avatar' in data:
        character.avatar = data['avatar']
    if 'description' in data:
        character.description = data['description']
    if 'personality' in data:
        character.personality = data['personality']
    if 'scenario' in data:
        character.scenario = data['scenario']
    if 'first_message' in data:
        character.first_message = data['first_message']
    if 'example_dialogs' in data:
        character.example_dialogs = data['example_dialogs']
    
    db.session.commit()
    
    return jsonify({'success': True, 'character': character.to_dict()})


@novel_bp.route('/api/characters/<int:character_id>', methods=['DELETE'])
@login_required
def delete_character(character_id):
    """删除自定义角色"""
    character = NovelCharacter.query.get(character_id)
    
    if not character:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    
    # 只能删除自己创建的角色
    if character.created_by != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权删除此角色'}), 403
    
    # 系统角色不能删除
    if character.is_system:
        return jsonify({'success': False, 'message': '系统角色不能删除'}), 403
    
    character.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': '角色已删除'})


# ============ 预设API ============

@novel_bp.route('/api/presets', methods=['GET'])
@login_required
def get_presets():
    """获取所有预设条目"""
    return jsonify({
        'success': True,
        'presets': NOVEL_PRESET_PROMPTS,
        'order': PRESET_ORDER
    })


@novel_bp.route('/api/characters/import', methods=['POST'])
@login_required
def import_character():
    """
    导入角色（支持SillyTavern世界书格式）
    格式: {"entries": {"0": {"key": [...], "content": "...", "comment": "..."}, ...}}
    """
    import json
    
    data = request.json or {}
    
    # 基本角色信息
    name = data.get('name', '').strip()
    avatar = data.get('avatar', '👤')
    description = data.get('description', '')
    personality = data.get('personality', '')
    scenario = data.get('scenario', '')
    first_message = data.get('first_message', '')
    
    # 世界书/lorebook导入
    entries_data = data.get('entries')
    example_dialogs = data.get('example_dialogs', '')
    
    if entries_data:
        # 解析SillyTavern世界书格式
        try:
            if isinstance(entries_data, str):
                entries_data = json.loads(entries_data)
            
            # 提取entries
            if isinstance(entries_data, dict):
                entries = entries_data.get('entries', entries_data)
            else:
                entries = {}
            
            # 构建示例对话 - 每个条目独立分隔
            dialog_parts = []
            for key, entry in entries.items():
                if isinstance(entry, dict):
                    content = entry.get('content', '').strip()
                    comment = entry.get('comment', '').strip()
                    keywords = entry.get('key', [])
                    
                    if content:
                        # 构建单个条目
                        entry_text = ''
                        
                        # 添加条目标题（使用comment或keywords）
                        if comment:
                            entry_text = f'【{comment}】\n'
                        elif keywords and isinstance(keywords, list) and len(keywords) > 0:
                            entry_text = f'【{", ".join(keywords[:3])}】\n'
                        
                        entry_text += content
                        dialog_parts.append(entry_text)
            
            if dialog_parts:
                # 使用分隔线分隔每个条目
                example_dialogs = '\n\n---\n\n'.join(dialog_parts)
                
        except (json.JSONDecodeError, TypeError) as e:
            current_app.logger.error(f'Import character error: {e}')
            return jsonify({'success': False, 'message': f'解析导入数据失败: {str(e)}'}), 400
    
    if not name:
        return jsonify({'success': False, 'message': '角色名称不能为空'}), 400
    
    try:
        character = NovelCharacter.create(
            name=name,
            avatar=avatar,
            description=description,
            personality=personality,
            scenario=scenario,
            first_message=first_message,
            example_dialogs=example_dialogs,
            is_system=False,
            created_by=current_user.id
        )
        
        return jsonify({'success': True, 'character': character.to_dict(), 'message': '角色导入成功'})
    except Exception as e:
        current_app.logger.error(f'Create character error: {e}')
        return jsonify({'success': False, 'message': f'创建角色失败: {str(e)}'}), 500


# ============ 用户预设API ============

@novel_bp.route('/api/presets/user', methods=['GET'])
@login_required
def get_user_presets():
    """获取用户自定义预设"""
    presets = NovelUserPreset.get_user_presets(current_user.id)
    return jsonify({
        'success': True,
        'presets': [p.to_dict() for p in presets]
    })


@novel_bp.route('/api/presets/user', methods=['POST'])
@login_required
def create_user_preset():
    """创建用户自定义预设"""
    data = request.json or {}
    
    name = data.get('name', '').strip()
    content = data.get('content', '').strip()
    role = data.get('role', 'system')
    
    if not name or not content:
        return jsonify({'success': False, 'message': '名称和内容不能为空'}), 400
    
    if role not in ['user', 'assistant', 'system']:
        role = 'system'
    
    # 生成唯一key
    key = f"custom_{current_user.id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    
    preset = NovelUserPreset.create(
        user_id=current_user.id,
        key=key,
        name=name,
        role=role,
        content=content,
        enabled=data.get('enabled', True),
        order_index=data.get('order_index', 100),
        is_override=False
    )
    
    return jsonify({'success': True, 'preset': preset.to_dict()})


@novel_bp.route('/api/presets/import', methods=['POST'])
@login_required
def import_presets():
    """批量导入预设（支持SillyTavern格式）"""
    data = request.json or {}
    presets_data = data.get('presets', [])
    
    if not presets_data:
        return jsonify({'success': False, 'message': '没有预设数据'}), 400
    
    imported = []
    errors = []
    
    for p in presets_data:
        name = p.get('name', '').strip()
        content = p.get('content', '').strip()
        role = p.get('role', 'system')
        
        if not name or not content:
            errors.append(f'跳过无效预设: {name or "未命名"}')
            continue
        
        if role not in ['user', 'assistant', 'system']:
            role = 'system'
        
        key = f"custom_{current_user.id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        
        try:
            preset = NovelUserPreset.create(
                user_id=current_user.id,
                key=key,
                name=name,
                role=role,
                content=content,
                enabled=p.get('enabled', True),
                order_index=p.get('order_index', 100),
                is_override=False
            )
            imported.append(preset.to_dict())
        except Exception as e:
            errors.append(f'导入失败: {name} - {str(e)}')
    
    return jsonify({
        'success': True,
        'imported': imported,
        'imported_count': len(imported),
        'errors': errors
    })


@novel_bp.route('/api/presets/override', methods=['POST'])
@login_required
def override_system_preset():
    """覆盖系统预设内容"""
    data = request.json or {}
    
    key = data.get('key', '').strip()
    content = data.get('content', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', '')
    
    if not key or not content:
        return jsonify({'success': False, 'message': 'key和内容不能为空'}), 400
    
    # 检查是否是有效的系统预设key
    if key not in NOVEL_PRESET_PROMPTS:
        return jsonify({'success': False, 'message': '无效的预设key'}), 400
    
    original = NOVEL_PRESET_PROMPTS[key]
    
    # 检查是否已有覆盖
    existing = NovelUserPreset.get_override(current_user.id, key)
    
    if existing:
        # 更新现有覆盖
        existing.content = content
        existing.name = name or original['name']
        existing.role = role if role in ['user', 'assistant', 'system'] else original['role']
        existing.updated_at = db.func.now()
        db.session.commit()
        return jsonify({'success': True, 'preset': existing.to_dict(), 'message': '预设已更新'})
    else:
        # 创建新覆盖
        preset = NovelUserPreset.create(
            user_id=current_user.id,
            key=key,
            name=name or original['name'],
            role=role if role in ['user', 'assistant', 'system'] else original['role'],
            content=content,
            enabled=original.get('enabled', True),
            is_override=True
        )
        return jsonify({'success': True, 'preset': preset.to_dict(), 'message': '预设覆盖已创建'})


@novel_bp.route('/api/presets/override/<key>', methods=['DELETE'])
@login_required
def reset_system_preset(key):
    """重置系统预设为默认值（删除覆盖）"""
    if key not in NOVEL_PRESET_PROMPTS:
        return jsonify({'success': False, 'message': '无效的预设key'}), 400
    
    existing = NovelUserPreset.get_override(current_user.id, key)
    if existing:
        existing.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': '已重置为默认值'})
    
    return jsonify({'success': True, 'message': '预设未被修改过'})


@novel_bp.route('/api/presets/user/<int:preset_id>', methods=['PUT'])
@login_required
def update_user_preset(preset_id):
    """更新用户自定义预设"""
    preset = NovelUserPreset.query.get(preset_id)
    
    if not preset or preset.user_id != current_user.id:
        return jsonify({'success': False, 'message': '预设不存在'}), 404
    
    data = request.json or {}
    
    if 'name' in data:
        preset.name = data['name']
    if 'content' in data:
        preset.content = data['content']
    if 'role' in data and data['role'] in ['user', 'assistant', 'system']:
        preset.role = data['role']
    if 'enabled' in data:
        preset.enabled = data['enabled']
    if 'order_index' in data:
        preset.order_index = data['order_index']
    
    preset.updated_at = db.func.now()
    db.session.commit()
    
    return jsonify({'success': True, 'preset': preset.to_dict()})


@novel_bp.route('/api/presets/user/<int:preset_id>', methods=['DELETE'])
@login_required
def delete_user_preset(preset_id):
    """删除用户自定义预设"""
    preset = NovelUserPreset.query.get(preset_id)
    
    if not preset or preset.user_id != current_user.id:
        return jsonify({'success': False, 'message': '预设不存在'}), 404
    
    preset.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': '预设已删除'})


# ============ 提示词预览API ============

@novel_bp.route('/api/dialogs/<int:dialog_id>/preview', methods=['GET'])
@login_required
def preview_prompt(dialog_id):
    """预览将要发送的提示词"""
    dialog = NovelDialog.query.get(dialog_id)
    
    if not dialog or dialog.user_id != current_user.id:
        return jsonify({'success': False, 'message': '对话不存在'}), 404
    
    character = dialog.character
    novel_service = get_novel_service()
    
    # 获取用户级别的预设配置和persona
    user_settings = UserSettings.get_or_create(current_user.id)
    user_preset_config = user_settings.get_setting('novel_preset_config', {})
    user_persona = user_settings.get_setting('novel_user_persona', '')
    
    # 获取用户自定义预设
    user_presets = NovelUserPreset.get_user_presets(current_user.id)
    custom_presets = {p.key: p.to_dict() for p in user_presets}
    
    # 构建消息
    messages = novel_service.build_messages(
        character=character,
        user_persona=user_persona,
        dialog_history=dialog.get_messages_for_api(),
        preset_config=user_preset_config,
        user_message='[用户消息将在此处]',
        custom_presets=custom_presets
    )
    
    # 计算token估算（简单估算：4字符≈1token）
    total_chars = sum(len(m.get('content', '')) for m in messages)
    estimated_tokens = total_chars // 4
    
    return jsonify({
        'success': True,
        'messages': messages,
        'message_count': len(messages),
        'estimated_tokens': estimated_tokens
    })


# ============ 头像上传API ============

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@novel_bp.route('/api/characters/<int:character_id>/avatar', methods=['POST'])
@login_required
def upload_character_avatar(character_id):
    """上传角色头像"""
    character = NovelCharacter.query.get(character_id)
    
    if not character:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    
    # 只能编辑自己创建的角色
    if character.created_by != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权编辑此角色'}), 403
    
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400
    
    file = request.files['avatar']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': '不支持的文件格式'}), 400
    
    # 生成唯一文件名
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"char_{character_id}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # 保存到uploads/avatars目录
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_dir, exist_ok=True)
    
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    
    # 更新角色头像URL
    avatar_url = f"/static/uploads/avatars/{filename}"
    character.avatar_url = avatar_url
    db.session.commit()
    
    return jsonify({
        'success': True,
        'avatar_url': avatar_url,
        'message': '头像上传成功'
    })


# ============ 正则表达式API ============

@novel_bp.route('/api/characters/<int:character_id>/regex', methods=['GET'])
@login_required
def get_character_regex(character_id):
    """获取角色的正则表达式规则"""
    character = NovelCharacter.query.get(character_id)
    
    if not character:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    
    return jsonify({
        'success': True,
        'regex_rules': character.regex_rules or []
    })


@novel_bp.route('/api/characters/<int:character_id>/regex', methods=['POST'])
@login_required
def update_character_regex(character_id):
    """更新角色的正则表达式规则"""
    character = NovelCharacter.query.get(character_id)
    
    if not character:
        return jsonify({'success': False, 'message': '角色不存在'}), 404
    
    # 只能编辑自己创建的角色
    if character.created_by != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权编辑此角色'}), 403
    
    data = request.json or {}
    regex_rules = data.get('regex_rules', [])
    
    # 验证正则表达式格式
    validated_rules = []
    for rule in regex_rules:
        if not isinstance(rule, dict):
            continue
        
        pattern = rule.get('pattern', '')
        replacement = rule.get('replacement', '')
        name = rule.get('name', '未命名规则')
        enabled = rule.get('enabled', True)
        apply_to = rule.get('apply_to', 'output')  # input/output/both
        
        # 验证正则表达式是否有效
        try:
            re.compile(pattern)
        except re.error:
            continue
        
        validated_rules.append({
            'name': name,
            'pattern': pattern,
            'replacement': replacement,
            'enabled': enabled,
            'apply_to': apply_to
        })
    
    character.regex_rules = validated_rules
    db.session.commit()
    
    return jsonify({
        'success': True,
        'regex_rules': validated_rules,
        'message': '正则规则已更新'
    })


@novel_bp.route('/api/regex/test', methods=['POST'])
@login_required
def test_regex():
    """测试正则表达式"""
    data = request.json or {}
    pattern = data.get('pattern', '')
    replacement = data.get('replacement', '')
    test_text = data.get('test_text', '')
    
    if not pattern or not test_text:
        return jsonify({'success': False, 'message': '请提供正则表达式和测试文本'}), 400
    
    try:
        regex = re.compile(pattern)
        result = regex.sub(replacement, test_text)
        matches = regex.findall(test_text)
        
        return jsonify({
            'success': True,
            'result': result,
            'matches': matches[:10],  # 最多返回10个匹配
            'match_count': len(matches)
        })
    except re.error as e:
        return jsonify({'success': False, 'message': f'正则表达式错误: {str(e)}'}), 400
