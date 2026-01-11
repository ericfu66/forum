"""
认证服务
处理用户注册、登录等认证相关逻辑
"""
from app.models.user import User
from app.utils.security import SecurityUtils


class AuthService:
    """认证服务"""

    @staticmethod
    def register(username: str, email: str, password: str) -> tuple[bool, str, User]:
        """
        用户注册

        Returns:
            (success, message, user): 成功状态、消息、用户对象
        """
        # 验证用户名
        valid, message = SecurityUtils.validate_username(username)
        if not valid:
            return False, message, None
        
        # 验证邮箱
        valid, message = SecurityUtils.validate_email(email)
        if not valid:
            return False, message, None
        
        # 验证密码
        valid, message = SecurityUtils.validate_password(password)
        if not valid:
            return False, message, None
        
        # 检查用户名是否已存在
        if User.find_by_username(username):
            return False, '用户名已存在', None

        # 检查邮箱是否已存在
        if User.find_by_email(email):
            return False, '邮箱已被注册', None

        # 创建用户
        user = User.create(username=username, email=email, password=password)
        
        # 发送猫娘欢迎消息
        AuthService._send_welcome_message(user.id)

        return True, '注册成功', user
    
    @staticmethod
    def _send_welcome_message(user_id: int):
        """发送猫娘欢迎消息给新用户"""
        try:
            from app.services.cat_girl_service import get_cat_girl_service
            cat_girl_service = get_cat_girl_service()
            cat_girl_service.send_welcome_message(user_id)
        except Exception as e:
            # 欢迎消息发送失败不影响注册
            import logging
            logging.error(f'Failed to send welcome message: {str(e)}')

    @staticmethod
    def login(username: str, password: str, remember: bool = False) -> tuple[bool, str, User]:
        """
        用户登录

        Returns:
            (success, message, user): 成功状态、消息、用户对象
        """
        # 基本验证
        if not username or not password:
            return False, '用户名和密码不能为空', None
        
        # 尝试用用户名查找
        user = User.find_by_username(username)

        # 如果用户名不存在，尝试用邮箱查找
        if not user:
            user = User.find_by_email(username)

        # 检查用户是否存在
        if not user:
            return False, '用户名或邮箱不存在', None

        # 检查密码
        if not user.check_password(password):
            return False, '密码错误', None

        # 检查是否被封禁
        if user.is_banned:
            return False, '该账号已被封禁', None

        return True, '登录成功', user

    @staticmethod
    def update_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
        """修改密码"""
        from app.extensions import db

        user = User.query.get(user_id)
        if not user:
            return False, '用户不存在'

        if not user.check_password(old_password):
            return False, '原密码错误'

        # 验证新密码
        valid, message = SecurityUtils.validate_password(new_password)
        if not valid:
            return False, message

        user.set_password(new_password)
        db.session.commit()

        return True, '密码修改成功'
