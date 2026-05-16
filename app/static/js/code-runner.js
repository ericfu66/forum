/**
 * 代码运行器组件
 * 支持Python代码运行和HTML渲染
 */

class CodeRunner {
    constructor(options = {}) {
        this.container = options.container || null;
        this.onOutput = options.onOutput || null;
        this.onError = options.onError || null;
        this.theme = options.theme || 'light';
        
        this.isRunning = false;
        this.installedPackages = [];
        this.allowedPackages = [];
        this.pendingCode = null;  // 等待输入的代码
        
        this.init();
    }
    
    init() {
        this.loadPackages();
    }
    
    async loadPackages() {
        try {
            const response = await fetch('/ai/api/code/packages');
            const data = await response.json();
            if (data.success) {
                this.installedPackages = data.installed || [];
                this.allowedPackages = data.allowed || [];
            }
        } catch (e) {
            console.error('Failed to load packages:', e);
        }
    }
    
    /**
     * 运行Python代码
     */
    async runPython(code, timeout = 30, stdinInput = null) {
        if (this.isRunning) {
            return { success: false, error: '代码正在运行中...' };
        }
        
        if (!code || !code.trim()) {
            return { success: false, error: '代码不能为空' };
        }
        
        this.isRunning = true;
        
        try {
            const body = { code, timeout };
            if (stdinInput !== null) {
                body.stdin_input = stdinInput;
            }
            
            const response = await fetch('/ai/api/code/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            const result = await response.json();
            
            if (this.onOutput && result.success) {
                this.onOutput(result);
            }
            if (this.onError && !result.success && !result.needs_input) {
                this.onError(result);
            }
            
            return result;
        } catch (e) {
            const error = { success: false, error: e.message };
            if (this.onError) this.onError(error);
            return error;
        } finally {
            this.isRunning = false;
        }
    }
    
    /**
     * 安装Python包
     */
    async installPackage(packageName) {
        if (!packageName || !packageName.trim()) {
            return { success: false, message: '包名不能为空' };
        }
        
        try {
            const response = await fetch('/ai/api/code/install', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ package: packageName })
            });
            
            const result = await response.json();
            
            if (result.success) {
                await this.loadPackages();
            }
            
            return result;
        } catch (e) {
            return { success: false, message: e.message };
        }
    }
    
    /**
     * 检查代码安全性
     */
    async checkSafety(code) {
        try {
            const response = await fetch('/ai/api/code/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });
            return await response.json();
        } catch (e) {
            return { success: false, is_safe: false, message: e.message };
        }
    }
    
    /**
     * 渲染HTML预览
     */
    renderHTML(html, container) {
        if (!container) return;
        
        // 创建沙箱iframe
        const iframe = document.createElement('iframe');
        iframe.style.cssText = 'width:100%;height:400px;border:1px solid var(--border-color);border-radius:8px;background:white;';
        iframe.sandbox = 'allow-scripts allow-same-origin';
        
        container.innerHTML = '';
        container.appendChild(iframe);
        
        // 写入HTML内容
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.open();
        doc.write(html);
        doc.close();
        
        // 自动调整高度
        setTimeout(() => {
            try {
                const height = doc.body.scrollHeight + 20;
                iframe.style.height = Math.min(Math.max(height, 100), 600) + 'px';
            } catch (e) {}
        }, 100);
        
        return iframe;
    }
    
    /**
     * 创建代码运行器UI
     */
    createRunnerUI(container, options = {}) {
        const { language = 'python', code = '', showInstall = true } = options;
        
        const wrapper = document.createElement('div');
        wrapper.className = 'code-runner-wrapper';
        wrapper.innerHTML = `
            <div class="code-runner-header">
                <div class="code-runner-tabs">
                    <button class="runner-tab active" data-lang="python">🐍 Python</button>
                    <button class="runner-tab" data-lang="html">🌐 HTML</button>
                </div>
                <div class="code-runner-actions">
                    ${showInstall ? '<button class="btn btn-sm btn-ghost" id="install-pkg-btn">📦 安装库</button>' : ''}
                    <button class="btn btn-sm btn-primary" id="run-code-btn">▶️ 运行</button>
                </div>
            </div>
            <div class="code-runner-editor">
                <textarea class="code-input" placeholder="在此输入代码...">${this.escapeHtml(code)}</textarea>
            </div>
            <div class="code-runner-output">
                <div class="output-header">
                    <span>📤 输出</span>
                    <button class="btn btn-xs btn-ghost" id="clear-output-btn">清空</button>
                </div>
                <div class="output-content"></div>
            </div>
        `;
        
        container.appendChild(wrapper);
        
        // 绑定事件
        this.bindRunnerEvents(wrapper);
        
        return wrapper;
    }
    
    bindRunnerEvents(wrapper) {
        const tabs = wrapper.querySelectorAll('.runner-tab');
        const codeInput = wrapper.querySelector('.code-input');
        const runBtn = wrapper.querySelector('#run-code-btn');
        const installBtn = wrapper.querySelector('#install-pkg-btn');
        const clearBtn = wrapper.querySelector('#clear-output-btn');
        const outputContent = wrapper.querySelector('.output-content');
        
        let currentLang = 'python';
        
        // 切换语言
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentLang = tab.dataset.lang;
                
                codeInput.placeholder = currentLang === 'python' 
                    ? '在此输入Python代码...' 
                    : '在此输入HTML代码...';
                
                runBtn.textContent = currentLang === 'python' ? '▶️ 运行' : '👁️ 预览';
            });
        });
        
        // 运行代码
        runBtn.addEventListener('click', async () => {
            const code = codeInput.value.trim();
            if (!code) {
                this.showOutput(outputContent, '请输入代码', 'warning');
                return;
            }
            
            if (currentLang === 'python') {
                runBtn.disabled = true;
                runBtn.textContent = '⏳ 运行中...';
                
                const result = await this.runPython(code);
                
                runBtn.disabled = false;
                runBtn.textContent = '▶️ 运行';
                
                if (result.success) {
                    let output = result.output || '(无输出)';
                    if (result.images && result.images.length > 0) {
                        output += '\n\n[图片输出]';
                    }
                    this.showOutput(outputContent, output, 'success', result.images);
                } else {
                    this.showOutput(outputContent, result.error || '运行失败', 'error');
                }
            } else {
                // HTML预览
                this.showOutput(outputContent, '', 'html');
                this.renderHTML(code, outputContent);
            }
        });
        
        // 安装包
        if (installBtn) {
            installBtn.addEventListener('click', () => {
                this.showInstallDialog(outputContent);
            });
        }
        
        // 清空输出
        clearBtn.addEventListener('click', () => {
            outputContent.innerHTML = '<span class="text-muted">输出将显示在这里...</span>';
        });
        
        // 快捷键
        codeInput.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + Enter 运行
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                runBtn.click();
            }
            // Tab 缩进
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = codeInput.selectionStart;
                const end = codeInput.selectionEnd;
                codeInput.value = codeInput.value.substring(0, start) + '    ' + codeInput.value.substring(end);
                codeInput.selectionStart = codeInput.selectionEnd = start + 4;
            }
        });
    }
    
    showOutput(container, content, type = 'info', images = []) {
        if (type === 'html') {
            container.innerHTML = '';
            return;
        }
        
        const colorMap = {
            success: 'var(--success-color, #4CAF50)',
            error: 'var(--danger-color, #F44336)',
            warning: 'var(--warning-color, #FF9800)',
            info: 'var(--text-primary)'
        };
        
        let html = `<pre style="color:${colorMap[type]};margin:0;white-space:pre-wrap;word-break:break-all;">${this.escapeHtml(content)}</pre>`;
        
        // 添加图片
        if (images && images.length > 0) {
            html += '<div class="output-images" style="margin-top:12px;display:flex;flex-wrap:wrap;gap:8px;">';
            images.forEach(img => {
                html += `<img src="${img}" style="max-width:300px;max-height:300px;border-radius:8px;cursor:pointer;" onclick="window.open('${img}')">`;
            });
            html += '</div>';
        }
        
        container.innerHTML = html;
    }
    
    showInstallDialog(outputContainer) {
        const dialog = document.createElement('div');
        dialog.className = 'install-dialog';
        dialog.innerHTML = `
            <div class="install-dialog-content">
                <h4>📦 安装Python库</h4>
                <p class="text-muted" style="font-size:0.85rem;">仅支持白名单中的库</p>
                <div style="display:flex;gap:8px;margin:12px 0;">
                    <input type="text" class="form-control" id="pkg-name-input" placeholder="输入包名，如 numpy">
                    <button class="btn btn-primary" id="do-install-btn">安装</button>
                </div>
                <div class="allowed-packages" style="max-height:150px;overflow-y:auto;font-size:0.8rem;">
                    <strong>可安装的库：</strong><br>
                    ${this.allowedPackages.slice(0, 20).join(', ')}${this.allowedPackages.length > 20 ? '...' : ''}
                </div>
                <button class="btn btn-ghost btn-sm" style="margin-top:12px;" id="close-install-btn">关闭</button>
            </div>
        `;
        
        outputContainer.innerHTML = '';
        outputContainer.appendChild(dialog);
        
        const input = dialog.querySelector('#pkg-name-input');
        const installBtn = dialog.querySelector('#do-install-btn');
        const closeBtn = dialog.querySelector('#close-install-btn');
        
        installBtn.addEventListener('click', async () => {
            const pkg = input.value.trim();
            if (!pkg) return;
            
            installBtn.disabled = true;
            installBtn.textContent = '安装中...';
            
            const result = await this.installPackage(pkg);
            
            installBtn.disabled = false;
            installBtn.textContent = '安装';
            
            if (result.success) {
                this.showOutput(outputContainer, `✅ ${result.message}`, 'success');
            } else {
                this.showOutput(outputContainer, `❌ ${result.message}`, 'error');
            }
        });
        
        closeBtn.addEventListener('click', () => {
            outputContainer.innerHTML = '<span class="text-muted">输出将显示在这里...</span>';
        });
        
        input.focus();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

/**
 * 为代码块添加运行按钮
 */
function addRunButtonsToCodeBlocks() {
    document.querySelectorAll('.code-block-wrapper').forEach(wrapper => {
        // 检查是否已添加运行按钮
        if (wrapper.querySelector('.code-run-btn')) return;
        
        const header = wrapper.querySelector('.code-block-header');
        if (!header) return;
        
        const codeBlock = wrapper.querySelector('pre code');
        if (!codeBlock) return;
        
        // 从多个来源获取语言
        let lang = '';
        
        // 1. 从 code 元素的 class 获取 (language-xxx)
        const langMatch = codeBlock.className.match(/language-(\w+)/);
        if (langMatch) {
            lang = langMatch[1];
        }
        
        // 2. 从 code-lang 标签获取
        if (!lang) {
            const langLabel = header.querySelector('.code-lang');
            if (langLabel) {
                lang = langLabel.textContent.trim().toLowerCase();
            }
        }
        
        // 只为Python和HTML添加运行按钮
        if (!['python', 'py', 'html'].includes(lang.toLowerCase())) return;
        
        const isPython = ['python', 'py'].includes(lang.toLowerCase());
        
        const runBtn = document.createElement('button');
        runBtn.className = 'code-run-btn';
        runBtn.innerHTML = isPython ? '▶️ 运行' : '👁️ 预览';
        runBtn.style.cssText = 'margin-left:8px;padding:4px 10px;font-size:0.75rem;background:var(--primary-color);border:none;border-radius:6px;cursor:pointer;color:white;transition:all 0.2s;';
        
        runBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const code = codeBlock.textContent;
            
            // 创建或获取输出区域
            let outputArea = wrapper.querySelector('.code-output-area');
            if (!outputArea) {
                outputArea = document.createElement('div');
                outputArea.className = 'code-output-area';
                outputArea.style.cssText = 'padding:12px;background:var(--bg-tertiary);border-top:1px solid var(--border-color);max-height:400px;overflow:auto;border-radius:0 0 8px 8px;';
                wrapper.appendChild(outputArea);
            }
            
            if (!isPython) {
                // HTML预览
                const runner = new CodeRunner();
                runner.renderHTML(code, outputArea);
            } else {
                // Python运行
                await runPythonWithInputSupport(code, outputArea, runBtn);
            }
        });
        
        header.appendChild(runBtn);
    });
}

/**
 * 运行Python代码，支持用户输入
 */
async function runPythonWithInputSupport(code, outputArea, runBtn, stdinInput = null) {
    outputArea.innerHTML = '<span style="color:var(--text-muted);">⏳ 运行中...</span>';
    runBtn.disabled = true;
    runBtn.innerHTML = '⏳ 运行中...';
    
    const runner = new CodeRunner();
    const result = await runner.runPython(code, 30, stdinInput);
    
    runBtn.disabled = false;
    runBtn.innerHTML = '▶️ 运行';
    
    // 如果需要用户输入
    if (result.needs_input) {
        showInputPrompt(code, outputArea, runBtn, result);
        return;
    }
    
    if (result.success) {
        let html = `<pre style="margin:0;white-space:pre-wrap;color:var(--success-color, #4CAF50);">${escapeHtmlForOutput(result.output || '(无输出)')}</pre>`;
        if (result.images?.length > 0) {
            html += '<div style="margin-top:8px;">';
            result.images.forEach(img => {
                html += `<img src="${img}" style="max-width:100%;border-radius:8px;margin-top:8px;">`;
            });
            html += '</div>';
        }
        if (result.execution_time) {
            html += `<div style="margin-top:8px;font-size:0.75rem;color:var(--text-muted);">⏱️ 执行时间: ${result.execution_time}s</div>`;
        }
        outputArea.innerHTML = html;
    } else {
        outputArea.innerHTML = `<pre style="margin:0;white-space:pre-wrap;color:var(--danger-color, #F44336);">${escapeHtmlForOutput(result.error || '运行失败')}</pre>`;
    }
}

/**
 * 显示用户输入提示框
 */
function showInputPrompt(code, outputArea, runBtn, result) {
    const prompts = result.input_prompt || ['请输入'];
    const promptText = prompts.join('\n');
    const isInteractive = result.is_interactive || false;
    
    let warningHtml = '';
    if (isInteractive) {
        warningHtml = `
            <div style="margin-bottom:12px;padding:10px;background:rgba(255,152,0,0.1);border-radius:8px;border-left:3px solid var(--warning-color);">
                <strong>⚠️ 交互式程序提示</strong><br>
                <span style="font-size:0.85rem;">这是一个交互式程序（如游戏），包含循环中的多次输入。<br>
                由于无法实时交互，请尝试一次性提供所有输入值，但复杂的交互逻辑可能无法正常运行。<br>
                建议：将此类程序下载到本地运行以获得完整体验。</span>
            </div>
        `;
    }
    
    outputArea.innerHTML = `
        <div class="code-input-prompt" style="padding:8px 0;">
            ${warningHtml}
            <div style="margin-bottom:8px;color:var(--warning-color, #FF9800);">
                ${isInteractive ? '' : '⚠️'} ${result.message || '程序需要用户输入'}
            </div>
            <div style="margin-bottom:8px;font-size:0.85rem;color:var(--text-muted);">
                输入提示: ${escapeHtmlForOutput(promptText)}
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <textarea class="stdin-input" placeholder="输入内容（多行输入用换行分隔）${isInteractive ? '\n例如猜数游戏：每行输入一个猜测的数字' : ''}" 
                    style="flex:1;min-width:200px;padding:8px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-secondary);color:var(--text-primary);font-family:monospace;resize:vertical;min-height:${isInteractive ? '100' : '60'}px;"></textarea>
            </div>
            <div style="margin-top:8px;display:flex;gap:8px;">
                <button class="submit-input-btn" style="padding:6px 16px;background:var(--primary-color);color:white;border:none;border-radius:6px;cursor:pointer;">
                    ▶️ 提交输入并运行
                </button>
                <button class="cancel-input-btn" style="padding:6px 16px;background:var(--bg-tertiary);color:var(--text-primary);border:1px solid var(--border-color);border-radius:6px;cursor:pointer;">
                    取消
                </button>
            </div>
            <div style="margin-top:8px;font-size:0.75rem;color:var(--text-muted);">
                💡 提示：如果程序有多个input()，请按顺序输入，每行一个值
            </div>
        </div>
    `;
    
    const stdinTextarea = outputArea.querySelector('.stdin-input');
    const submitBtn = outputArea.querySelector('.submit-input-btn');
    const cancelBtn = outputArea.querySelector('.cancel-input-btn');
    
    // 提交输入
    submitBtn.addEventListener('click', async () => {
        const userInput = stdinTextarea.value;
        if (!userInput.trim()) {
            stdinTextarea.style.borderColor = 'var(--danger-color)';
            stdinTextarea.placeholder = '请输入内容...';
            return;
        }
        await runPythonWithInputSupport(code, outputArea, runBtn, userInput);
    });
    
    // 取消
    cancelBtn.addEventListener('click', () => {
        outputArea.innerHTML = '<span style="color:var(--text-muted);">已取消运行</span>';
    });
    
    // 快捷键：Ctrl+Enter 提交
    stdinTextarea.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            submitBtn.click();
        }
    });
    
    stdinTextarea.focus();
}

// HTML转义辅助函数
function escapeHtmlForOutput(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 导出
window.CodeRunner = CodeRunner;
window.addRunButtonsToCodeBlocks = addRunButtonsToCodeBlocks;

// 页面加载后自动添加运行按钮
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(addRunButtonsToCodeBlocks, 500);
});
