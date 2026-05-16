/**
 * PostEditor - 帖子编辑器共享模块
 * 提供Markdown工具栏、预览、图片上传等功能
 */
class PostEditor {
    constructor(options = {}) {
        this.editorId = options.editorId || 'content-editor';
        this.previewId = options.previewId || 'content-preview';
        this.containerSelector = options.containerSelector || '.md-editor-container';
        this.imageInputId = options.imageInputId || 'image-input';
        this.imagePreviewId = options.imagePreviewId || 'image-preview';
        this.maxImages = options.maxImages || 9;
        this.mode = options.mode || 'create'; // 'create' or 'edit'

        this.editor = null;
        this.preview = null;
        this.container = null;
        this.selectedImages = [];

        this.init();
    }

    init() {
        this.editor = document.getElementById(this.editorId);
        this.preview = document.getElementById(this.previewId);
        this.container = document.querySelector(this.containerSelector);

        if (!this.editor) return;

        this.bindKeyboardShortcuts();
        this.initImageUpload();
        this.initAIPolish();
    }

    // ==================== Markdown 插入 ====================

    mdInsert(type) {
        const start = this.editor.selectionStart;
        const end = this.editor.selectionEnd;
        const selectedText = this.editor.value.substring(start, end);
        let before = '', after = '', placeholder = '';

        switch (type) {
            case 'bold':
                before = '**'; after = '**'; placeholder = '粗体文字'; break;
            case 'italic':
                before = '*'; after = '*'; placeholder = '斜体文字'; break;
            case 'strikethrough':
                before = '~~'; after = '~~'; placeholder = '删除的文字'; break;
            case 'h2':
                before = '\n## '; after = '\n'; placeholder = '标题'; break;
            case 'h3':
                before = '\n### '; after = '\n'; placeholder = '子标题'; break;
            case 'quote':
                before = '\n> '; after = '\n'; placeholder = '引用内容'; break;
            case 'code':
                before = '`'; after = '`'; placeholder = '代码'; break;
            case 'codeblock':
                before = '\n```\n'; after = '\n```\n'; placeholder = '代码块'; break;
            case 'ul':
                before = '\n- '; after = '\n'; placeholder = '列表项'; break;
            case 'ol':
                before = '\n1. '; after = '\n'; placeholder = '列表项'; break;
            case 'task':
                before = '\n- [ ] '; after = '\n'; placeholder = '待办事项'; break;
            case 'link':
                before = '['; after = '](url)'; placeholder = '链接文字'; break;
            case 'image':
                before = '!['; after = '](图片URL)'; placeholder = '图片描述'; break;
            case 'hr':
                before = '\n\n---\n\n'; after = ''; placeholder = ''; break;
        }

        const insertText = selectedText || placeholder;
        const newText = before + insertText + after;

        this.editor.focus();
        document.execCommand('insertText', false, newText);

        if (!selectedText && placeholder) {
            this.editor.setSelectionRange(start + before.length, start + before.length + placeholder.length);
        }
    }

    // ==================== 预览 ====================

    togglePreview() {
        if (!this.container || !this.preview) return;
        this.container.classList.toggle('preview-mode');
        if (this.container.classList.contains('preview-mode')) {
            this.preview.innerHTML = this.parseMarkdown(this.editor.value);
        }
    }

    parseMarkdown(text) {
        if (!text) return '<p class="text-muted">预览区域（内容为空）</p>';

        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/~~(.+?)~~/g, '<del>$1</del>')
            .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
            .replace(/^---$/gm, '<hr>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
            .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">')
            .replace(/^- \[x\] (.+)$/gm, '<div>☑ $1</div>')
            .replace(/^- \[ \] (.+)$/gm, '<div>☐ $1</div>')
            .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        return '<p>' + html + '</p>';
    }

    // ==================== 快捷键 ====================

    bindKeyboardShortcuts() {
        this.editor.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key.toLowerCase()) {
                    case 'b': e.preventDefault(); this.mdInsert('bold'); break;
                    case 'i': e.preventDefault(); this.mdInsert('italic'); break;
                    case 'k': e.preventDefault(); this.mdInsert('link'); break;
                }
            }
            if (e.key === 'Tab') {
                e.preventDefault();
                document.execCommand('insertText', false, '    ');
            }
        });
    }

    // ==================== 图片上传 ====================

    initImageUpload() {
        const imageInput = document.getElementById(this.imageInputId);
        if (!imageInput) return;

        imageInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            const existingCount = this.mode === 'edit'
                ? document.querySelectorAll('#existing-images .image-preview-item').length
                : 0;

            if (existingCount + this.selectedImages.length + files.length > this.maxImages) {
                if (typeof Utils !== 'undefined') Utils.showToast(`最多只能上传${this.maxImages}张图片`, 'warning');
                return;
            }

            files.forEach(file => {
                if (file.type.startsWith('image/')) {
                    this.selectedImages.push(file);
                }
            });

            this.renderImagePreviews();
            this.updateImageInput();
        });
    }

    renderImagePreviews() {
        const container = document.getElementById(this.imagePreviewId);
        if (!container) return;

        container.innerHTML = '';
        this.selectedImages.forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const div = document.createElement('div');
                div.className = 'image-preview-item';
                div.dataset.index = index;
                div.innerHTML = `
                    <img src="${e.target.result}" alt="预览">
                    <button type="button" class="remove-btn" onclick="postEditor.removeImage(${index})">&times;</button>
                `;
                container.appendChild(div);
            };
            reader.readAsDataURL(file);
        });
    }

    removeImage(index) {
        this.selectedImages.splice(index, 1);
        this.renderImagePreviews();
        this.updateImageInput();
    }

    updateImageInput() {
        const imageInput = document.getElementById(this.imageInputId);
        if (!imageInput) return;
        const dt = new DataTransfer();
        this.selectedImages.forEach(file => dt.items.add(file));
        imageInput.files = dt.files;
    }

    // ==================== AI 润色 ====================

    initAIPolish() {
        const toolbar = document.querySelector(this.containerSelector + ' .md-toolbar');
        if (!toolbar) return;

        // 创建AI润色按钮和下拉菜单
        const divider = document.createElement('div');
        divider.className = 'md-toolbar-divider';
        toolbar.appendChild(divider);

        const wrapper = document.createElement('div');
        wrapper.style.position = 'relative';
        wrapper.style.display = 'inline-block';

        wrapper.innerHTML = `
            <button type="button" class="md-toolbar-btn ai-polish-btn" title="AI润色">
                <span>✨</span><span>AI</span>
            </button>
            <div class="ai-polish-dropdown" style="display:none;position:absolute;top:100%;left:0;z-index:100;min-width:130px;background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:var(--radius-sm);box-shadow:0 4px 12px rgba(0,0,0,0.15);margin-top:4px;">
                <div class="ai-polish-option" data-action="polish" style="padding:8px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px;">✨ 润色</div>
                <div class="ai-polish-option" data-action="expand" style="padding:8px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px;">📝 扩写</div>
                <div class="ai-polish-option" data-action="condense" style="padding:8px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px;">✂️ 缩写</div>
                <div class="ai-polish-option" data-action="restyle" style="padding:8px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px;">🎨 换风格</div>
                <div class="ai-polish-option" data-action="correct" style="padding:8px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px;">🔍 纠错</div>
            </div>
        `;

        toolbar.appendChild(wrapper);

        const btn = wrapper.querySelector('.ai-polish-btn');
        const dropdown = wrapper.querySelector('.ai-polish-dropdown');

        // 切换下拉菜单
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        });

        // 选项点击
        dropdown.querySelectorAll('.ai-polish-option').forEach(opt => {
            opt.addEventListener('click', () => {
                dropdown.style.display = 'none';
                this.doAIPolish(opt.dataset.action);
            });
        });

        // 悬停样式
        dropdown.querySelectorAll('.ai-polish-option').forEach(opt => {
            opt.addEventListener('mouseenter', () => {
                opt.style.background = 'var(--primary-light)';
                opt.style.color = 'var(--primary-color)';
            });
            opt.addEventListener('mouseleave', () => {
                opt.style.background = '';
                opt.style.color = '';
            });
        });

        // 点击外部关闭
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) dropdown.style.display = 'none';
        });
    }

    async doAIPolish(action) {
        const start = this.editor.selectionStart;
        const end = this.editor.selectionEnd;
        let text = this.editor.value.substring(start, end);
        const isSelection = text.length > 0;
        if (!text) text = this.editor.value;

        if (!text.trim()) {
            if (typeof Utils !== 'undefined') Utils.showToast('请先输入内容', 'warning');
            return;
        }

        const actionNames = {polish:'润色', expand:'扩写', condense:'缩写', restyle:'换风格', correct:'纠错'};
        if (typeof Utils !== 'undefined') Utils.showToast(`正在AI${actionNames[action]}...`, 'info');

        try {
            const response = await fetch('/ai/api/polish', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({content: text, action: action})
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let result = '';

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6).replace(/\\n/g, '\n');
                        if (data === '[DONE]') break;
                        if (!data.startsWith('错误')) result += data;
                    }
                }
            }

            if (result) {
                if (confirm(`AI${actionNames[action]}完成，是否替换原文？`)) {
                    if (isSelection) {
                        this.editor.focus();
                        this.editor.setSelectionRange(start, end);
                        document.execCommand('insertText', false, result);
                    } else {
                        this.editor.value = result;
                    }
                }
            } else {
                if (typeof Utils !== 'undefined') Utils.showToast('AI润色未返回结果', 'warning');
            }
        } catch (e) {
            if (typeof Utils !== 'undefined') Utils.showToast('AI润色失败: ' + e.message, 'danger');
        }
    }
}

// 全局实例（供onclick调用）
let postEditor;
