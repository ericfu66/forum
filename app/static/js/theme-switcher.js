/**
 * 主题切换器
 * 支持浅色/深色/纸质主题切换
 */

class ThemeSwitcher {
    constructor() {
        this.themes = ['light', 'dark', 'paper'];
        this.themeIcons = {
            'light': '🌙',
            'dark': '📜',
            'paper': '☀️'
        };
        this.themeNames = {
            'light': '浅色模式',
            'dark': '深色模式',
            'paper': '纸质主题'
        };
        this.currentTheme = localStorage.getItem('theme') || 'light';
        this.toggleBtn = document.getElementById('theme-toggle');
        this.init();
    }

    init() {
        // 应用保存的主题
        this.applyTheme(this.currentTheme);

        // 绑定切换按钮
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', () => this.toggle());
            this.updateButton();
        }
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        this.currentTheme = theme;
        this.updateButton();

        // 同步到服务器
        this.syncToServer(theme);
    }

    toggle() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        const newTheme = this.themes[nextIndex];
        this.applyTheme(newTheme);

        // 添加切换动画
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
        setTimeout(() => {
            document.body.style.transition = '';
        }, 300);

        // 显示提示
        if (window.Utils && Utils.showToast) {
            Utils.showToast(`已切换到${this.themeNames[newTheme]}`, 'info');
        }
    }

    updateButton() {
        if (!this.toggleBtn) return;
        // 显示下一个主题的图标
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextTheme = this.themes[(currentIndex + 1) % this.themes.length];
        this.toggleBtn.textContent = this.themeIcons[this.currentTheme];
        this.toggleBtn.title = `切换到${this.themeNames[nextTheme]}`;
    }

    async syncToServer(theme) {
        try {
            await fetch('/api/user/preferences', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme })
            });
        } catch (e) {
            // 静默失败
        }
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    window.themeSwitcher = new ThemeSwitcher();
});
