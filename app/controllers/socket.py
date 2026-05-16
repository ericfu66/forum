"""
SocketIO 实时推送事件处理器
"""
from flask_login import current_user
from flask_socketio import join_room, leave_room
from app.extensions import socketio, db


@socketio.on('connect')
def handle_connect():
    """用户连接"""
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        # 发送未读消息数
        from app.services.message_service import get_message_service
        try:
            msg_service = get_message_service()
            unread = msg_service.get_unread_count(current_user.id)
            socketio.emit('unread_count', {'count': unread}, room=f'user_{current_user.id}')
        except Exception:
            pass


@socketio.on('disconnect')
def handle_disconnect():
    """用户断开"""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')


@socketio.on('join_post')
def handle_join_post(data):
    """进入帖子详情页，接收实时评论"""
    post_id = data.get('post_id')
    if post_id:
        join_room(f'post_{post_id}')


@socketio.on('leave_post')
def handle_leave_post(data):
    """离开帖子详情页"""
    post_id = data.get('post_id')
    if post_id:
        leave_room(f'post_{post_id}')


def emit_new_comment(post_id, comment):
    """推送新评论到帖子房间"""
    socketio.emit('new_comment', {
        'post_id': post_id,
        'comment': comment
    }, room=f'post_{post_id}')


def emit_new_like(post_id, like_data):
    """推送点赞更新"""
    socketio.emit('like_update', {
        'post_id': post_id,
        **like_data
    }, room=f'post_{post_id}')


def emit_notification(user_id, notification):
    """推送通知给指定用户"""
    socketio.emit('notification', notification, room=f'user_{user_id}')


def emit_unread_count(user_id, count):
    """推送未读数更新"""
    socketio.emit('unread_count', {'count': count}, room=f'user_{user_id}')
