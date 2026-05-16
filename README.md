# 🌐 Forum — AI 驱动的创作社区

> 一个融合人文美学与智能技术的现代化论坛系统。在这里，AI 不仅是工具，更是你的创作伙伴。

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3+-000?logo=flask&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## ✨ 项目亮点

- **🎨 独特视觉设计** — 采用 Editorial 杂志风格排版，Fraunces + Noto Serif SC 字体组合，温暖赭石色调，拒绝千篇一律的"AI 设计"
- **🤖 深度 AI 集成**
  - **AI 对话** — 流式响应，支持多轮上下文
  - **AI 写稿** — 输入主题，自动生成完整文章
  - **AI 绘图** — 文生图，支持画廊展示
  - **AI 代码** — 在线编程助手与代码运行器
  - **AI 小说** — 创意小说生成
  - **AI 吐槽** — 发帖时随机触发幽默 AI 评论
- **👥 完整社区生态** — 版块、发帖、评论、点赞、私信、关注体系
- **🛡️ 后台管理系统** — 用户管理、内容审核、配置热重载、敏感词过滤
- **🌓 深色模式** — 一键切换，护眼体验

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 |
|------|------|
| Python | 3.11+ |
| SQLite | 3.35+ |
| Redis | 7.0+（可选，用于 Celery 任务队列） |

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/ericfu66/forum.git
cd forum

# 2. 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填写你的 DeepSeek API Key 等配置

# 5. 初始化数据库
flask init-db

# 6. 创建管理员（可选）
flask create-admin

# 7. 启动应用
python run.py
```

访问 http://localhost:5000 即可体验。

---

## 📁 项目结构

```
forum/
├── app/
│   ├── __init__.py          # 应用工厂
│   ├── config.py            # 配置管理
│   ├── extensions.py        # 扩展初始化
│   ├── celery.py            # Celery 配置
│   ├── controllers/         # 路由控制器
│   │   ├── main.py          # 首页、搜索
│   │   ├── auth.py          # 认证系统
│   │   ├── post.py          # 帖子管理
│   │   ├── ai.py            # AI 功能
│   │   ├── admin.py         # 后台管理
│   │   └── ...
│   ├── models/              # 数据模型
│   ├── services/            # 业务逻辑层
│   ├── templates/           # Jinja2 模板
│   │   ├── base.html        # 基础布局
│   │   ├── main/index.html  # 首页（Editorial 设计）
│   │   └── ...
│   └── static/              # 静态资源
│       ├── css/             # 样式文件
│       └── js/              # 脚本文件
├── tests/                   # 测试套件
├── migrations/              # 数据库迁移
├── config.json              # 运行时配置
├── .env.example             # 环境变量模板
└── run.py                   # 应用入口
```

---

## 🎯 核心功能

### AI 创作中心

| 功能 | 说明 |
|------|------|
| AI 对话 | 基于 DeepSeek API 的流式对话，支持多轮历史 |
| AI 写稿 | 输入主题和关键词，自动生成文章并保存为帖子 |
| AI 绘图 | 文生图创作，支持画廊展示与下载 |
| AI 代码 | 在线代码运行器，支持 Python/JavaScript 等 |
| AI 小说 | 创意小说生成，支持章节续写 |
| AI 吐槽 | 发帖时按概率自动触发 AI 幽默评论 |

### 论坛社区

- **版块系统** — 支持创建、排序、图标自定义
- **帖子管理** — 富文本编辑器、图片上传、置顶、AI 生成标记
- **评论互动** — 嵌套评论、点赞
- **私信系统** — 实时消息通知（WebSocket）
- **用户体系** — 注册、登录、个人中心、头像上传

### 后台管理

- 仪表盘数据统计
- 用户管理与权限控制
- 内容审核与敏感词管理
- 系统配置热重载（修改 .env 无需重启）
- 操作日志记录

---

## 🛠️ 开发指南

### 常用命令

```bash
# 启动开发服务器
python run.py

# 初始化数据库
flask init-db

# 创建管理员
flask create-admin

# 查看所有路由
flask routes

# 运行测试
pytest
```

### API 接口

```
POST   /auth/api/register           # 用户注册
POST   /auth/api/login              # 用户登录
GET    /auth/api/me                 # 当前用户信息

POST   /ai/api/dialogs              # 创建对话
POST   /ai/api/dialogs/<id>/message # 发送消息（SSE 流式）
POST   /ai/api/write/generate       # 生成文章
POST   /ai/api/image/generate       # 生成图片
POST   /ai/api/roast/trigger        # 触发 AI 吐槽

GET    /admin/api/stats             # 统计数据
GET    /admin/api/config            # 获取配置
POST   /admin/api/config/update     # 更新配置
```

---

## 🎨 设计哲学

本项目主页采用 **Editorial Warmth** 设计语言：

- **排版** — Fraunces（西文）+ Noto Serif SC（中文）作为展示字体，DM Sans 作为正文字体，形成强烈的衬线/无衬线对比
- **色彩** — 暖奶油底色（#faf6f1）搭配深炭文字（#1a120b），赭石赤陶（#c75b39）作为强调色，琥珀金（#d4a373）点缀
- **空间** — 大量留白、非对称布局、网格与有机形态的对比
- **动效** — 滚动揭示动画、数字计数器、优雅的悬停状态

---

## 🚀 生产部署

### 使用 Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

### Systemd 服务示例

```ini
[Unit]
Description=Forum
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/forum
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/forum/app/static;
        expires 1d;
    }
}
```

---

## 📄 许可证

MIT License © 2026

---

> **博学笃志 · 切问近思** — 用技术连接思想，让创作触手可及。
