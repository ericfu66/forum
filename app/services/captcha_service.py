"""
验证码服务
生成和验证图形验证码
"""
import random
import string
import io
import base64
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from flask import session


class CaptchaService:
    """验证码服务"""
    
    # 验证码配置
    CAPTCHA_LENGTH = 4
    CAPTCHA_TIMEOUT = 300  # 5分钟过期
    CAPTCHA_WIDTH = 120
    CAPTCHA_HEIGHT = 40
    
    @staticmethod
    def generate_code():
        """生成随机验证码字符串"""
        # 排除容易混淆的字符
        chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
        return ''.join(random.choice(chars) for _ in range(CaptchaService.CAPTCHA_LENGTH))
    
    @staticmethod
    def generate_image(code: str) -> str:
        """
        生成验证码图片
        
        Args:
            code: 验证码文本
            
        Returns:
            base64编码的图片数据URI
        """
        # 创建图片
        width = CaptchaService.CAPTCHA_WIDTH
        height = CaptchaService.CAPTCHA_HEIGHT
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        
        # 绘制干扰线
        for _ in range(3):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            draw.line([(x1, y1), (x2, y2)], fill=(200, 200, 200), width=1)
        
        # 绘制干扰点
        for _ in range(50):
            x = random.randint(0, width)
            y = random.randint(0, height)
            draw.point((x, y), fill=(150, 150, 150))
        
        # 绘制验证码文字
        try:
            # 尝试使用系统字体
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            # 如果没有找到字体，使用默认字体
            font = ImageFont.load_default()
        
        # 计算文字位置
        char_width = width // len(code)
        for i, char in enumerate(code):
            x = char_width * i + random.randint(5, 10)
            y = random.randint(5, 10)
            # 随机颜色
            color = (
                random.randint(0, 100),
                random.randint(0, 100),
                random.randint(0, 100)
            )
            draw.text((x, y), char, font=font, fill=color)
        
        # 添加轻微扭曲
        image = image.filter(ImageFilter.SMOOTH)
        
        # 转换为base64
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f'data:image/png;base64,{img_str}'
    
    @staticmethod
    def create_captcha() -> dict:
        """
        创建验证码并存储到session
        
        Returns:
            包含图片数据URI的字典
        """
        code = CaptchaService.generate_code()
        image_data = CaptchaService.generate_image(code)
        
        # 存储到session
        session['captcha_code'] = code.upper()
        session['captcha_time'] = datetime.now().timestamp()
        
        return {
            'image': image_data,
            'expires_in': CaptchaService.CAPTCHA_TIMEOUT
        }
    
    @staticmethod
    def verify_captcha(user_input: str) -> tuple[bool, str]:
        """
        验证用户输入的验证码
        
        Args:
            user_input: 用户输入的验证码
            
        Returns:
            (success, message): 验证结果和消息
        """
        if not user_input:
            return False, '请输入验证码'
        
        # 检查session中是否有验证码
        stored_code = session.get('captcha_code')
        stored_time = session.get('captcha_time')
        
        if not stored_code or not stored_time:
            return False, '验证码已过期，请刷新'
        
        # 检查是否过期
        if datetime.now().timestamp() - stored_time > CaptchaService.CAPTCHA_TIMEOUT:
            session.pop('captcha_code', None)
            session.pop('captcha_time', None)
            return False, '验证码已过期，请刷新'
        
        # 验证码不区分大小写
        if user_input.upper() != stored_code:
            return False, '验证码错误'
        
        # 验证成功后清除session中的验证码（一次性使用）
        session.pop('captcha_code', None)
        session.pop('captcha_time', None)
        
        return True, '验证成功'
    
    @staticmethod
    def clear_captcha():
        """清除session中的验证码"""
        session.pop('captcha_code', None)
        session.pop('captcha_time', None)


def get_captcha_service():
    """获取验证码服务实例"""
    return CaptchaService()
