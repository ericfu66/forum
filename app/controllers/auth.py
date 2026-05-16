"""
认证路由控制器
处理用户注册、登录、登出等
"""
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from app.services.auth_service import AuthService
from app.services.captcha_service import get_captcha_service
from app.models.user import User
from app.extensions import db
from app.utils.security import SecurityUtils, rate_limit

auth_bp = Blueprint('auth', __name__)

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@auth_bp.route('/register', methods=['GET', 'POST'])
@rate_limit(max_requests=5, window=300)  # 5分钟内最多5次注册尝试
def register():
    """用户注册"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        captcha = request.form.get('captcha', '').strip()

        # 验证验证码
        captcha_service = get_captcha_service()
        success, message = captcha_service.verify_captcha(captcha)
        if not success:
            flash(message, 'warning')
            return render_template('auth/register.html')

        # 验证输入
        if not username or not email or not password:
            flash('请填写所有必填项', 'warning')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('两次输入的密码不一致', 'warning')
            return render_template('auth/register.html')

        # 尝试注册
        success, message, user = AuthService.register(username, email, password)

        if success:
            flash(message, 'success')
            login_user(user)
            return redirect(url_for('main.index'))
        else:
            flash(message, 'danger')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@rate_limit(max_requests=10, window=300)  # 5分钟内最多10次登录尝试
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        captcha = request.form.get('captcha', '').strip()

        # 验证验证码
        captcha_service = get_captcha_service()
        success, message = captcha_service.verify_captcha(captcha)
        if not success:
            flash(message, 'warning')
            return render_template('auth/login.html')

        success, message, user = AuthService.login(username, password, remember)

        if success:
            # 登录用户
            login_user(user, remember=remember)
            # 获取重定向地址
            next_page = request.args.get('next')
            flash(message, 'success')
            return redirect(next_page or url_for('main.index'))
        else:
            flash(message, 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    flash('已成功登出', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile')
@login_required
def profile():
    """个人资料页面"""
    user_dict = current_user.to_dict(include_stats=True)
    # 如果访问的是自己的资料，is_following 为 None（不显示按钮）
    # 但模板里已经通过 current_user.id != user.id 判断了
    return render_template('user/profile.html', user=user_dict, is_following=False)


@auth_bp.route('/profile/<int:user_id>')
def public_profile(user_id):
    """公开用户资料页面"""
    from app.models.user import User
    user = User.query.get(user_id)
    if not user:
        flash('用户不存在', 'warning')
        return redirect(url_for('main.index'))

    user_dict = user.to_dict(include_stats=True)
    is_following = False
    if current_user.is_authenticated and current_user.id != user_id:
        is_following = current_user.is_following(user)

    return render_template('user/profile.html', user=user_dict, is_following=is_following)


@auth_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """个人设置页面"""
    from app.extensions import db

    if request.method == 'POST':
        bio = request.form.get('bio', '').strip()
        theme = request.form.get('theme', 'light')

        # 更新个人资料
        current_user.bio = bio
        current_user.preferences = {'theme': theme}
        db.session.commit()

        flash('设置已保存', 'success')
        return redirect(url_for('auth.settings'))

    return render_template('user/settings.html', user=current_user.to_dict())


@auth_bp.route('/password', methods=['POST'])
@login_required
def change_password():
    """修改密码"""
    old_password = request.form.get('old_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if new_password != confirm_password:
        flash('两次输入的新密码不一致', 'warning')
        return redirect(url_for('auth.settings'))

    success, message = AuthService.update_password(
        current_user.id, old_password, new_password
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('auth.settings'))


# API路由
@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """API注册接口"""
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    success, message, user = AuthService.register(username, email, password)

    if success:
        return jsonify({'success': True, 'message': message, 'user': user.to_dict()})
    else:
        return jsonify({'success': False, 'message': message}), 400


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """API登录接口"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    remember = data.get('remember', False)

    success, message, user = AuthService.login(username, password, remember)

    if success:
        login_user(user, remember=remember)
        return jsonify({'success': True, 'message': message, 'user': user.to_dict()})
    else:
        return jsonify({'success': False, 'message': message}), 401


@auth_bp.route('/api/me')
@login_required
def api_me():
    """获取当前用户信息"""
    return jsonify({'success': True, 'user': current_user.to_dict()})


# ============ 验证码API ============

@auth_bp.route('/api/captcha', methods=['GET'])
def get_captcha():
    """获取验证码"""
    captcha_service = get_captcha_service()
    captcha_data = captcha_service.create_captcha()
    return jsonify({
        'success': True,
        'image': captcha_data['image'],
        'expires_in': captcha_data['expires_in']
    })


@auth_bp.route('/api/captcha/refresh', methods=['POST'])
def refresh_captcha():
    """刷新验证码"""
    captcha_service = get_captcha_service()
    captcha_service.clear_captcha()
    captcha_data = captcha_service.create_captcha()
    return jsonify({
        'success': True,
        'image': captcha_data['image'],
        'expires_in': captcha_data['expires_in']
    })


# ============ 头像管理 ============

@auth_bp.route('/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """上传头像"""
    if 'avatar' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400

    file = request.files['avatar']

    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': '不支持的文件格式'}), 400

    # 检查文件大小 (2MB)
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > 2 * 1024 * 1024:
        return jsonify({'success': False, 'message': '文件大小不能超过2MB'}), 400

    # 确保上传目录存在
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_folder, exist_ok=True)

    # 生成唯一文件名
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(upload_folder, filename)

    # 删除旧头像文件（如果存在且不是默认头像）
    if current_user.avatar and 'uploads/avatars/' in current_user.avatar:
        old_avatar = os.path.join(current_app.root_path, 'static', current_user.avatar.lstrip('/static/'))
        if os.path.exists(old_avatar):
            try:
                os.remove(old_avatar)
            except:
                pass

    # 保存新头像
    file.save(filepath)

    # 更新用户头像路径
    avatar_url = f'/static/uploads/avatars/{filename}'
    current_user.avatar = avatar_url
    db.session.commit()

    return jsonify({'success': True, 'avatar': avatar_url})


@auth_bp.route('/avatar/preset', methods=['POST'])
@login_required
def set_preset_avatar():
    """设置预设头像（emoji）"""
    data = request.get_json()
    avatar_emoji = data.get('avatar', '😀')

    # 验证是否为有效的emoji
    valid_emojis = ['😀', '😎', '🤖', '🐱', '🦊', '🐼', '🐶', '🐰', '🦁', '🐻']
    if avatar_emoji not in valid_emojis:
        avatar_emoji = '😀'

    # 生成SVG头像URL (使用data URI)
    svg_avatar = generate_emoji_avatar(avatar_emoji)
    current_user.avatar = svg_avatar
    db.session.commit()

    return jsonify({'success': True, 'avatar': svg_avatar})


def generate_emoji_avatar(emoji):
    """生成emoji头像的data URI"""
    # 使用简单的SVG来显示emoji
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <rect width="100" height="100" fill="#8b5cf6"/>
        <text x="50" y="65" font-size="50" text-anchor="middle">{emoji}</text>
    </svg>'''
    import base64
    svg_base64 = base64.b64encode(svg.encode()).decode()
    return f'data:image/svg+xml;base64,{svg_base64}'
