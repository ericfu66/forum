"""
消息路由控制器
处理私信、收件箱、对话等功能
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.services.message_service import get_message_service
from app.models.user import User
from app.models.cat_girl import get_or_create_cat_girl, is_cat_girl

message_bp = Blueprint('message', __name__)


# ============ 页面路由 ============

@message_bp.route('/inbox')
@login_required
def inbox():
    """收件箱页面"""
    page = int(request.args.get('page', 1))
    per_page = 20
    message_type = request.args.get('type')  # 'private', 'system', 'moderation'
    
    message_service = get_message_service()
    messages, total = message_service.get_inbox(current_user.id, page, per_page, message_type)
    unread_count = message_service.get_unread_count(current_user.id)
    
    # 获取猫娘信息
    cat_girl = get_or_create_cat_girl()
    
    return render_template('messages/inbox.html',
                          messages=messages,
                          total=total,
                          page=page,
                          per_page=per_page,
                          message_type=message_type,
                          unread_count=unread_count,
                          cat_girl=cat_girl.to_dict())


@message_bp.route('/conversations')
@login_required
def conversations():
    """对话列表页面"""
    page = int(request.args.get('page', 1))
    per_page = 20
    
    message_service = get_message_service()
    conversation_list, total = message_service.get_conversation_list(current_user.id, page, per_page)
    
    # 获取猫娘信息
    cat_girl = get_or_create_cat_girl()
    
    return render_template('messages/conversations.html',
                          conversations=conversation_list,
                          total=total,
                          page=page,
                          per_page=per_page,
                          cat_girl=cat_girl.to_dict())


@message_bp.route('/conversation/<int:user_id>')
@login_required
def conversation(user_id):
    """与某用户的对话页面"""
    page = int(request.args.get('page', 1))
    per_page = 50
    
    # 获取对方用户信息
    other_user = User.query.get(user_id)
    if not other_user:
        flash('用户不存在', 'warning')
        return redirect(url_for('message.inbox'))
    
    message_service = get_message_service()
    
    # 标记对话为已读
    message_service.mark_conversation_as_read(current_user.id, user_id)
    
    # 获取对话消息
    messages, total = message_service.get_conversation(current_user.id, user_id, page, per_page)
    
    # 检查是否是猫娘
    is_cat = is_cat_girl(user_id)
    
    # 获取猫娘背景设置
    cat_girl_background = 'default'
    cat_girl_background_css = ''
    if is_cat:
        from app.models.user_settings import UserSettings
        cat_girl_background = UserSettings.get_user_setting(current_user.id, 'cat_girl_background', 'default')
        cat_girl_background_css = UserSettings.get_cat_girl_background_css(cat_girl_background)
    
    return render_template('messages/conversation.html',
                          other_user=other_user.to_dict(),
                          messages=messages,
                          total=total,
                          page=page,
                          per_page=per_page,
                          is_cat_girl=is_cat,
                          cat_girl_background=cat_girl_background,
                          cat_girl_background_css=cat_girl_background_css)


@message_bp.route('/new')
@message_bp.route('/new/<int:recipient_id>')
@login_required
def new_message(recipient_id=None):
    """发送新消息页面"""
    recipient = None
    if recipient_id:
        recipient = User.query.get(recipient_id)
        if not recipient:
            flash('用户不存在', 'warning')
            return redirect(url_for('message.inbox'))
    
    return render_template('messages/new.html',
                          recipient=recipient.to_dict() if recipient else None)


# ============ API路由 ============

@message_bp.route('/send', methods=['POST'])
@login_required
def send():
    """发送私信"""
    data = request.get_json()
    recipient_id = data.get('recipient_id')
    content = data.get('content', '').strip()
    subject = data.get('subject', '').strip() or None
    
    if not recipient_id:
        return jsonify({'success': False, 'message': '请选择收件人'}), 400
    
    if not content:
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400
    
    message_service = get_message_service()
    success, message, msg_obj = message_service.send_private_message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        content=content,
        subject=subject
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'data': msg_obj.to_dict() if msg_obj else None
        })
    else:
        return jsonify({'success': False, 'message': message}), 400


@message_bp.route('/<int:message_id>/read', methods=['POST'])
@login_required
def mark_read(message_id):
    """标记消息为已读"""
    message_service = get_message_service()
    success, message = message_service.mark_as_read(message_id, current_user.id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@message_bp.route('/<int:message_id>/delete', methods=['POST'])
@login_required
def delete(message_id):
    """删除消息"""
    message_service = get_message_service()
    success, message = message_service.delete_message(message_id, current_user.id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@message_bp.route('/api/unread-count')
@login_required
def unread_count():
    """获取未读消息数量"""
    message_service = get_message_service()
    count = message_service.get_unread_count(current_user.id)
    return jsonify({'success': True, 'count': count})


@message_bp.route('/api/ai-reply', methods=['POST'])
@login_required
def ai_reply():
    """AI帮回消息"""
    data = request.get_json()
    other_user_id = data.get('other_user_id')
    style = data.get('style', 'friendly')  # 'formal', 'friendly', 'brief'
    
    if not other_user_id:
        return jsonify({'success': False, 'message': '缺少对方用户ID'}), 400
    
    if style not in ['formal', 'friendly', 'brief']:
        style = 'friendly'
    
    message_service = get_message_service()
    success, message, reply = message_service.generate_ai_reply(
        user_id=current_user.id,
        other_user_id=other_user_id,
        style=style
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'reply': reply
        })
    else:
        return jsonify({'success': False, 'message': message}), 400


@message_bp.route('/api/search-users')
@login_required
def search_users():
    """搜索用户（用于发送消息时选择收件人）"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify({'success': True, 'users': []})
    
    users = User.query.filter(
        User.username.ilike(f'%{query}%'),
        User.id != current_user.id,
        User.is_banned == False,
        User.role != 'system'  # 排除系统用户
    ).limit(10).all()
    
    return jsonify({
        'success': True,
        'users': [{'id': u.id, 'username': u.username, 'avatar': u.avatar} for u in users]
    })


@message_bp.route('/api/cat-girl-chat', methods=['POST'])
@login_required
def cat_girl_chat():
    """与猫娘聊天（非流式，用于保存消息）"""
    from app.services.cat_girl_service import get_cat_girl_service
    from app.models.message import Message
    from app.models.cat_girl import get_cat_girl_id
    
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400
    
    # 保存用户消息
    cat_girl_id = get_cat_girl_id()
    Message.create(
        sender_id=current_user.id,
        recipient_id=cat_girl_id,
        message_type='private',
        content=content
    )
    
    # 触发异步回复
    cat_girl_service = get_cat_girl_service()
    cat_girl_service.auto_reply_async(current_user.id, content)
    
    return jsonify({'success': True, 'message': '消息已发送'})


@message_bp.route('/api/cat-girl-stream', methods=['POST'])
@login_required
def cat_girl_stream():
    """与猫娘聊天（流式输出）"""
    from flask import Response, stream_with_context
    from app.services.cat_girl_service import get_cat_girl_service
    from app.models.message import Message
    from app.models.cat_girl import get_cat_girl_id
    
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400
    
    # 保存用户消息
    cat_girl_id = get_cat_girl_id()
    Message.create(
        sender_id=current_user.id,
        recipient_id=cat_girl_id,
        message_type='private',
        content=content
    )
    
    # 获取对话历史
    cat_girl_service = get_cat_girl_service()
    conversation_history = cat_girl_service._get_conversation_history(current_user.id, cat_girl_id)
    
    def generate():
        full_response = []
        try:
            for chunk in cat_girl_service.generate_response_stream(content, conversation_history):
                full_response.append(chunk)
                yield f"data: {chunk}\n\n"
            
            # 流式结束后保存完整回复
            complete_reply = ''.join(full_response)
            if complete_reply.strip():
                Message.create(
                    sender_id=cat_girl_id,
                    recipient_id=current_user.id,
                    message_type='private',
                    content=complete_reply
                )
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR]{str(e)}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@message_bp.route('/api/cat-girl-clear-memory', methods=['POST'])
@login_required
def cat_girl_clear_memory():
    """清除与猫娘的对话记忆"""
    from app.models.message import Message
    from app.models.cat_girl import get_cat_girl_id
    
    cat_girl_id = get_cat_girl_id()
    
    try:
        # 删除用户与猫娘之间的所有消息
        deleted_count = Message.query.filter(
            db.or_(
                db.and_(Message.sender_id == current_user.id, Message.recipient_id == cat_girl_id),
                db.and_(Message.sender_id == cat_girl_id, Message.recipient_id == current_user.id)
            )
        ).delete(synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'已清除 {deleted_count} 条对话记录，记忆已重置喵~',
            'deleted_count': deleted_count
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'清除失败: {str(e)}'}), 500


@message_bp.route('/api/cat-girl-background', methods=['GET'])
@login_required
def get_cat_girl_background():
    """获取用户的猫娘聊天背景设置"""
    from app.models.user_settings import UserSettings
    
    current_bg = UserSettings.get_user_setting(current_user.id, 'cat_girl_background', 'default')
    backgrounds = UserSettings.get_cat_girl_backgrounds()
    
    return jsonify({
        'success': True,
        'current': current_bg,
        'backgrounds': backgrounds
    })


@message_bp.route('/api/cat-girl-background', methods=['POST'])
@login_required
def set_cat_girl_background():
    """设置用户的猫娘聊天背景"""
    from app.models.user_settings import UserSettings
    
    data = request.get_json()
    background_key = data.get('background', 'default')
    
    # 验证背景是否存在
    backgrounds = UserSettings.get_cat_girl_backgrounds()
    if background_key not in backgrounds:
        return jsonify({'success': False, 'message': '无效的背景选项'}), 400
    
    UserSettings.set_user_setting(current_user.id, 'cat_girl_background', background_key)
    
    return jsonify({
        'success': True,
        'message': '背景已更新喵~',
        'background': background_key,
        'css': backgrounds[background_key]['css']
    })
