/**
 * AI聊天功能 - 重构版
 * 支持流式响应、对话管理、数学公式、代码高亮
 */

class AIChat {
    constructor(options = {}) {
        this.dialogId = options.dialogId || null;
        this.messagesContainer = options.messagesContainer || '#chat-messages';
        this.inputElement = options.inputElement || '#chat-input';
        this.sendButton = options.sendButton || '#send-btn';
        this.messages = [];
        this.isGenerating = false;
        this.options = options;
        this.currentAssistant = 'general';
        this.currentAssistantData = null;
        this.messageIdCounter = 0;
        this.useSearch = false;  // 联网搜索开关

        this.init();
    }

    init() {
        const sendBtn = document.querySelector(this.sendButton);
        const input = document.querySelector(this.inputElement);

        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }

        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            // 自动调整高度
            input.addEventListener('input', () => {
                input.style.height = 'auto';
                input.style.height = Math.min(input.scrollHeight, 150) + 'px';
            });
        }

        if (this.dialogId) {
            this.loadDialog();
        }
    }

    generateMessageId() {
        return 'msg-' + Date.now() + '-' + (++this.messageIdCounter);
    }

    async loadDialog(dialogId = null) {
        if (dialogId) {
            this.dialogId = dialogId;
            document.querySelectorAll('.dialog-item').forEach(el => el.classList.remove('active'));
            const item = document.querySelector('[data-dialog-id="' + dialogId + '"]');
            if (item) item.classList.add('active');
        }

        const welcome = document.getElementById('welcome-screen');
        if (welcome) welcome.style.display = 'none';

        try {
            const response = await Utils.get('/ai/api/dialogs/' + this.dialogId);
            if (response.success) {
                const dialog = response.dialog;
                this.messages = (dialog.messages || []).map((msg, idx) => ({
                    messageId: this.generateMessageId(),
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.timestamp || new Date().toISOString()
                }));
                this.renderAllMessages();
            }
        } catch (e) {
            console.error('Failed to load dialog:', e);
        }
    }

    async sendMessage() {
        if (this.isGenerating) return;

        const input = document.querySelector(this.inputElement);
        const content = input.value.trim();
        const images = (typeof uploadedImages !== 'undefined') ? [...uploadedImages] : [];

        if (!content && images.length === 0) return;

        input.value = '';
        input.style.height = 'auto';

        if (typeof uploadedImages !== 'undefined') {
            uploadedImages.length = 0;
            if (typeof renderUploadPreview === 'function') {
                renderUploadPreview();
            }
        }

        // 隐藏欢迎界面
        const welcome = document.getElementById('welcome-screen');
        if (welcome) welcome.style.display = 'none';

        // 添加用户消息
        const userMsgId = this.generateMessageId();
        const displayContent = images.length > 0 ? '[📷 ' + images.length + '张图片]\n' + content : content;
        this.addMessage(userMsgId, 'user', displayContent, images);

        // 添加AI消息占位符
        const aiMsgId = this.generateMessageId();
        this.addMessage(aiMsgId, 'assistant', '');
        this.showTypingIndicator(aiMsgId);

        this.isGenerating = true;
        this.setSendButtonState(false);

        try {
            await this.streamResponse(content, aiMsgId, images);
        } catch (e) {
            this.updateMessageContent(aiMsgId, '抱歉，AI回复出现问题：' + e.message);
            console.error('Chat error:', e);
        } finally {
            this.hideTypingIndicator(aiMsgId);
            this.isGenerating = false;
            this.setSendButtonState(true);
        }
    }

    async streamResponse(userMessage, aiMessageId, images = []) {
        if (!this.dialogId) {
            const response = await Utils.post('/ai/api/dialogs', { title: '新对话' });
            if (response.success) {
                this.dialogId = response.dialog.id;
                this.addDialogToList(response.dialog);
            }
        }

        let systemPrompt = '';
        let useKnowledge = true;
        let assistantId = null;

        if (this.options.assistants && this.currentAssistant) {
            const assistant = this.options.assistants[this.currentAssistant];
            if (assistant) {
                systemPrompt = assistant.prompt || '';
                useKnowledge = assistant.useKnowledge !== false;
                assistantId = assistant.customId || null;
            }
        }

        const requestBody = {
            message: userMessage,
            system_prompt: systemPrompt,
            use_knowledge: useKnowledge,
            use_search: this.useSearch  // 添加搜索开关
        };

        if (images && images.length > 0) {
            requestBody.images = images;
        }
        if (assistantId) {
            requestBody.assistant_id = assistantId;
        }

        const response = await fetch('/ai/api/dialogs/' + this.dialogId + '/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || '请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let aiContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    if (data === '[DONE]') break;

                    const decodedData = data.replace(/\\n/g, '\n');
                    aiContent += decodedData;
                    this.updateMessageContent(aiMessageId, aiContent);
                    this.scrollToBottom();
                }
            }
        }

        // 更新本地消息
        const msg = this.messages.find(m => m.messageId === aiMessageId);
        if (msg) msg.content = aiContent;

        this.updateDialogTitle(userMessage);
    }

    addMessage(messageId, role, content, images = []) {
        const message = {
            messageId: messageId,
            role: role,
            content: content,
            images: images,
            timestamp: new Date().toISOString()
        };
        this.messages.push(message);
        this.renderMessage(message);
        this.scrollToBottom();
    }

    renderMessage(message) {
        const container = document.querySelector(this.messagesContainer);
        if (!container) return;

        const isAI = message.role === 'assistant';
        const messageEl = document.createElement('div');
        messageEl.className = 'chat-message ' + (isAI ? 'ai-message' : 'user-message');
        messageEl.setAttribute('data-message-id', message.messageId);

        let imagesHtml = '';
        if (message.images && message.images.length > 0) {
            imagesHtml = '<div class="message-images">' +
                message.images.map(img => '<img src="' + img + '" alt="图片" class="message-image" onclick="window.open(\'' + img + '\', \'_blank\')">').join('') +
                '</div>';
        }

        const avatarIcon = isAI ? '🤖' : '👤';
        const formattedContent = this.formatContent(message.content);

        // AI消息添加重新生成按钮
        let actionsHtml = '';
        if (isAI && message.content) {
            actionsHtml = '<div class="message-actions">' +
                '<button class="message-action-btn regenerate-btn" onclick="chat.regenerateMessage(\'' + message.messageId + '\')" title="重新生成">' +
                    '🔄 重新生成' +
                '</button>' +
            '</div>';
        }

        messageEl.innerHTML = 
            '<div class="message-avatar">' + avatarIcon + '</div>' +
            '<div class="message-bubble glass-bubble">' +
                imagesHtml +
                '<div class="message-content">' + formattedContent + '</div>' +
                '<div class="message-footer">' +
                    '<div class="message-time">' + this.formatTime(message.timestamp) + '</div>' +
                    actionsHtml +
                '</div>' +
            '</div>';

        container.appendChild(messageEl);
        this.renderMath(messageEl);
    }

    renderAllMessages() {
        const container = document.querySelector(this.messagesContainer);
        if (!container) return;
        container.innerHTML = '';
        this.messages.forEach(msg => this.renderMessage(msg));
        this.scrollToBottom();
    }

    updateMessageContent(messageId, content) {
        const msg = this.messages.find(m => m.messageId === messageId);
        if (msg) msg.content = content;

        const messageEl = document.querySelector('[data-message-id="' + messageId + '"]');
        if (messageEl) {
            const contentEl = messageEl.querySelector('.message-content');
            if (contentEl) {
                contentEl.innerHTML = this.formatContent(content);
                this.renderMath(messageEl);
            }
            
            // 确保AI消息有重新生成按钮
            const isAI = messageEl.classList.contains('ai-message');
            if (isAI && content) {
                let footer = messageEl.querySelector('.message-footer');
                if (!footer) {
                    const bubble = messageEl.querySelector('.glass-bubble');
                    if (bubble) {
                        const timeEl = bubble.querySelector('.message-time');
                        const timeHtml = timeEl ? timeEl.outerHTML : '<div class="message-time">' + this.formatTime(msg.timestamp) + '</div>';
                        if (timeEl) timeEl.remove();
                        
                        footer = document.createElement('div');
                        footer.className = 'message-footer';
                        footer.innerHTML = timeHtml +
                            '<div class="message-actions">' +
                                '<button class="message-action-btn regenerate-btn" onclick="chat.regenerateMessage(\'' + messageId + '\')" title="重新生成">' +
                                    '🔄 重新生成' +
                                '</button>' +
                            '</div>';
                        bubble.appendChild(footer);
                    }
                }
            }
        }
    }

    showTypingIndicator(messageId) {
        const messageEl = document.querySelector('[data-message-id="' + messageId + '"]');
        if (messageEl) {
            const contentEl = messageEl.querySelector('.message-content');
            if (contentEl) {
                contentEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
            }
        }
    }

    hideTypingIndicator(messageId) {
        // 内容更新时会自动替换
    }

    formatContent(content) {
        if (!content) return '';
        
        let html = content;
        
        // 保护区域
        const mathBlocks = [];
        const inlineMath = [];
        const codeBlocks = [];
        const inlineCode = [];
        
        // 保护块级数学公式 $$...$$
        html = html.replace(/\$\$([\s\S]*?)\$\$/g, function(match, p1) {
            mathBlocks.push(p1);
            return '%%MATHBLOCK' + (mathBlocks.length - 1) + '%%';
        });
        
        // 保护行内数学公式 $...$
        html = html.replace(/\$([^\$\n]+?)\$/g, function(match, p1) {
            inlineMath.push(p1);
            return '%%INLINEMATH' + (inlineMath.length - 1) + '%%';
        });
        
        // 保护代码块
        html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, function(match, lang, code) {
            codeBlocks.push({ lang: lang || '', code: code.trim() });
            return '%%CODEBLOCK' + (codeBlocks.length - 1) + '%%';
        });
        
        // 保护行内代码
        html = html.replace(/`([^`]+)`/g, function(match, code) {
            inlineCode.push(code);
            return '%%INLINECODE' + (inlineCode.length - 1) + '%%';
        });
        
        // 处理思维链
        var showThinking = localStorage.getItem('show-thinking') === 'true';
        html = html.replace(/<think>([\s\S]*?)<\/think>/g, function(match, thinkContent) {
            var display = showThinking ? 'block' : 'none';
            return '<div class="thinking-block" style="display:' + display + ';">' +
                '<div class="thinking-header" onclick="this.nextElementSibling.classList.toggle(\'collapsed\');">' +
                '<span>💭 思考过程</span></div>' +
                '<div class="thinking-content">' + thinkContent.trim() + '</div></div>';
        });
        
        // HTML转义
        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // 恢复思维链HTML标签
        html = html.replace(/&lt;div class="thinking-block"/g, '<div class="thinking-block"');
        html = html.replace(/&lt;div class="thinking-header"/g, '<div class="thinking-header"');
        html = html.replace(/&lt;div class="thinking-content"&gt;/g, '<div class="thinking-content">');
        html = html.replace(/&lt;\/div&gt;/g, '</div>');
        html = html.replace(/&lt;span&gt;/g, '<span>');
        html = html.replace(/&lt;\/span&gt;/g, '</span>');
        
        // 标题
        html = html.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>');
        html = html.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
        html = html.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
        
        // 粗体和斜体 - 修复跨行问题
        html = html.replace(/\*\*\*([^\*]+)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*([^\*\n]+)\*/g, '<em>$1</em>');
        html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');
        
        // 引用块
        html = html.replace(/^&gt;\s+(.+)$/gm, '<blockquote>$1</blockquote>');
        
        // 分隔线
        html = html.replace(/^---$/gm, '<hr>');
        
        // 列表
        html = html.replace(/^-\s+(.+)$/gm, '<li>$1</li>');
        html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
        
        // 换行
        html = html.replace(/\n/g, '<br>');
        
        // 恢复代码块
        for (var i = 0; i < codeBlocks.length; i++) {
            var block = codeBlocks[i];
            var codeId = 'code-' + Date.now() + '-' + i;
            var langLabel = block.lang ? '<span class="code-lang">' + block.lang + '</span>' : '';
            var escapedCode = block.code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            var codeHtml = '<div class="code-block-wrapper">' +
                '<div class="code-block-header">' + langLabel +
                '<button class="code-copy-btn" onclick="copyCodeBlock(\'' + codeId + '\')">📋 复制</button></div>' +
                '<pre><code id="' + codeId + '">' + escapedCode + '</code></pre></div>';
            html = html.replace('%%CODEBLOCK' + i + '%%', codeHtml);
        }
        
        // 恢复行内代码
        for (var j = 0; j < inlineCode.length; j++) {
            var code = inlineCode[j].replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            html = html.replace('%%INLINECODE' + j + '%%', '<code>' + code + '</code>');
        }
        
        // 恢复数学公式
        for (var k = 0; k < mathBlocks.length; k++) {
            html = html.replace('%%MATHBLOCK' + k + '%%', '<div class="math-block">$$' + mathBlocks[k] + '$$</div>');
        }
        for (var l = 0; l < inlineMath.length; l++) {
            html = html.replace('%%INLINEMATH' + l + '%%', '<span class="math-inline">$' + inlineMath[l] + '$</span>');
        }
        
        return html;
    }

    renderMath(element) {
        if (typeof renderMathInElement === 'function') {
            try {
                renderMathInElement(element, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false}
                    ],
                    throwOnError: false,
                    trust: true
                });
            } catch (e) {
                console.warn('Math rendering failed:', e);
            }
        }
    }

    formatTime(timestamp) {
        if (!timestamp) return '';
        try {
            var date = new Date(timestamp);
            var now = new Date();
            var diff = now - date;
            
            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
            if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
            
            return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        } catch (e) {
            return '';
        }
    }

    scrollToBottom() {
        var container = document.querySelector(this.messagesContainer);
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    setSendButtonState(enabled) {
        var btn = document.querySelector(this.sendButton);
        if (btn) {
            btn.disabled = !enabled;
            btn.innerHTML = enabled ? '发送' : '<div class="loading-spinner loading-spinner-sm"></div>';
        }
    }

    async createNewDialog() {
        var response = await Utils.post('/ai/api/dialogs', { title: '新对话' });
        if (response.success) {
            this.dialogId = response.dialog.id;
            this.messages = [];
            var welcome = document.getElementById('welcome-screen');
            if (welcome) welcome.style.display = 'none';
            this.renderAllMessages();
            this.addDialogToList(response.dialog);
            return true;
        }
        return false;
    }

    addDialogToList(dialog) {
        var dialogList = document.getElementById('dialog-list');
        if (!dialogList) return;

        var emptyHint = dialogList.querySelector('div[style*="text-align: center"]');
        if (emptyHint) emptyHint.remove();

        var dialogItem = document.createElement('div');
        dialogItem.className = 'dialog-item active';
        dialogItem.setAttribute('data-dialog-id', dialog.id);
        
        var self = this;
        dialogItem.onclick = function() { self.loadDialog(dialog.id); };

        dialogItem.innerHTML = 
            '<span class="dialog-item-icon">💬</span>' +
            '<div class="dialog-item-content">' +
                '<div class="dialog-item-title">' + (dialog.title || '新对话') + '</div>' +
                '<div class="dialog-item-time">刚刚</div>' +
            '</div>' +
            '<button class="dialog-item-delete" onclick="event.stopPropagation(); chat.deleteDialog(' + dialog.id + ')">🗑️</button>';

        dialogList.querySelectorAll('.dialog-item').forEach(function(el) { el.classList.remove('active'); });

        var title = dialogList.querySelector('.dialog-section-title');
        if (title) {
            title.after(dialogItem);
        } else {
            dialogList.prepend(dialogItem);
        }
    }

    updateDialogTitle(title) {
        if (!this.dialogId) return;
        var dialogItem = document.querySelector('[data-dialog-id="' + this.dialogId + '"] .dialog-item-title');
        if (dialogItem) {
            dialogItem.textContent = title.substring(0, 30) + (title.length > 30 ? '...' : '');
        }
    }

    async deleteDialog(dialogId) {
        if (!confirm('确定要删除这个对话吗？')) return;

        try {
            var response = await Utils.post('/ai/api/dialogs/' + dialogId + '/delete');
            if (response.success) {
                Utils.showToast('对话已删除', 'success');
                var item = document.querySelector('[data-dialog-id="' + dialogId + '"]');
                if (item) item.remove();
                
                if (this.dialogId === dialogId) {
                    this.dialogId = null;
                    this.messages = [];
                    var container = document.querySelector(this.messagesContainer);
                    if (container) {
                        container.innerHTML = 
                            '<div class="welcome-screen" id="welcome-screen">' +
                                '<div class="welcome-icon">🤖</div>' +
                                '<h2 class="welcome-title">你好！我是 AI 助手</h2>' +
                                '<p class="welcome-desc">选择上方不同的助手角色，开始智能对话</p>' +
                            '</div>';
                    }
                }
            }
        } catch (e) {
            Utils.showToast('删除失败', 'danger');
        }
    }

    switchAssistant(type) {
        var assistant = this.options.assistants ? this.options.assistants[type] : null;
        
        if (!assistant && typeof customAssistants !== 'undefined') {
            var customAssistant = customAssistants.find(function(a) { return a.id == type; });
            if (customAssistant) {
                assistant = {
                    icon: customAssistant.icon,
                    name: customAssistant.name,
                    prompt: customAssistant.system_prompt,
                    useKnowledge: false,
                    isCustom: true,
                    customId: customAssistant.id
                };
            }
        }
        
        if (!assistant) return;

        document.querySelectorAll('.assistant-item').forEach(function(el) { el.classList.remove('active'); });
        var activeEl = document.querySelector('[data-assistant="' + type + '"]');
        if (activeEl) activeEl.classList.add('active');
        
        var iconEl = document.getElementById('current-assistant-icon');
        var nameEl = document.getElementById('current-assistant-name');
        if (iconEl) iconEl.textContent = assistant.icon;
        if (nameEl) nameEl.textContent = assistant.name;

        // 移动端
        var mobileIconEl = document.getElementById('mobile-assistant-icon');
        var mobileNameEl = document.getElementById('mobile-assistant-name');
        if (mobileIconEl) mobileIconEl.textContent = assistant.icon;
        if (mobileNameEl) mobileNameEl.textContent = assistant.name;

        this.currentAssistant = type;
        this.currentAssistantData = assistant;
        localStorage.setItem('ai-assistant', type);
    }

    sendSuggestion(text) {
        var input = document.getElementById('chat-input');
        if (input) {
            input.value = text;
            this.sendMessage();
        }
    }

    toggleSearch(enabled) {
        this.useSearch = enabled;
        var searchToggle = document.getElementById('search-toggle');
        if (searchToggle) {
            searchToggle.classList.toggle('active', enabled);
        }
        var searchIcon = document.getElementById('search-icon');
        if (searchIcon) {
            searchIcon.textContent = enabled ? '🌐' : '🔍';
        }
        localStorage.setItem('ai-use-search', enabled ? 'true' : 'false');
    }

    initSearchToggle() {
        var saved = localStorage.getItem('ai-use-search');
        if (saved === 'true') {
            this.toggleSearch(true);
        }
    }

    async regenerateMessage(aiMessageId) {
        if (this.isGenerating) {
            Utils.showToast('正在生成中，请稍候', 'warning');
            return;
        }

        // 找到要重新生成的AI消息
        const aiMsgIndex = this.messages.findIndex(m => m.messageId === aiMessageId);
        if (aiMsgIndex === -1) {
            Utils.showToast('消息不存在', 'danger');
            return;
        }

        // 找到对应的用户消息（AI消息前面的那条）
        let userMsgIndex = -1;
        for (let i = aiMsgIndex - 1; i >= 0; i--) {
            if (this.messages[i].role === 'user') {
                userMsgIndex = i;
                break;
            }
        }

        if (userMsgIndex === -1) {
            Utils.showToast('找不到对应的用户消息', 'danger');
            return;
        }

        const userMessage = this.messages[userMsgIndex];
        // 提取原始用户消息内容（去掉图片标记）
        let userContent = userMessage.content;
        const imgMatch = userContent.match(/^\[📷 \d+张图片\]\n/);
        if (imgMatch) {
            userContent = userContent.substring(imgMatch[0].length);
        }

        // 显示加载状态
        this.showTypingIndicator(aiMessageId);
        this.isGenerating = true;
        this.setSendButtonState(false);

        // 禁用重新生成按钮
        const regenBtn = document.querySelector('[data-message-id="' + aiMessageId + '"] .regenerate-btn');
        if (regenBtn) {
            regenBtn.disabled = true;
            regenBtn.innerHTML = '⏳ 生成中...';
        }

        try {
            // 调用重新生成API
            await this.streamRegenerateResponse(userContent, aiMessageId, userMessage.images || []);
            Utils.showToast('重新生成完成', 'success');
        } catch (e) {
            this.updateMessageContent(aiMessageId, '重新生成失败：' + e.message);
            Utils.showToast('重新生成失败', 'danger');
            console.error('Regenerate error:', e);
        } finally {
            this.hideTypingIndicator(aiMessageId);
            this.isGenerating = false;
            this.setSendButtonState(true);

            // 恢复重新生成按钮
            if (regenBtn) {
                regenBtn.disabled = false;
                regenBtn.innerHTML = '🔄 重新生成';
            }
        }
    }

    async streamRegenerateResponse(userMessage, aiMessageId, images = []) {
        let systemPrompt = '';
        let useKnowledge = true;
        let assistantId = null;

        if (this.options.assistants && this.currentAssistant) {
            const assistant = this.options.assistants[this.currentAssistant];
            if (assistant) {
                systemPrompt = assistant.prompt || '';
                useKnowledge = assistant.useKnowledge !== false;
                assistantId = assistant.customId || null;
            }
        }

        const requestBody = {
            message: userMessage,
            system_prompt: systemPrompt,
            use_knowledge: useKnowledge,
            use_search: this.useSearch,
            regenerate: true  // 标记为重新生成
        };

        if (images && images.length > 0) {
            requestBody.images = images;
        }
        if (assistantId) {
            requestBody.assistant_id = assistantId;
        }

        const response = await fetch('/ai/api/dialogs/' + this.dialogId + '/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || '请求失败');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let aiContent = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.substring(6);
                    if (data === '[DONE]') break;

                    const decodedData = data.replace(/\\n/g, '\n');
                    aiContent += decodedData;
                    this.updateMessageContent(aiMessageId, aiContent);
                    this.scrollToBottom();
                }
            }
        }

        // 更新本地消息
        const msg = this.messages.find(m => m.messageId === aiMessageId);
        if (msg) msg.content = aiContent;
    }
}

// 全局复制代码函数
function copyCodeBlock(codeId) {
    var codeEl = document.getElementById(codeId);
    if (!codeEl) return;
    
    var code = codeEl.textContent;
    navigator.clipboard.writeText(code).then(function() {
        Utils.showToast('代码已复制', 'success');
    }).catch(function() {
        var textarea = document.createElement('textarea');
        textarea.value = code;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        Utils.showToast('代码已复制', 'success');
    });
}
