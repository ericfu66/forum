"""
安全工具类
提供输入验证、XSS防护、SQL注入防护等功能
"""
import re
import html
import bleach
from flask import request, abort
from functools import wraps


class SecurityUtils:
    """安全工具类"""
    
    # 允许的HTML标签（用于富文本内容）
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'blockquote', 'code', 'pre', 'ul', 'ol', 'li', 'a', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td'
    ]
    
    # 允许的HTML属性
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'code': ['class'],
        'pre': ['class']
    }
    
    # 允许的URL协议
    ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']
    
    @staticmethod
    def sanitize_html(content: str, strip_all: bool = False) -> str:
        """
        清理HTML内容，防止XSS攻击
        
        Args:
            content: 原始HTML内容
            strip_all: 是否移除所有HTML标签
            
        Returns:
            清理后的安全HTML
        """
        if not content:
            return ''
        
        if strip_all:
            # 移除所有HTML标签
            return bleach.clean(content, tags=[], strip=True)
        
        # 清理HTML，只保留安全的标签和属性
        cleaned = bleach.clean(
            content,
            tags=SecurityUtils.ALLOWED_TAGS,
            attributes=SecurityUtils.ALLOWED_ATTRIBUTES,
            protocols=SecurityUtils.ALLOWED_PROTOCOLS,
            strip=True
        )
        
        return cleaned
    
    @staticmethod
    def escape_html(text: str) -> str:
        """
        转义HTML特殊字符
        
        Args:
            text: 原始文本
            
        Returns:
            转义后的文本
        """
        if not text:
            return ''
        return html.escape(text)
    
    @staticmethod
    def validate_username(username: str) -> tuple[bool, str]:
        """
        验证用户名格式
        
        Args:
            username: 用户名
            
        Returns:
            (valid, message): 是否有效及错误消息
        """
        if not username:
            return False, '用户名不能为空'
        
        if len(username) < 3:
            return False, '用户名至少3个字符'
        
        if len(username) > 20:
            return False, '用户名最多20个字符'
        
        # 只允许字母、数字、下划线、中文
        if not re.match(r'^[\w\u4e00-\u9fa5]+$', username):
            return False, '用户名只能包含字母、数字、下划线和中文'
        
        # 检查敏感词
        if SecurityUtils.contains_sensitive_words(username):
            return False, '用户名包含敏感词'
        
        return True, ''
    
    @staticmethod
    def validate_email(email: str) -> tuple[bool, str]:
        """
        验证邮箱格式
        
        Args:
            email: 邮箱地址
            
        Returns:
            (valid, message): 是否有效及错误消息
        """
        if not email:
            return False, '邮箱不能为空'
        
        # 简单的邮箱格式验证
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, '邮箱格式不正确'
        
        if len(email) > 100:
            return False, '邮箱地址过长'
        
        return True, ''
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """
        验证密码强度
        
        Args:
            password: 密码
            
        Returns:
            (valid, message): 是否有效及错误消息
        """
        if not password:
            return False, '密码不能为空'
        
        if len(password) < 6:
            return False, '密码至少6个字符'
        
        if len(password) > 128:
            return False, '密码过长'
        
        # 检查是否包含常见弱密码
        weak_passwords = ['123456', 'password', '123456789', '12345678', 'qwerty', 'abc123']
        if password.lower() in weak_passwords:
            return False, '密码过于简单，请使用更强的密码'
        
        return True, ''
    
    @staticmethod
    def contains_sensitive_words(text: str) -> bool:
        """
        检查文本是否包含敏感词
        
        Args:
            text: 待检查的文本
            
        Returns:
            是否包含敏感词
        """
        # 这里应该从数据库或配置文件加载敏感词列表
        # 简化示例
        sensitive_words = ['admin', 'root', 'system', 'test']
        text_lower = text.lower()
        
        for word in sensitive_words:
            if word in text_lower:
                return True
        
        return False
    
    @staticmethod
    def validate_file_upload(file, allowed_extensions: set, max_size: int = 5 * 1024 * 1024) -> tuple[bool, str]:
        """
        验证文件上传
        
        Args:
            file: 上传的文件对象
            allowed_extensions: 允许的文件扩展名集合
            max_size: 最大文件大小（字节）
            
        Returns:
            (valid, message): 是否有效及错误消息
        """
        if not file or file.filename == '':
            return False, '没有选择文件'
        
        # 检查文件扩展名
        if '.' not in file.filename:
            return False, '文件名无效'
        
        ext = file.filename.rsplit('.', 1)[1].lower()
        if ext not in allowed_extensions:
            return False, f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
        
        # 检查文件大小
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        
        if size > max_size:
            max_mb = max_size / (1024 * 1024)
            return False, f'文件大小不能超过{max_mb:.1f}MB'
        
        return True, ''
    
    @staticmethod
    def generate_safe_filename(filename: str, user_id: int = None) -> str:
        """
        生成安全的文件名
        
        Args:
            filename: 原始文件名
            user_id: 用户ID（可选）
            
        Returns:
            安全的文件名
        """
        import uuid
        from werkzeug.utils import secure_filename
        
        # 使用werkzeug的secure_filename
        safe_name = secure_filename(filename)
        
        # 获取扩展名
        if '.' in safe_name:
            name, ext = safe_name.rsplit('.', 1)
        else:
            name, ext = safe_name, ''
        
        # 生成唯一文件名
        unique_id = uuid.uuid4().hex[:8]
        if user_id:
            new_name = f"{user_id}_{unique_id}"
        else:
            new_name = f"{unique_id}"
        
        if ext:
            new_name = f"{new_name}.{ext}"
        
        return new_name


def rate_limit(max_requests: int = 10, window: int = 60):
    """
    速率限制装饰器
    
    Args:
        max_requests: 时间窗口内最大请求数
        window: 时间窗口（秒）
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from flask import session
            import time
            
            # 获取客户端标识（IP + 用户ID）
            client_id = request.remote_addr
            if hasattr(request, 'user') and request.user:
                client_id += f"_{request.user.id}"
            
            # 获取请求历史
            key = f'rate_limit_{f.__name__}_{client_id}'
            requests = session.get(key, [])
            now = time.time()
            
            # 清理过期的请求记录
            requests = [req_time for req_time in requests if now - req_time < window]
            
            # 检查是否超过限制
            if len(requests) >= max_requests:
                abort(429, description='请求过于频繁，请稍后再试')
            
            # 记录本次请求
            requests.append(now)
            session[key] = requests
            
            return f(*args, **kwargs)
        return wrapped
    return decorator


def require_captcha(f):
    """
    需要验证码的装饰器
    """
    @wraps(f)
    def wrapped(*args, **kwargs):
        from app.services.captcha_service import get_captcha_service
        
        # 从请求中获取验证码
        if request.method == 'POST':
            if request.is_json:
                captcha = request.json.get('captcha', '')
            else:
                captcha = request.form.get('captcha', '')
            
            # 验证验证码
            captcha_service = get_captcha_service()
            success, message = captcha_service.verify_captcha(captcha)
            
            if not success:
                if request.is_json:
                    from flask import jsonify
                    return jsonify({'success': False, 'message': message}), 400
                else:
                    from flask import flash, redirect, url_for
                    flash(message, 'warning')
                    return redirect(request.referrer or url_for('main.index'))
        
        return f(*args, **kwargs)
    return wrapped
