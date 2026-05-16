"""
后台管理路由控制器
处理用户管理、内容管理、配置管理等功能
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.utils.decorators import admin_required
from app.services.config_service import get_config_service, get_config_schema
from app.services.moderation_service import get_moderation_service
from app.models.user import User
from app.models.post import Post
from app.models.board import Board
from app.models.moderation_log import ModerationLog
from app.extensions import db
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)


# ============ 后台首页 ============

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """后台首页 - 统计数据"""
    stats = {
        'users': User.query.count(),
        'posts': Post.query.filter_by(status='published').count(),
        'comments': db.session.query(db.func.count()).scalar() or 0,
        'boards': Board.query.count(),
        'api_calls': 0,
    }

    # 获取最近注册的用户
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    # 获取最近的帖子
    recent_posts = Post.query.filter_by(status='published').order_by(Post.created_at.desc()).limit(10).all()
    
    # 获取待审核数量
    pending_moderation_count = ModerationLog.query.filter_by(ai_action='hold', final_action=None).count()

    return render_template('admin/dashboard.html',
                          stats=stats,
                          recent_users=[u.to_dict() for u in recent_users],
                          recent_posts=[p.to_dict() for p in recent_posts],
                          pending_moderation_count=pending_moderation_count)


# ============ 用户管理 ============

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """用户管理"""
    page = int(request.args.get('page', 1))
    per_page = 30

    pagination = User.query.order_by(User.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/users.html',
                          users=[u.to_dict() for u in pagination.items],
                          page=page,
                          total=pagination.total,
                          per_page=per_page)


@admin_bp.route('/users/<int:user_id>/ban', methods=['POST'])
@login_required
@admin_required
def ban_user(user_id):
    """封禁用户"""
    reason = request.json.get('reason', '')

    user = User.query.get(user_id)
    if user:
        user.is_banned = True
        user.ban_reason = reason
        db.session.commit()

    return jsonify({'success': True, 'message': '用户已封禁'})


@admin_bp.route('/users/<int:user_id>/unban', methods=['POST'])
@login_required
@admin_required
def unban_user(user_id):
    """解封用户"""
    user = User.query.get(user_id)
    if user:
        user.is_banned = False
        user.ban_reason = None
        db.session.commit()

    return jsonify({'success': True, 'message': '用户已解封'})


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    """修改用户角色"""
    role = request.json.get('role')

    if role not in ['user', 'admin', 'moderator']:
        return jsonify({'success': False, 'message': '无效的角色'}), 400

    user = User.query.get(user_id)
    if user:
        user.role = role
        db.session.commit()

    return jsonify({'success': True, 'message': '角色已修改'})


# ============ 内容管理 ============

@admin_bp.route('/posts')
@login_required
@admin_required
def posts():
    """内容管理 - 帖子列表"""
    page = int(request.args.get('page', 1))
    per_page = 30

    pagination = Post.query.order_by(Post.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/posts.html',
                          posts=[p.to_dict(include_author=True, include_board=True) for p in pagination.items],
                          page=page,
                          total=pagination.total,
                          per_page=per_page)


@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    """删除帖子"""
    post = Post.query.get(post_id)
    if post:
        post.status = 'deleted'
        
        # 同步删除知识库条目
        from app.services.knowledge_service import delete_post_knowledge
        delete_post_knowledge(post_id)
        
        db.session.commit()

    return jsonify({'success': True, 'message': '帖子已删除'})


@admin_bp.route('/posts/<int:post_id>/pin', methods=['POST'])
@login_required
@admin_required
def pin_post(post_id):
    """置顶/取消置顶"""
    is_pinned = request.json.get('is_pinned', False)

    post = Post.query.get(post_id)
    if post:
        post.is_pinned = is_pinned
        db.session.commit()

    return jsonify({'success': True, 'message': '操作成功'})


@admin_bp.route('/boards')
@login_required
@admin_required
def boards():
    """版块管理"""
    boards_list = Board.query.order_by(Board.order).all()
    return render_template('admin/boards.html',
                          boards=[b.to_dict() for b in boards_list])


@admin_bp.route('/boards/create', methods=['POST'])
@login_required
@admin_required
def create_board():
    """创建版块"""
    name = request.form.get('name').strip()
    slug = request.form.get('slug').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', '📁')
    color = request.form.get('color', '#2196F3')
    order = int(request.form.get('order', 0))

    if not name or not slug:
        flash('版块名称和标识不能为空', 'warning')
        return redirect(url_for('admin.boards'))

    Board.create(name, slug, description, icon, color, order)

    flash('版块创建成功', 'success')
    return redirect(url_for('admin.boards'))


@admin_bp.route('/boards/<int:board_id>/update', methods=['POST'])
@login_required
@admin_required
def update_board(board_id):
    """更新版块"""
    board = Board.query.get(board_id)
    if not board:
        return jsonify({'success': False, 'message': '版块不存在'}), 404

    data = request.get_json()
    board.name = data.get('name', board.name)
    board.slug = data.get('slug', board.slug)
    board.description = data.get('description', board.description)
    board.icon = data.get('icon', board.icon)
    board.color = data.get('color', board.color)
    board.order = int(data.get('order', board.order))
    board.is_active = data.get('is_active', board.is_active)

    db.session.commit()
    return jsonify({'success': True, 'message': '版块已更新', 'board': board.to_dict()})


@admin_bp.route('/boards/<int:board_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_board(board_id):
    """删除版块"""
    board = Board.query.get(board_id)
    if board:
        db.session.delete(board)
        db.session.commit()

    return jsonify({'success': True, 'message': '版块已删除'})


@admin_bp.route('/boards/reorder', methods=['POST'])
@login_required
@admin_required
def reorder_boards():
    """重新排序版块"""
    data = request.get_json()
    order_list = data.get('order', [])

    for idx, board_id in enumerate(order_list):
        board = Board.query.get(board_id)
        if board:
            board.order = idx

    db.session.commit()
    return jsonify({'success': True, 'message': '排序已更新'})


# ============ 配置管理 ============

@admin_bp.route('/config')
@login_required
@admin_required
def config():
    """配置管理页面"""
    config_service = get_config_service()
    
    # 获取结构化配置
    configs = config_service.get_all_configs_structured()

    # 获取配置变更历史
    history = config_service.get_config_history(limit=20)

    return render_template('admin/config.html',
                          configs=configs,
                          history=history)


# ============ 知识库管理 ============

@admin_bp.route('/knowledge')
@login_required
@admin_required
def knowledge():
    """知识库管理页面"""
    return render_template('admin/knowledge.html')


@admin_bp.route('/api/config', methods=['GET'])
@login_required
@admin_required
def get_config():
    """获取所有配置（API）"""
    config_service = get_config_service()
    configs = config_service.get_all_configs_structured()

    return jsonify({'success': True, 'configs': configs})


@admin_bp.route('/api/config/schema', methods=['GET'])
@login_required
@admin_required
def get_config_schema_api():
    """获取配置Schema（API）"""
    schema = get_config_schema()
    return jsonify({'success': True, 'schema': schema})


@admin_bp.route('/api/config/update', methods=['POST'])
@login_required
@admin_required
def update_config():
    """更新单个配置"""
    data = request.get_json()
    category = data.get('category')
    updates = data.get('updates', {})

    if not category or not updates:
        return jsonify({'success': False, 'message': '参数不完整'}), 400

    config_service = get_config_service()
    success = config_service.update_env_config(updates, category)

    if success:
        return jsonify({'success': True, 'message': '配置已更新并重载'})
    else:
        return jsonify({'success': False, 'message': '配置更新失败'}), 500


@admin_bp.route('/api/config/batch-update', methods=['POST'])
@login_required
@admin_required
def batch_update_config():
    """批量更新配置"""
    data = request.get_json()
    updates = data.get('updates', {})

    if not updates:
        return jsonify({'success': False, 'message': '没有需要更新的配置'}), 400

    config_service = get_config_service()
    result = config_service.batch_update(updates)

    if result.success:
        return jsonify({
            'success': True,
            'message': result.message,
            'updated_count': result.updated_count
        })
    else:
        return jsonify({
            'success': False,
            'message': result.message,
            'errors': [{'field': e.field, 'message': e.message} for e in result.errors]
        }), 400


@admin_bp.route('/api/reload', methods=['POST'])
@login_required
@admin_required
def reload_config():
    """手动重载配置"""
    config_service = get_config_service()
    config_service._reload_config()

    return jsonify({'success': True, 'message': '配置已重载'})


# ============ 内容审核 ============

@admin_bp.route('/moderation')
@login_required
@admin_required
def moderation():
    """内容审核页面"""
    page = int(request.args.get('page', 1))
    per_page = 20
    tab = request.args.get('tab', 'pending')  # 'pending', 'rejected', 'all'
    
    moderation_service = get_moderation_service()
    
    # 使用新的统计方法
    stats = moderation_service.get_statistics()
    
    # 根据标签获取不同内容
    if tab == 'rejected':
        items, total = moderation_service.get_rejected_content(page, per_page)
    else:
        items, total = moderation_service.get_pending_queue(page, per_page)
    
    # 最近审核历史
    history = ModerationLog.get_recent(20)
    
    return render_template('admin/moderation.html',
                          pending_items=items,
                          total=total,
                          page=page,
                          per_page=per_page,
                          tab=tab,
                          pending_count=stats['pending_count'],
                          approved_today=stats['approved_today'],
                          rejected_today=stats['rejected_today'],
                          history=[h.to_dict(include_author=True) for h in history])


@admin_bp.route('/api/moderation/pending')
@login_required
@admin_required
def get_pending_moderation():
    """获取待审核队列（API）"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    moderation_service = get_moderation_service()
    items, total = moderation_service.get_pending_queue(page, per_page)
    
    return jsonify({
        'success': True,
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page
    })


@admin_bp.route('/api/moderation/rejected')
@login_required
@admin_required
def get_rejected_moderation():
    """获取被拒绝内容（API）"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    moderation_service = get_moderation_service()
    items, total = moderation_service.get_rejected_content(page, per_page)
    
    return jsonify({
        'success': True,
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page
    })


@admin_bp.route('/api/moderation/action', methods=['POST'])
@login_required
@admin_required
def moderation_action():
    """审核操作（批准/拒绝）"""
    data = request.get_json()
    log_id = data.get('log_id')
    action = data.get('action')
    note = data.get('note', '')
    
    if not log_id or action not in ['approve', 'reject']:
        return jsonify({'success': False, 'message': '参数无效'}), 400
    
    moderation_service = get_moderation_service()
    
    if action == 'approve':
        success = moderation_service.approve_content(log_id, current_user.id, note)
    else:
        success = moderation_service.reject_content(log_id, current_user.id, note)
    
    if success:
        return jsonify({'success': True, 'message': '操作成功'})
    else:
        return jsonify({'success': False, 'message': '操作失败'}), 500


# ============ 统计数据 ============

@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """获取统计数据（API）"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    stats = {
        'total': {
            'users': User.query.count(),
            'posts': Post.query.filter_by(status='published').count(),
            'comments': 0,
        },
        'today': {
            'users': User.query.filter(User.created_at >= today).count(),
            'posts': Post.query.filter(
                Post.status == 'published',
                Post.created_at >= today
            ).count(),
            'comments': 0,
        },
        'ai': {
            'total_calls': 0,
            'today_calls': 0,
            'roast_count': 0,
        }
    }

    return jsonify({'success': True, 'stats': stats})


# ============ 猫娘管理 ============

@admin_bp.route('/api/cat-girl/name', methods=['POST'])
@login_required
@admin_required
def update_cat_girl_name():
    """修改猫娘名字"""
    from app.models.cat_girl import update_cat_girl_name as do_update
    
    data = request.get_json()
    new_name = data.get('name', '').strip()
    
    if not new_name:
        return jsonify({'success': False, 'message': '名字不能为空'}), 400
    
    if len(new_name) > 20:
        return jsonify({'success': False, 'message': '名字不能超过20个字符'}), 400
    
    success = do_update(new_name)
    
    if success:
        return jsonify({'success': True, 'message': f'猫娘名字已更新为：{new_name}'})
    else:
        return jsonify({'success': False, 'message': '更新失败'}), 500


@admin_bp.route('/api/cat-girl/info')
@login_required
@admin_required
def get_cat_girl_info():
    """获取猫娘信息"""
    from app.models.cat_girl import get_or_create_cat_girl
    
    cat_girl = get_or_create_cat_girl()
    
    return jsonify({
        'success': True,
        'cat_girl': {
            'id': cat_girl.id,
            'username': cat_girl.username,
            'avatar': cat_girl.avatar,
            'bio': cat_girl.bio
        }
    })



# ============ AI配置测试 ============

@admin_bp.route('/api/ai/test-connection', methods=['POST'])
@login_required
@admin_required
def test_ai_connection():
    """测试AI API连接"""
    from app.services.ai_factory import AIServiceFactory
    
    data = request.get_json()
    config = {
        'api_base': data.get('api_base', '').strip(),
        'api_key': data.get('api_key', '').strip(),
        'model': data.get('model', '').strip()
    }
    
    result = AIServiceFactory.test_connection(config)
    
    return jsonify({
        'success': result.success,
        'message': result.message,
        'model_info': result.model_info,
        'response_time': result.response_time
    })


@admin_bp.route('/api/ai/test-image-api', methods=['POST'])
@login_required
@admin_required
def test_image_api():
    """测试图片生成API连接"""
    from app.services.ai_factory import AIServiceFactory
    
    data = request.get_json()
    config = {
        'api_base': data.get('api_base', '').strip(),
        'api_key': data.get('api_key', '').strip(),
        'model': data.get('model', '').strip()
    }
    
    result = AIServiceFactory.test_image_api(config)
    
    return jsonify({
        'success': result.success,
        'message': result.message,
        'model_info': result.model_info,
        'response_time': result.response_time
    })


@admin_bp.route('/api/ai/module-status', methods=['GET'])
@login_required
@admin_required
def get_ai_module_status():
    """获取所有AI模块的配置状态"""
    from app.services.ai_factory import AIServiceFactory
    
    raw_status = AIServiceFactory.get_all_module_status()
    
    # 转换为前端期望的格式
    status = {}
    for module, info in raw_status.items():
        status[module] = {
            'use_global': info.get('use_global', True),
            'configured': info.get('is_configured', False),
            'model': info.get('model', ''),
        }
    
    return jsonify({
        'success': True,
        'modules': status
    })


# ============ 敏感词管理 ============

@admin_bp.route('/sensitive-words')
@login_required
@admin_required
def sensitive_words():
    """敏感词管理页面"""
    from app.utils.security import SecurityUtils
    words = SecurityUtils.get_sensitive_words()
    return render_template('admin/sensitive_words.html', words=words)


@admin_bp.route('/api/sensitive-words', methods=['GET'])
@login_required
@admin_required
def get_sensitive_words():
    """获取敏感词列表"""
    from app.utils.security import SecurityUtils
    words = SecurityUtils.get_sensitive_words()
    return jsonify({'success': True, 'words': words, 'count': len(words)})


@admin_bp.route('/api/sensitive-words/add', methods=['POST'])
@login_required
@admin_required
def add_sensitive_word():
    """添加敏感词"""
    from app.utils.security import SecurityUtils
    data = request.get_json() or {}
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'success': False, 'message': '请输入敏感词'}), 400
    if SecurityUtils.add_sensitive_word(word):
        return jsonify({'success': True, 'message': f'已添加: {word}'})
    return jsonify({'success': False, 'message': '添加失败（可能已存在）'}), 400


@admin_bp.route('/api/sensitive-words/remove', methods=['POST'])
@login_required
@admin_required
def remove_sensitive_word():
    """删除敏感词"""
    from app.utils.security import SecurityUtils
    data = request.get_json() or {}
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'success': False, 'message': '请指定要删除的敏感词'}), 400
    if SecurityUtils.remove_sensitive_word(word):
        return jsonify({'success': True, 'message': f'已删除: {word}'})
    return jsonify({'success': False, 'message': '删除失败（可能不存在）'}), 400
