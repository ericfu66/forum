/**
 * 帖子编辑器
 * 简单的Markdown编辑器
 */

class PostEditor {
    constructor(options = {}) {
        this.textarea = document.querySelector(options.textarea || '#post-content');
        this.preview = document.querySelector(options.preview || '#post-preview');
        this.toolbar = document.querySelector(options.toolbar || '#editor-toolbar');

        if (this.textarea) {
            this.init();
        }
    }

    init() {
        // 创建工具栏
        this.createToolbar();

        // 监听输入变化
        this.textarea.addEventListener('input', () => {
            this.updatePreview();
        });

        // 初始化预览
        this.updatePreview();
    }

    createToolbar() {
        if (!this.toolbar) return;

        const buttons = [
            { name: 'bold', icon: 'B', title: '粗体', action: () => this.insert('**', '**') },
            { name: 'italic', icon: 'I', title: '斜体', action: () => this.insert('*', '*') },
            { name: 'code', icon: '</>', title: '代码', action: () => this.insert('`', '`') },
            { name: 'link', icon: '🔗', title: '链接', action: () => this.insert('[', '](url)') },
            { name: 'quote', icon: '❝', title: '引用', action: () => this.insert('> ', '') },
            { name: 'list', icon: '☰', title: '列表', action: () => this.insert('- ', '') },
            { name: 'h1', icon: 'H1', title: '一级标题', action: () => this.insert('# ', '') },
            { name: 'h2', icon: 'H2', title: '二级标题', action: () => this.insert('## ', '') },
        ];

        buttons.forEach(btn => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-ghost btn-sm';
            button.textContent = btn.icon;
            button.title = btn.title;
            button.addEventListener('click', (e) => {
                e.preventDefault();
                btn.action();
            });
            this.toolbar.appendChild(button);
        });
    }

    insert(before, after = '') {
        const start = this.textarea.selectionStart;
        const end = this.textarea.selectionEnd;
        const text = this.textarea.value;
        const selected = text.substring(start, end);

        this.textarea.value = text.substring(0, start) + before + selected + after + text.substring(end);
        this.textarea.focus();
        this.textarea.setSelectionRange(start + before.length, start + before.length + selected.length);
        this.updatePreview();
    }

    updatePreview() {
        if (!this.preview) return;

        const content = this.textarea.value;
        this.preview.innerHTML = this.parseMarkdown(content);
    }

    parseMarkdown(text) {
        return Utils.escapeHtml(text)
            // 标题
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // 粗体
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // 斜体
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // 代码
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // 链接
            .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
            // 引用
            .replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>')
            // 列表
            .replace(/^- (.*$)/gm, '<li>$1</li>')
            // 换行
            .replace(/\n/g, '<br>');
    }
}
