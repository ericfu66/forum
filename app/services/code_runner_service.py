"""
代码运行服务
安全执行Python代码，支持自定义安装库
"""
import subprocess
import tempfile
import os
import sys
import json
import uuid
import shutil
import threading
import time
import ast
import platform
from pathlib import Path
from flask import current_app


# 允许导入的安全模块
ALLOWED_MODULES = {
    'math', 'random', 'datetime', 'collections', 'itertools', 'functools',
    'string', 're', 'json', 'csv', 'io', 'typing', 'dataclasses', 'enum',
    'copy', 'pprint', 'textwrap', 'heapq', 'bisect', 'decimal', 'fractions',
    'statistics', 'pathlib', 'tempfile', 'hashlib', 'base64', 'uuid',
    'time', 'struct', 'array', 'operator', 'contextlib', 'abc', 'weakref',
    'os',  # 允许os模块，但通过AST检查限制危险函数
    # 安全的第三方库（如果已安装）
    'numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy', 'sympy',
    'PIL', 'jieba', 'tabulate', 'prettytable', 'rich',
    'plotly', 'bokeh', 'altair', 'networkx', 'faker',
}

# 明确禁止的模块
BLOCKED_MODULES = {
    'subprocess', 'shutil', 'socket', 'ctypes', 'importlib',
    'code', 'codeop', 'multiprocessing', 'threading',
    'signal', 'pty', 'fcntl', 'termios', 'resource',
    'webbrowser', 'http', 'ftplib', 'smtplib', 'telnetlib',
    'xmlrpc', 'cgi', 'cgitb', 'wsgiref',
}

# 禁止调用的内置函数
BLOCKED_BUILTINS = {
    'eval', 'exec', 'compile', '__import__', 'globals', 'locals',
    'getattr', 'setattr', 'delattr',
}

# os模块中禁止使用的危险函数
BLOCKED_OS_FUNCTIONS = {
    'system', 'popen', 'exec', 'execv', 'execve', 'execvp', 'execvpe',
    'spawn', 'spawnl', 'spawnle', 'spawnlp', 'spawnlpe',
    'spawnv', 'spawnve', 'spawnvp', 'spawnvpe',
    'remove', 'unlink', 'rmdir', 'removedirs',
    'rename', 'renames', 'replace',
}


class CodeRunnerService:
    """代码运行服务"""

    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 30

    # 最大输出长度
    MAX_OUTPUT_LENGTH = 50000

    # 允许安装的库白名单
    ALLOWED_PACKAGES = [
        'numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy',
        'sympy', 'pillow', 'opencv-python', 'scikit-learn',
        'beautifulsoup4', 'lxml', 'jieba', 'wordcloud',
        'plotly', 'bokeh', 'altair', 'pyecharts',
        'networkx', 'igraph', 'graphviz',
        'faker', 'arrow', 'pendulum', 'dateutil',
        'tabulate', 'prettytable', 'rich',
        'pyyaml', 'toml', 'configparser',
        'tqdm', 'colorama', 'termcolor',
        'regex', 'chardet', 'ftfy',
    ]
    
    def __init__(self):
        self.workspace_base = self._get_workspace_base()
        self._ensure_workspace()
    
    def _get_workspace_base(self):
        """获取工作空间基础路径"""
        try:
            base = current_app.config.get('CODE_RUNNER_WORKSPACE', 'code_workspace')
        except RuntimeError:
            base = 'code_workspace'
        # 确保使用绝对路径
        path = Path(base)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()
    
    def _ensure_workspace(self):
        """确保工作空间目录存在"""
        self.workspace_base.mkdir(parents=True, exist_ok=True)
        # 创建虚拟环境目录
        venv_dir = self.workspace_base / 'venv'
        if not venv_dir.exists():
            self._create_venv(venv_dir)
    
    def _create_venv(self, venv_dir):
        """创建虚拟环境"""
        try:
            subprocess.run(
                [sys.executable, '-m', 'venv', str(venv_dir)],
                check=True,
                capture_output=True,
                timeout=120
            )
        except Exception as e:
            print(f"Failed to create venv: {e}")
    
    def _get_python_executable(self):
        """获取虚拟环境的Python可执行文件"""
        venv_dir = self.workspace_base / 'venv'
        if os.name == 'nt':  # Windows
            python_path = venv_dir / 'Scripts' / 'python.exe'
        else:  # Unix
            python_path = venv_dir / 'bin' / 'python'
        
        if python_path.exists():
            return str(python_path)
        return sys.executable
    
    def _get_pip_executable(self):
        """获取虚拟环境的pip可执行文件"""
        venv_dir = self.workspace_base / 'venv'
        if os.name == 'nt':  # Windows
            pip_path = venv_dir / 'Scripts' / 'pip.exe'
        else:  # Unix
            pip_path = venv_dir / 'bin' / 'pip'
        
        if pip_path.exists():
            return str(pip_path)
        return None
    
    def check_code_safety(self, code: str):
        """
        使用AST分析检查代码安全性

        Returns:
            tuple: (is_safe: bool, message: str)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return True, "语法错误，将在运行时报告"

        for node in ast.walk(tree):
            # 检查import语句
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split('.')[0]
                    if mod in BLOCKED_MODULES:
                        return False, f"禁止导入模块: {alias.name}"
                    if mod not in ALLOWED_MODULES and mod not in BLOCKED_MODULES:
                        return False, f"不允许的模块: {alias.name}"

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module.split('.')[0]
                    if mod in BLOCKED_MODULES:
                        return False, f"禁止从 {node.module} 导入"
                    if mod not in ALLOWED_MODULES and mod not in BLOCKED_MODULES:
                        return False, f"不允许的模块: {node.module}"

                    # os模块特殊处理：允许os.path，限制危险函数
                    if mod == 'os' and node.module != 'os.path':
                        for alias in node.names:
                            if alias.name in BLOCKED_OS_FUNCTIONS:
                                return False, f"禁止使用 os.{alias.name}"

            # 检查内置函数调用
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_BUILTINS:
                    return False, f"禁止调用内置函数: {node.func.id}"
                # 检查os.system()等直接调用
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id == 'os' and node.func.attr in BLOCKED_OS_FUNCTIONS:
                            return False, f"禁止使用 os.{node.func.attr}()"

        return True, "代码安全检查通过"
    
    def run_python(self, code: str, timeout: int = None, user_id: int = None, stdin_input: str = None) -> dict:
        """
        运行Python代码
        
        Args:
            code: Python代码
            timeout: 超时时间（秒）
            user_id: 用户ID（用于隔离工作空间）
            stdin_input: 标准输入内容（用于input()函数）
        
        Returns:
            dict: {success, output, error, execution_time, needs_input, input_prompt}
        """
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        
        # 安全检查
        is_safe, msg = self.check_code_safety(code)
        if not is_safe:
            return {
                'success': False,
                'output': '',
                'error': f'安全检查失败: {msg}',
                'execution_time': 0
            }
        
        # 检查代码是否包含input()调用
        has_input = self._check_has_input(code)
        
        # 创建临时文件
        run_id = str(uuid.uuid4())[:8]
        temp_dir = self.workspace_base / 'runs' / run_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        script_path = temp_dir / 'script.py'
        
        # 包装代码，捕获输出
        wrapped_code = self._wrap_code(code)
        
        try:
            # 写入脚本
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(wrapped_code)
            
            # 执行代码
            start_time = time.time()
            python_exe = self._get_python_executable()
            
            # 准备stdin
            stdin_data = stdin_input if stdin_input else None
            
            # 使用绝对路径执行脚本
            # Linux下添加内存限制（256MB）
            extra_kwargs = {}
            if platform.system() != 'Windows':
                try:
                    import resource
                    def _set_limits():
                        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                    extra_kwargs['preexec_fn'] = _set_limits
                except ImportError:
                    pass

            result = subprocess.run(
                [python_exe, str(script_path.absolute())],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(temp_dir.absolute()),
                env=self._get_safe_env(),
                input=stdin_data,
                **extra_kwargs
            )
            
            execution_time = time.time() - start_time
            
            output = result.stdout
            error = result.stderr
            
            # 检查是否因为缺少输入而失败
            if 'EOFError' in error and has_input and not stdin_input:
                # 检测是否是交互式游戏
                is_game = self._is_interactive_game(code)
                input_count = self._count_input_calls(code)
                
                # 提取input提示信息
                input_prompt = self._extract_input_prompt(code)
                
                message = '程序需要用户输入，请在下方输入框中提供输入数据'
                if is_game or input_count > 5:
                    message = '⚠️ 这是一个交互式程序（如游戏），包含循环中的多次输入。请一次性提供所有需要的输入值，每行一个。由于无法实时交互，程序可能无法正常运行复杂的交互逻辑。'
                
                return {
                    'success': False,
                    'output': output,
                    'error': '',
                    'execution_time': round(execution_time, 3),
                    'needs_input': True,
                    'input_prompt': input_prompt,
                    'is_interactive': is_game,
                    'input_count': input_count,
                    'message': message
                }
            
            # 截断过长输出
            if len(output) > self.MAX_OUTPUT_LENGTH:
                output = output[:self.MAX_OUTPUT_LENGTH] + '\n... (输出已截断)'
            if len(error) > self.MAX_OUTPUT_LENGTH:
                error = error[:self.MAX_OUTPUT_LENGTH] + '\n... (错误信息已截断)'
            
            # 检查是否有图片输出
            images = self._collect_images(temp_dir)
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'error': error,
                'execution_time': round(execution_time, 3),
                'images': images
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': '',
                'error': f'执行超时（{timeout}秒）',
                'execution_time': timeout
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': f'执行错误: {str(e)}',
                'execution_time': 0
            }
        finally:
            # 清理临时文件（延迟清理，保留图片）
            self._schedule_cleanup(temp_dir, delay=300)
    
    def _wrap_code(self, code: str) -> str:
        """包装代码，添加输出捕获和异常处理"""
        indented_code = self._indent_code(code, 4)
        return f'''# -*- coding: utf-8 -*-
import sys
import io

# 捕获stdout/stderr
_stdout_capture = io.StringIO()
_stderr_capture = io.StringIO()
_orig_stdout = sys.stdout
_orig_stderr = sys.stderr

# 重定向matplotlib输出
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _plt_available = True
except ImportError:
    _plt_available = False

sys.stdout = _stdout_capture
sys.stderr = _stderr_capture

try:
{indented_code}
except Exception as _e:
    sys.stdout = _orig_stdout
    sys.stderr = _orig_stderr
    print(f"{{type(_e).__name__}}: {{_e}}", file=sys.stderr)
finally:
    sys.stdout = _orig_stdout
    sys.stderr = _orig_stderr
    print(_stdout_capture.getvalue(), end='')
    _err = _stderr_capture.getvalue()
    if _err:
        print(_err, file=sys.stderr, end='')

# 保存matplotlib图片
if _plt_available and plt.get_fignums():
    for i, fig_num in enumerate(plt.get_fignums()):
        plt.figure(fig_num)
        plt.savefig(f'output_{{i}}.png', dpi=100, bbox_inches='tight')
    plt.close('all')
'''

    def _indent_code(self, code: str, spaces: int) -> str:
        """缩进代码块"""
        indent = ' ' * spaces
        lines = code.split('\n')
        return '\n'.join(indent + line if line.strip() else '' for line in lines)
    
    def _get_safe_env(self) -> dict:
        """获取安全的环境变量"""
        safe_env = os.environ.copy()
        # 移除敏感环境变量
        sensitive_vars = ['SECRET_KEY', 'DATABASE_URL', 'API_KEY', 'PASSWORD']
        for var in list(safe_env.keys()):
            if any(s in var.upper() for s in sensitive_vars):
                del safe_env[var]
        return safe_env
    
    def _collect_images(self, temp_dir: Path) -> list:
        """收集生成的图片"""
        images = []
        for img_file in temp_dir.glob('output_*.png'):
            # 读取图片并转为base64
            import base64
            with open(img_file, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
                images.append(f'data:image/png;base64,{img_data}')
        return images
    
    def _check_has_input(self, code: str) -> bool:
        """检查代码是否包含input()调用"""
        import re
        # 匹配input()调用，排除注释中的
        lines = code.split('\n')
        for line in lines:
            # 去除注释
            if '#' in line:
                line = line[:line.index('#')]
            if 'input(' in line:
                return True
        return False
    
    def _count_input_calls(self, code: str) -> int:
        """统计代码中input()调用的数量（不包括循环中的）"""
        import re
        count = 0
        in_loop = False
        loop_depth = 0
        lines = code.split('\n')
        
        for line in lines:
            stripped = line.strip()
            # 去除注释
            if '#' in stripped:
                stripped = stripped[:stripped.index('#')]
            
            # 检测循环开始
            if re.match(r'^(while|for)\s+', stripped):
                in_loop = True
                loop_depth += 1
            
            # 检测循环结束（简单判断缩进）
            if in_loop and stripped and not line.startswith(' ') and not line.startswith('\t'):
                if not re.match(r'^(while|for|if|elif|else|try|except|finally|def|class)\s*', stripped):
                    loop_depth = 0
                    in_loop = False
            
            # 统计input调用
            if 'input(' in stripped:
                if in_loop:
                    count += 10  # 循环中的input标记为多次
                else:
                    count += 1
        
        return count
    
    def _is_interactive_game(self, code: str) -> bool:
        """检测代码是否是交互式游戏（循环中有input）"""
        import re
        lines = code.split('\n')
        in_loop = False
        
        for line in lines:
            stripped = line.strip()
            if '#' in stripped:
                stripped = stripped[:stripped.index('#')]
            
            if re.match(r'^(while|for)\s+', stripped):
                in_loop = True
            
            if in_loop and 'input(' in stripped:
                return True
        
        return False
    
    def _extract_input_prompt(self, code: str) -> list:
        """提取代码中的input()提示信息"""
        import re
        prompts = []
        # 匹配 input("提示") 或 input('提示') 或 input(f"提示")
        pattern = r'input\s*\(\s*[f]?["\']([^"\']*)["\']'
        matches = re.findall(pattern, code)
        for match in matches:
            # 清理f-string中的变量占位符
            clean_match = re.sub(r'\{[^}]+\}', '...', match)
            prompts.append(clean_match.strip())
        if not prompts:
            prompts = ['请输入']
        return prompts
    
    def _schedule_cleanup(self, path: Path, delay: int = 300):
        """延迟清理临时文件"""
        def cleanup():
            time.sleep(delay)
            try:
                if path.exists():
                    shutil.rmtree(path)
            except Exception:
                pass
        
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
    
    def install_package(self, package_name: str, user_id: int = None) -> dict:
        """
        安装Python包
        
        Args:
            package_name: 包名
            user_id: 用户ID
        
        Returns:
            dict: {success, message}
        """
        # 清理包名
        package_name = package_name.strip().lower()
        
        # 检查是否在白名单中
        base_name = package_name.split('==')[0].split('>=')[0].split('<=')[0]
        if base_name not in self.ALLOWED_PACKAGES:
            return {
                'success': False,
                'message': f'包 {package_name} 不在允许安装的列表中。\n允许的包: {", ".join(self.ALLOWED_PACKAGES[:10])}...'
            }
        
        pip_exe = self._get_pip_executable()
        if not pip_exe:
            return {
                'success': False,
                'message': '虚拟环境未正确配置'
            }
        
        try:
            result = subprocess.run(
                [pip_exe, 'install', package_name, '--quiet'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'成功安装 {package_name}'
                }
            else:
                return {
                    'success': False,
                    'message': f'安装失败: {result.stderr}'
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'message': '安装超时'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'安装错误: {str(e)}'
            }
    
    def list_installed_packages(self) -> list:
        """列出已安装的包"""
        pip_exe = self._get_pip_executable()
        if not pip_exe:
            return []
        
        try:
            result = subprocess.run(
                [pip_exe, 'list', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return [{'name': p['name'], 'version': p['version']} for p in packages]
        except Exception:
            pass
        return []
    
    def get_allowed_packages(self) -> list:
        """获取允许安装的包列表"""
        return self.ALLOWED_PACKAGES.copy()


# 单例
_code_runner_service = None

def get_code_runner_service() -> CodeRunnerService:
    """获取代码运行服务实例"""
    global _code_runner_service
    if _code_runner_service is None:
        _code_runner_service = CodeRunnerService()
    return _code_runner_service
