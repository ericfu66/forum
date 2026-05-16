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
    
    # 将环境变量中的API配置注入JSON_CONFIG，覆盖文件中的值
    _inject_sensitive_config(app)

    # 根据数据库类型设置引擎选项
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('postgresql'):
        # PostgreSQL 需要连接池配置
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'pool_pre_ping': True,
            'connect_args': {
                'sslmode': 'require',
                'connect_timeout': 10,
            }
        }
    else:
        # SQLite 使用空配置或简单配置
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}

    # 初始化扩展
    from .extensions import init_extensions
    init_extensions(app)

    # 注册自定义过滤器
    register_template_filters(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册SocketIO事件
    from app.controllers import socket

    # 注册上下文处理器
    register_context_processors(app)

    # 注册错误处理器
    register_error_handlers(app)

    return app


def load_json_config(app):
    """加载config.json配置（不再存放敏感信息）"""
    config_path = Path(__file__).parent.parent / 'config.json'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            # 抹掉可能残留的敏感key（强制使用环境变量）
            raw.pop('ai_global', None)
            for mod in raw.get('ai_modules', {}).values():
                if isinstance(mod, dict):
                    mod.pop('api_key', None)
                    mod.pop('fallback_api_key', None)
            raw.pop('embedding', None)
            raw.pop('search', None)
            app.config['JSON_CONFIG'] = raw
    else:
        app.config['JSON_CONFIG'] = {}


def _inject_sensitive_config(app):
    """将环境变量中的API密钥注入JSON_CONFIG，优先于文件配置"""
    jc = app.config.get('JSON_CONFIG', {})
    
    # 全局AI配置
    global_cfg = jc.setdefault('ai_global', {})
    global_cfg['api_key'] = app.config.get('DEEPSEEK_API_KEY', '')
    global_cfg['api_base'] = app.config.get('DEEPSEEK_API_BASE', 'https://api.deepseek.com/v1')
    global_cfg['model'] = app.config.get('DEEPSEEK_MODEL', 'deepseek-chat')
    
    # 各模块配置
    modules = jc.setdefault('ai_modules', {})
    for mod_name in ['moderation', 'chat', 'write', 'roast', 'summarize']:
        mod = modules.setdefault(mod_name, {})
        mod.setdefault('use_global', True)
    
    # 图像模块（独立配置）
    img = modules.setdefault('image', {})
    img['api_key'] = app.config.get('AI_IMAGE_API_KEY', '')
    img['api_base'] = app.config.get('AI_IMAGE_API_BASE', '')
    img['fallback_api_key'] = app.config.get('AI_IMAGE_FALLBACK_API_KEY', '')
    img['fallback_api_base'] = app.config.get('AI_IMAGE_FALLBACK_API_BASE', '')
    
    # 视觉模块
    vision = modules.setdefault('vision', {})
    vision['api_key'] = app.config.get('VISION_API_KEY', '')
    vision['api_base'] = app.config.get('VISION_API_BASE', '')
    
    # Embedding
    emb = jc.setdefault('embedding', {})
    emb['api_key'] = app.config.get('EMBEDDING_API_KEY', '')
    emb['api_base'] = app.config.get('EMBEDDING_API_BASE', '')
    emb['model'] = app.config.get('EMBEDDING_MODEL', 'BAAI/bge-large-zh-v1.5')
    emb['dimensions'] = int(app.config.get('EMBEDDING_DIMENSIONS', 1024))
    
    # 搜索
    srch = jc.setdefault('search', {})
    srch['tavily_api_key'] = app.config.get('TAVILY_API_KEY', '')


def register_template_filters(app):
    """注册自定义Jinja2过滤器"""
    import re
    import uuid
    import base64
    from markupsafe import Markup

    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """将换行符转换为<br>标签"""
        if not text:
            return ''
        from markupsafe import escape
        escaped = escape(text)
        return Markup(str(escaped).replace('\n', '<br>\n'))

    # 配置 markdown 扩展
    import markdown as md_lib
    _md = md_lib.Markdown(
        extensions=['tables', 'fenced_code', 'toc', 'nl2br', 'sane_lists'],
        extension_configs={'toc': {'permalink': False}}
    )

    @app.template_filter('markdown')
    def markdown_filter(text):
        """将Markdown转换为HTML，支持数学公式和代码块高亮"""
        if not text:
            return ''

        # 1. 保护数学公式和代码块
        math_blocks = []
        inline_math = []
        code_blocks = []
        
        def save_math_block(match):
            math_blocks.append(match.group(1))
            return f'%%MATHBLOCK{len(math_blocks)-1}%%'
        text = re.sub(r'\$\$([\s\S]*?)\$\$', save_math_block, text)
        
        def save_inline_math(match):
            inline_math.append(match.group(1))
            return f'%%INLINEMATH{len(inline_math)-1}%%'
        text = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)', save_inline_math, text)

        def save_code_block(match):
            lang = match.group(1) or ''
            code = match.group(2)
            code_blocks.append({'lang': lang, 'code': code})
            return f'%%CODEBLOCK{len(code_blocks)-1}%%'
        text = re.sub(r'```(\w*)\n?([\s\S]*?)```', save_code_block, text)

        # 2. 用标准 Markdown 库解析
        _md.reset()
        html = _md.convert(text)

        # 3. 恢复代码块（带复制按钮和高亮）
        for i, block in enumerate(code_blocks):
            code_id = f'code-{uuid.uuid4().hex[:8]}'
            lang_lower = block["lang"].lower()
            escaped_code = block["code"].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            if lang_lower in ('html', 'htm'):
                code_b64 = base64.b64encode(block["code"].encode('utf-8')).decode('ascii')
                code_html = f'''<div class="html-render-wrapper">
                    <div class="html-render-header">
                        <span>📺 HTML渲染</span>
                        <button class="code-toggle-btn" onclick="toggleHtmlCode('{code_id}')" title="查看源码">📝 源码</button>
                    </div>
                    <div class="html-render-frame" id="frame-{code_id}" data-code="{code_b64}"></div>
                    <div class="html-code-hidden" id="code-wrap-{code_id}" style="display:none;">
                        <pre><code id="{code_id}">{escaped_code}</code></pre>
                    </div>
                </div>'''
            else:
                lang_label = f'<span class="code-lang">{block["lang"]}</span>' if block["lang"] else ''
                code_html = f'''<div class="code-block-wrapper" data-lang="{block['lang']}">
                    <div class="code-block-header">
                        {lang_label}
                        <button class="code-copy-btn" onclick="copyCode('{code_id}')" title="复制代码">📋 复制</button>
                    </div>
                    <pre><code id="{code_id}" class="language-{block['lang']}">{escaped_code}</code></pre>
                </div>'''
            html = html.replace(f'<p>%%CODEBLOCK{i}%%</p>', code_html).replace(f'%%CODEBLOCK{i}%%', code_html)
        
        # 4. 恢复数学公式
        for i, math in enumerate(math_blocks):
            placeholder = f'<p>%%MATHBLOCK{i}%%</p>' if f'<p>%%MATHBLOCK{i}%%</p>' in html else f'%%MATHBLOCK{i}%%'
            html = html.replace(placeholder, f'<div class="math-block">$${math}$$</div>')
        
        for i, math in enumerate(inline_math):
            placeholder = f'<p>%%INLINEMATH{i}%%</p>' if f'<p>%%INLINEMATH{i}%%</p>' in html else f'%%INLINEMATH{i}%%'
            html = html.replace(placeholder, f'<span class="math-inline">${math}$</span>')

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
    from .controllers.follow import follow_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(post_bp, url_prefix='/post')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(message_bp, url_prefix='/messages')
    app.register_blueprint(novel_bp, url_prefix='/novel')
    app.register_blueprint(follow_bp, url_prefix='/follow')


def register_context_processors(app):
    """注册上下文处理器"""
    from .utils.context import inject_config
    app.context_processor(inject_config)


def register_error_handlers(app):
    """注册错误处理器"""
    from flask import render_template, request, jsonify

    def is_api_request():
        """判断是否为API请求"""
        return request.path.startswith('/api/') or '/api/' in request.path

    @app.errorhandler(404)
    def not_found(error):
        if is_api_request():
            return jsonify({'success': False, 'message': '接口不存在'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        if is_api_request():
            return jsonify({'success': False, 'message': '服务器内部错误'}), 500
        return render_template('errors/500.html'), 500
