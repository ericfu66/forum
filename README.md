# AI Forum

一个使用 Python Flask + MongoDB + DeepSeek API 构建的现代化 AI 论坛系统。

## ✨ 特性

- 🎨 **清新UI设计** - 蓝绿色系主题，支持浅色/深色模式切换
- 🤖 **AI功能集成**
  - **AI吐槽** - 发帖时随机概率触发AI幽默评论
  - **AI对话** - 支持流式响应的AI聊天功能
  - **AI写稿** - 输入主题自动生成文章内容
- 👥 **用户系统** - 完整的注册、登录、权限管理
- 📝 **论坛功能** - 版块、发帖、回复、评论、点赞
- 🛡️ **后台管理** - 用户管理、内容审核、配置热重载

## 🚀 快速开始

### 环境要求

- Python 3.8+
- MongoDB 4.0+

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd forum
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下关键项：

```ini
# DeepSeek API配置
DEEPSEEK_API_KEY=sk-your-api-key-here

# MongoDB配置
MONGO_URI=mongodb://localhost:27017/forum_db

# Flask密钥（生产环境请修改）
SECRET_KEY=your-secret-key-here
```

4. **启动MongoDB**

确保MongoDB服务已启动：

```bash
# Windows
net start MongoDB

# Linux/Mac
mongod --dbpath /path/to/data
```

5. **初始化数据库**

```bash
flask init-db
```

6. **创建管理员账户**（可选）

```bash
flask create-admin
```

7. **运行应用**

```bash
python run.py
```

访问 http://localhost:5000 查看论坛。

## 📁 项目结构

```
forum/
├── app/                    # 应用主目录
│   ├── __init__.py        # 应用工厂
│   ├── config.py          # 配置类
│   ├── extensions.py      # 扩展初始化
│   ├── models/            # 数据模型
│   ├── services/          # 业务逻辑
│   ├── controllers/       # 路由控制器
│   ├── utils/             # 工具函数
│   ├── static/            # 静态文件
│   │   ├── css/          # 样式文件
│   │   └── js/           # JavaScript文件
│   └── templates/         # Jinja2模板
├── .env                   # 环境配置
├── .env.example           # 配置示例
├── config.json            # 运行时配置
├── requirements.txt       # Python依赖
└── run.py                # 应用入口
```

## 🎯 核心功能

### AI吐槽

- 发帖/回复时按配置的概率自动触发
- 可在后台管理中调整触发概率
- 支持手动触发AI吐槽

### AI对话

- 流式响应，实时显示AI回复
- 支持多轮对话历史
- 对话记录持久化

### AI写稿

- 输入主题和关键词自动生成文章
- 支持选择文章长度
- 可直接保存为帖子

### 配置热重载

- 后台可直接修改.env配置
- 修改后自动重载，无需重启
- 记录配置变更历史

## 🎨 自定义主题

### 配色方案

在 `app/static/css/base.css` 中修改CSS变量：

```css
:root {
    --bg-primary: #E3F2FD;      /* 背景色 */
    --primary-color: #2196F3;   /* 主色调 */
    --secondary-color: #4CAF50; /* 辅助色 */
}
```

### 添加新版块

1. 登录后台管理
2. 进入"版块管理"
3. 点击"创建版块"
4. 填写版块信息并保存

## 🔧 API文档

### 认证API

```
POST /auth/api/register  # 用户注册
POST /auth/api/login     # 用户登录
GET  /auth/api/me        # 获取当前用户信息
```

### AI功能API

```
POST /ai/api/dialogs              # 创建对话
POST /ai/api/dialogs/<id>/message # 发送消息（SSE）
POST /ai/api/write/generate       # 生成文章
POST /ai/api/roast/trigger        # 触发AI吐槽
```

### 后台管理API

```
GET  /admin/api/config        # 获取配置
POST /admin/api/config/update # 更新配置
GET  /admin/api/stats         # 获取统计数据
```

## 📝 开发命令

```bash
# 初始化数据库
flask init-db

# 创建管理员
flask create-admin

# 查看所有路由
flask routes

# 启动开发服务器
python run.py
```

## 🚀 生产部署

### 使用Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### 使用Systemd服务

创建 `/etc/systemd/system/forum.service`：

```ini
[Unit]
Description=AI Forum
After=network.target mongodb.service

[Service]
User=www-data
WorkingDirectory=/path/to/forum
ExecStart=/usr/bin/gunicorn -w 4 -b 127.0.0.1:5000 run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static {
        alias /path/to/forum/app/static;
    }
}
```

## 📄 许可证

MIT License

## 🙏 致谢

- [Flask](https://flask.palletsprojects.com/) - Web框架
- [MongoDB](https://www.mongodb.com/) - 数据库
- [DeepSeek](https://www.deepseek.com/) - AI服务提供商
