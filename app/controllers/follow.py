"""
关注功能路由控制器
"""
from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.models.user import User
from app.extensions import db

follow_bp = Blueprint('follow', __name__)


@follow_bp.route('/api/follow/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    """关注用户"""
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '不能关注自己'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    current_user.follow(user)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': '关注成功',
        'follower_count': user.followers.count()
    })


@follow_bp.route('/api/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow_user(user_id):
    """取消关注"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    current_user.unfollow(user)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': '已取消关注',
        'follower_count': user.followers.count()
    })


@follow_bp.route('/api/follow-status/<int:user_id>', methods=['GET'])
@login_required
def follow_status(user_id):
    """获取关注状态"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    return jsonify({
        'success': True,
        'is_following': current_user.is_following(user),
        'follower_count': user.followers.count(),
        'following_count': user.following.count()
    })


@follow_bp.route('/api/followers/<int:user_id>', methods=['GET'])
def get_followers(user_id):
    """获取粉丝列表"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    page = int(__import__('flask').request.args.get('page', 1))
    per_page = 20

    pagination = user.followers.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'success': True,
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page
    })


@follow_bp.route('/api/following/<int:user_id>', methods=['GET'])
def get_following(user_id):
    """获取关注列表"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    page = int(__import__('flask').request.args.get('page', 1))
    per_page = 20

    pagination = user.following.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'success': True,
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page
    })
