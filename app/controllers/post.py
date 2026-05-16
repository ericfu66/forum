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
from app.services.knowledge_service import add_post_to_knowledge_async, update_post_knowledge
from app.services.moderation_service import get_moderation_service
from app.services.level_service import add_exp
from app.extensions import db
from sqlalchemy.orm import joinedload

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
    post = Post.query.options(
        joinedload(Post.author),
        joinedload(Post.board)
    ).get(post_id)
    if not post:
        flash('帖子不存在', 'warning')
        return redirect(url_for('main.index'))

    # 增加浏览次数
    post.increment_view()

    # 获取评论（预加载作者）
    comments = Comment.query.options(
        joinedload(Comment.author)
    ).filter_by(post_id=post_id, parent_id=None, status='published')\
     .order_by(Comment.created_at.asc()).limit(100).all()

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

        # AI智能标签生成（用户标签少于2个时触发）
        if not tags or len([t for t in tags if t.strip()]) < 2:
            try:
                from app.services.tag_service import generate_tags_ai, merge_tags
                ai_tags = generate_tags_ai(title, content)
                if ai_tags:
                    from app.models.tag import Tag
                    merged = merge_tags(tags or [], ai_tags)
                    for tag_name in merged:
                        tag = Tag.find_or_create(tag_name)
                        if tag and tag not in post.tags:
                            post.tags.append(tag)
                            tag.post_count += 1
                    db.session.commit()
            except Exception as e:
                current_app.logger.warning(f'AI tag generation failed: {e}')

        # 异步生成帖子摘要
        try:
            from app.tasks.summary_tasks import generate_post_summary_async
            generate_post_summary_async(post.id)
        except Exception as e:
            current_app.logger.warning(f'Post summary task failed: {e}')

        # 增加发帖经验值
        try:
            add_exp(current_user, 'post')
        except Exception as e:
            current_app.logger.warning(f'Add exp failed: {e}')

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

        # 处理标签更新
        tags_str = request.form.get('tags', '')
        if tags_str is not None:
            from app.models.tag import Tag
            new_tag_names = [t.strip() for t in tags_str.split(',') if t.strip()]
            # 清除旧标签计数
            for old_tag in post.tags:
                old_tag.post_count = max(0, old_tag.post_count - 1)
            post.tags.clear()
            # 添加新标签
            for tag_name in new_tag_names:
                tag = Tag.find_or_create(tag_name)
                if tag:
                    post.tags.append(tag)
                    tag.post_count += 1

        db.session.commit()

        # 同步更新知识库
        try:
            update_post_knowledge(post.id, title, content)
        except Exception as e:
            current_app.logger.warning(f'Failed to update knowledge for post {post.id}: {e}')

        # 编辑后重新生成摘要
        post.summary = None
        db.session.commit()
        try:
            from app.tasks.summary_tasks import generate_post_summary_async
            generate_post_summary_async(post.id)
        except Exception as e:
            current_app.logger.warning(f'Post summary task failed: {e}')

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

    # 增加评论经验值
    try:
        add_exp(current_user, 'comment')
    except Exception as e:
        current_app.logger.warning(f'Add comment exp failed: {e}')

    return jsonify({
        'success': True,
        'message': '评论成功',
        'comment': comment.to_dict(include_author=True)
    })


@post_bp.route('/comment/<int:comment_id>/like', methods=['POST'])
@login_required
def like_comment(comment_id):
    """点赞/取消点赞评论"""
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'success': False, 'message': '评论不存在'}), 404

    existing = Like.query.filter_by(
        user_id=current_user.id,
        target_id=comment_id,
        target_type='comment'
    ).first()

    if existing:
        db.session.delete(existing)
        comment.like_count -= 1
        db.session.commit()
        return jsonify({'success': True, 'liked': False, 'like_count': comment.like_count})
    else:
        like = Like(
            user_id=current_user.id,
            target_id=comment_id,
            target_type='comment'
        )
        db.session.add(like)
        comment.like_count += 1
        db.session.commit()
        return jsonify({'success': True, 'liked': True, 'like_count': comment.like_count})


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
        # 给帖子作者增加经验值
        try:
            if post.author_id != current_user.id:
                from app.models.user import User
                author = User.query.get(post.author_id)
                if author:
                    add_exp(author, 'like_received')
        except Exception as e:
            current_app.logger.warning(f'Add like exp failed: {e}')
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


@post_bp.route('/tag/<slug>')
def by_tag(slug):
    """按标签筛选帖子"""
    from app.models.tag import Tag
    tag = Tag.find_by_slug(slug)
    if not tag:
        flash('标签不存在', 'warning')
        return redirect(url_for('main.index'))

    page = int(request.args.get('page', 1))
    posts_query = tag.posts.filter_by(status='published').order_by(Post.created_at.desc())
    pagination = posts_query.paginate(page=page, per_page=20, error_out=False)

    return render_template('post/list.html',
                          tag=tag.to_dict(),
                          posts=[p.to_dict(include_author=True, include_board=True) for p in pagination.items],
                          page=page,
                          total=pagination.total)


@post_bp.route('/<int:post_id>/summary', methods=['POST'])
@login_required
def generate_summary(post_id):
    """按需生成帖子摘要"""
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'success': False, 'message': '帖子不存在'}), 404

    if post.summary:
        return jsonify({'success': True, 'summary': post.summary})

    from app.services.ai_service import get_ai_service
    ai = get_ai_service('write')
    summary = ai.generate_simple(
        f"请用中文为以下帖子生成摘要（2-3句话，不超过150字）：\n"
        f"标题：{post.title}\n内容：{post.content[:2000]}"
    )
    if summary:
        post.summary = summary
        db.session.commit()

    return jsonify({'success': True, 'summary': summary or ''})
