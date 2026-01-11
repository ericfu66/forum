from flask import Flask
import json
import os
from pathlib import Path


def create_app(config_name='default'):
    """Flask应用工厂"""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # 加载配置类
    from .config import config_by_name
    app.config.from_object(config_by_name[config_name])

    # 加载config.json
    load_json_config(app)

    # 初始化扩展
    from .extensions import init_extensions
    init_extensions(app)

    # 注册自定义过滤器
    register_template_filters(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册上下文处理器
    register_context_processors(app)

    # 注册错误处理器
    register_error_handlers(app)

    return app


def load_json_config(app):
    """加载config.json配置"""
    config_path = Path(__file__).parent.parent / 'config.json'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            app.config['JSON_CONFIG'] = json.load(f)
    else:
        app.config['JSON_CONFIG'] = {}


def register_template_filters(app):
    """注册自定义Jinja2过滤器"""

    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """将换行符转换为<br>标签"""
        if not text:
            return ''
        from markupsafe import escape, Markup
        escaped = escape(text)
        return Markup(str(escaped).replace('\n', '<br>\n'))

    @app.template_filter('markdown')
    def markdown_filter(text):
        """将Markdown转换为HTML，支持数学公式和化学方程式"""
        if not text:
            return ''
        import re
        import uuid
        from markupsafe import Markup

        html = text
        
        # 保护数学公式
        math_blocks = []
        inline_math = []
        code_blocks = []
        
        # 保护块级数学公式 $$...$$
        def save_math_block(match):
            math_blocks.append(match.group(1))
            return f'%%MATHBLOCK{len(math_blocks)-1}%%'
        html = re.sub(r'\$\$([\s\S]*?)\$\$', save_math_block, html)
        
        # 保护行内数学公式 $...$
        def save_inline_math(match):
            inline_math.append(match.group(1))
            return f'%%INLINEMATH{len(inline_math)-1}%%'
        html = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)', save_inline_math, html)

        # 保护代码块（带复制按钮）
        def save_code_block(match):
            lang = match.group(1) or ''
            code = match.group(2).strip()
            code_blocks.append({'lang': lang, 'code': code})
            return f'%%CODEBLOCK{len(code_blocks)-1}%%'
        html = re.sub(r'```(\w*)\n?([\s\S]*?)```', save_code_block, html)

        # 行内代码
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        # 标题
        html = re.sub(r'^######\s+(.+)$', r'<h6>\1</h6>', html, flags=re.MULTILINE)
        html = re.sub(r'^#####\s+(.+)$', r'<h5>\1</h5>', html, flags=re.MULTILINE)
        html = re.sub(r'^####\s+(.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

        # 粗体和斜体（支持跨行）
        html = re.sub(r'\*\*\*([^*]+?)\*\*\*', r'<strong><em>\1</em></strong>', html, flags=re.DOTALL)
        html = re.sub(r'\*\*([^*]+?)\*\*', r'<strong>\1</strong>', html, flags=re.DOTALL)
        html = re.sub(r'\*([^*]+?)\*', r'<em>\1</em>', html)
        html = re.sub(r'~~(.+?)~~', r'<del>\1</del>', html)

        # 引用块
        html = re.sub(r'^>\s+(.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

        # 分隔线
        html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
        html = re.sub(r'^\*\*\*$', r'<hr>', html, flags=re.MULTILINE)

        # 链接
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', html)

        # 图片
        html = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" loading="lazy">', html)

        # 任务列表
        html = re.sub(r'^-\s+\[x\]\s+(.+)$', r'<div class="task-item task-done"><span class="task-checkbox">☑</span> \1</div>', html, flags=re.MULTILINE)
        html = re.sub(r'^-\s+\[\s?\]\s+(.+)$', r'<div class="task-item"><span class="task-checkbox">☐</span> \1</div>', html, flags=re.MULTILINE)

        # 无序列表
        html = re.sub(r'^-\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html)

        # 有序列表
        html = re.sub(r'^\d+\.\s+(.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)

        # 段落
        paragraphs = html.split('\n\n')
        processed = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                p = f'<p>{p}</p>'
            processed.append(p)
        html = '\n'.join(processed)

        # 单换行变<br>
        html = html.replace('\n', '<br>\n')

        # 清理多余的<br>
        html = re.sub(r'(</(h[1-6]|p|div|ul|ol|li|pre|blockquote|hr)>)<br>', r'\1', html)
        html = re.sub(r'<br>\n(<(h[1-6]|p|div|ul|ol|li|pre|blockquote))', r'\n<\2', html)
        
        # 恢复代码块（带复制按钮）
        for i, block in enumerate(code_blocks):
            code_id = f'code-{uuid.uuid4().hex[:8]}'
            lang_label = f'<span class="code-lang">{block["lang"]}</span>' if block["lang"] else ''
            escaped_code = block["code"].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            code_html = f'''<div class="code-block-wrapper">
                <div class="code-block-header">
                    {lang_label}
                    <button class="code-copy-btn" onclick="copyCode('{code_id}')" title="复制代码">📋 复制</button>
                </div>
                <pre><code id="{code_id}" class="language-{block['lang']}">{escaped_code}</code></pre>
            </div>'''
            html = html.replace(f'%%CODEBLOCK{i}%%', code_html)
        
        # 恢复数学公式
        for i, math in enumerate(math_blocks):
            html = html.replace(f'%%MATHBLOCK{i}%%', f'<div class="math-block">$${math}$$</div>')
        
        for i, math in enumerate(inline_math):
            html = html.replace(f'%%INLINEMATH{i}%%', f'<span class="math-inline">${math}$</span>')

        return Markup(html)

    @app.template_filter('truncate_md')
    def truncate_md_filter(text, length=200):
        """截断Markdown文本"""
        if not text:
            return ''
        import re
        plain = re.sub(r'[#*`~\[\]()>]', '', text)
        plain = re.sub(r'\n+', ' ', plain)
        if len(plain) > length:
            return plain[:length] + '...'
        return plain


def register_blueprints(app):
    """注册所有蓝图"""
    from .controllers.main import main_bp
    from .controllers.auth import auth_bp
    from .controllers.post import post_bp
    from .controllers.ai import ai_bp
    from .controllers.admin import admin_bp
    from .controllers.message import message_bp
    from .controllers.novel import novel_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(post_bp, url_prefix='/post')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(message_bp, url_prefix='/messages')
    app.register_blueprint(novel_bp, url_prefix='/novel')


def register_context_processors(app):
    """注册上下文处理器"""
    from .utils.context import inject_config
    app.context_processor(inject_config)


def register_error_handlers(app):
    """注册错误处理器"""
    from flask import render_template

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
