"""
帖子路由控制器
处理发帖、回复、评论等功能
"""
import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models.post import Post
from app.models.comment import Comment
from app.models.board import Board
from app.models.like import Like
from app.utils.ai_trigger import ai_roast_trigger
from app.services.knowledge_service import add_post_to_knowledge_async
from app.services.moderation_service import get_moderation_service
from app.extensions import db

post_bp = Blueprint('post', __name__)

# 允许的文件扩展名
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'webm'}


def allowed_image_file(filename):
    """检查是否为允许的图片文件"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_audio_file(filename):
    """检查是否为允许的音频文件"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def save_upload_file(file, subfolder, allowed_check_func):
    """保存上传文件并返回URL"""
    if not file or file.filename == '':
        return None
    
    if not allowed_check_func(file.filename):
        return None
    
    # 生成安全的文件名
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    
    # 确保上传目录存在
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存文件
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)
    
    return f"/static/uploads/{subfolder}/{filename}"


@post_bp.route('/list')
def post_list():
    """帖子列表"""
    board_id = request.args.get('board')
    page = int(request.args.get('page', 1))

    # 获取版块信息
    board = None
    if board_id:
        board = Board.query.get(board_id)

    # 获取帖子列表
    posts, total = Post.find_all(board_id=board_id, page=page, per_page=20)

    return render_template('post/list.html',
                          board=board.to_dict() if board else None,
                          posts=[p.to_dict(include_author=True, include_board=True) for p in posts],
                          page=page,
                          total=total)


@post_bp.route('/<int:post_id>')
def detail(post_id):
    """帖子详情"""
    post = Post.query.get(post_id)
    if not post:
        flash('帖子不存在', 'warning')
        return redirect(url_for('main.index'))

    # 增加浏览次数
    post.increment_view()

    # 获取评论
    comments, _ = Comment.find_by_post(post_id, page=1, per_page=100)

    return render_template('post/detail.html',
                          post=post.to_dict(include_author=True, include_board=True),
                          comments=[c.to_dict(include_author=True) for c in comments])


@post_bp.route('/create', methods=['GET', 'POST'])
@login_required
@ai_roast_trigger
def create():
    """创建帖子"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        board_id = request.form.get('board_id')
        tags = request.form.get('tags', '').split(',') if request.form.get('tags') else []

        if not title or not content or not board_id:
            flash('请填写标题、内容并选择版块', 'warning')
            return redirect(request.referrer or url_for('post.create'))

        # 处理图片上传
        images = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename:
                    url = save_upload_file(file, 'post_images', allowed_image_file)
                    if url:
                        images.append(url)
        
        # 处理语音上传
        audio_url = None
        if 'audio' in request.files:
            audio_file = request.files['audio']
            if audio_file and audio_file.filename:
                audio_url = save_upload_file(audio_file, 'post_audio', allowed_audio_file)

        # 获取版块信息
        board = Board.query.get(board_id)

        # AI内容审核
        moderation_service = get_moderation_service()
        initial_status = 'published'
        
        if moderation_service.is_enabled():
            # 设置初始状态为pending，等待异步审核
            initial_status = 'pending'

        # 创建帖子
        post = Post.create(
            title=title,
            content=content,
            author_id=current_user.id,
            board_id=board_id,
            tags=[t.strip() for t in tags if t.strip()],
            images=images,
            audio_url=audio_url
        )
        
        # 设置帖子状态
        if initial_status != 'published':
            post.status = initial_status
            db.session.commit()
        
        # 启动异步审核
        if moderation_service.is_enabled():
            moderation_service.moderate_content_async(
                content=f'{title}\n{content}',
                content_type='post',
                content_id=post.id,
                title=title,
                author_id=current_user.id
            )
            flash('您的帖子已提交，正在进行审核，审核通过后将自动发布。', 'info')
        else:
            # 审核未启用，直接添加到知识库
            add_post_to_knowledge_async(
                post_id=post.id,
                title=title,
                content=content,
                board_name=board.name if board else None,
                author_name=current_user.username
            )
            flash('发帖成功！', 'success')

        return redirect(url_for('post.detail', post_id=post.id))

    # 获取所有版块
    boards = Board.find_all(active_only=True)

    return render_template('post/create.html', boards=[b.to_dict() for b in boards])


@post_bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    """编辑帖子"""
    post = Post.query.get(post_id)
    if not post:
        flash('帖子不存在', 'warning')
        return redirect(url_for('main.index'))

    # 检查权限
    if post.author_id != current_user.id and not current_user.is_admin():
        flash('无权编辑此帖子', 'danger')
        return redirect(url_for('post.detail', post_id=post_id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('标题和内容不能为空', 'warning')
            return redirect(request.referrer or url_for('post.edit', post_id=post_id))

        # 处理新上传的图片
        new_images = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename:
                    url = save_upload_file(file, 'post_images', allowed_image_file)
                    if url:
                        new_images.append(url)
        
        # 获取保留的旧图片
        keep_images = request.form.getlist('keep_images')
        all_images = keep_images + new_images
        
        # 处理语音上传
        if 'audio' in request.files:
            audio_file = request.files['audio']
            if audio_file and audio_file.filename:
                audio_url = save_upload_file(audio_file, 'post_audio', allowed_audio_file)
                if audio_url:
                    post.audio_url = audio_url
        
        # 检查是否要删除语音
        if request.form.get('remove_audio') == '1':
            post.audio_url = None

        # 更新帖子
        post.title = title
        post.content = content
        post.set_images(all_images)
        post.updated_at = datetime.utcnow()
        db.session.commit()

        flash('帖子已更新', 'success')
        return redirect(url_for('post.detail', post_id=post_id))

    boards = Board.find_all(active_only=True)

    return render_template('post/edit.html',
                          post=post.to_dict(),
                          boards=[b.to_dict() for b in boards])


@post_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete(post_id):
    """删除帖子"""
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'success': False, 'message': '帖子不存在'}), 404

    # 检查权限
    if post.author_id != current_user.id and not current_user.is_admin():
        return jsonify({'success': False, 'message': '无权删除此帖子'}), 403

    # 删除帖子（软删除）
    post.status = 'deleted'
    
    # 同步删除知识库条目
    from app.services.knowledge_service import delete_post_knowledge
    delete_post_knowledge(post_id)
    
    db.session.commit()

    flash('帖子已删除', 'success')
    return jsonify({'success': True})


@post_bp.route('/<int:post_id>/comment', methods=['POST'])
@login_required
@ai_roast_trigger
def add_comment(post_id):
    """添加评论"""
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'success': False, 'message': '帖子不存在'}), 404

    content = request.form.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'message': '评论内容不能为空'}), 400

    # AI内容审核
    moderation_service = get_moderation_service()
    initial_status = 'published'
    
    if moderation_service.is_enabled():
        initial_status = 'pending'

    # 创建评论
    comment = Comment.create(
        post_id=post_id,
        author_id=current_user.id,
        content=content,
        status=initial_status
    )
    
    # 启动异步审核
    if moderation_service.is_enabled():
        moderation_service.moderate_content_async(
            content=content,
            content_type='comment',
            content_id=comment.id,
            title='',
            author_id=current_user.id
        )
        return jsonify({
            'success': True,
            'message': '评论已提交，正在审核中',
            'comment': comment.to_dict(include_author=True),
            'pending': True
        })

    return jsonify({
        'success': True,
        'message': '评论成功',
        'comment': comment.to_dict(include_author=True)
    })


@post_bp.route('/<int:post_id>/like', methods=['POST'])
@login_required
def like(post_id):
    """点赞帖子"""
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'success': False, 'message': '帖子不存在'}), 404

    # 检查是否已点赞
    existing = Like.query.filter_by(
        user_id=current_user.id,
        target_id=post_id,
        target_type='post'
    ).first()

    if existing:
        # 取消点赞
        db.session.delete(existing)
        post.like_count -= 1
        db.session.commit()
        return jsonify({'success': True, 'liked': False})
    else:
        # 点赞
        like = Like(
            user_id=current_user.id,
            target_id=post_id,
            target_type='post'
        )
        db.session.add(like)
        post.like_count += 1
        db.session.commit()
        return jsonify({'success': True, 'liked': True})


@post_bp.route('/board/<slug>')
def board(slug):
    """版块页面"""
    board = Board.find_by_slug(slug)
    if not board:
        flash('版块不存在', 'warning')
        return redirect(url_for('main.index'))

    page = int(request.args.get('page', 1))
    posts, total = Post.find_all(board_id=board.id, page=page, per_page=20)

    return render_template('post/list.html',
                          board=board.to_dict(),
                          posts=[p.to_dict(include_author=True) for p in posts],
                          page=page,
                          total=total)
