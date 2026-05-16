import pytest
from app import create_app
from app.extensions import db
from app.models.user import User


@pytest.fixture
def app():
    """创建测试应用"""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """测试客户端"""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """已登录的测试客户端"""
    with app.test_client() as client:
        with app.app_context():
            # 创建测试用户
            user = User.create('testuser', 'test@test.com', 'password123')
            user_id = user.id

        # 在session中设置验证码并登录
        with client.session_transaction() as sess:
            sess['captcha_code'] = 'TEST'
            sess['captcha_time'] = 9999999999

        client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'password123',
            'captcha': 'TEST'
        }, follow_redirects=True)
        yield client
