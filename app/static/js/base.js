/**
 * 基础JavaScript - AI Forum
 * 通用工具函数和初始化
 */

// 工具函数
const Utils = {
    // 格式化时间
    formatTime(date) {
        if (!date) return '';
        const d = new Date(date);
        const now = new Date();
        const diff = now - d;

        // 小于1分钟
        if (diff < 60000) {
            return '刚刚';
        }
        // 小于1小时
        if (diff < 3600000) {
            return `${Math.floor(diff / 60000)}分钟前`;
        }
        // 小于24小时
        if (diff < 86400000) {
            return `${Math.floor(diff / 3600000)}小时前`;
        }
        // 小于30天
        if (diff < 2592000000) {
            return `${Math.floor(diff / 86400000)}天前`;
        }
        // 格式化日期
        return d.toLocaleDateString('zh-CN');
    },

    // 转义HTML
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // 显示Toast消息
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast alert alert-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 250px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    // 确认对话框
    confirm(message) {
        return window.confirm(message);
    },

    // GET请求
    async get(url) {
        const response = await fetch(url);
        return await response.json();
    },

    // POST请求
    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return await response.json();
    },

    // 表单POST请求
    async postForm(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        return await response.json();
    },

    // 显示加载中
    showLoading(element) {
        if (typeof element === 'string') {
            element = document.querySelector(element);
        }
        if (element) {
            element.innerHTML = '<div class="loading-spinner"></div>';
        }
    },

    // 隐藏加载中
    hideLoading(element, content) {
        if (typeof element === 'string') {
            element = document.querySelector(element);
        }
        if (element && content) {
            element.innerHTML = content;
        }
    }
};

// 移动菜单功能
const MobileMenu = {
    menuBtn: null,
    menu: null,
    overlay: null,
    isOpen: false,

    init() {
        this.menuBtn = document.getElementById('mobile-menu-btn');
        this.menu = document.getElementById('mobile-menu');
        this.overlay = document.getElementById('mobile-menu-overlay');

        if (!this.menuBtn || !this.menu) return;

        // 点击菜单按钮
        this.menuBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.toggle();
        });

        // 点击遮罩关闭菜单
        if (this.overlay) {
            this.overlay.addEventListener('click', () => {
                this.close();
            });
        }

        // 点击菜单项后关闭菜单
        const menuItems = this.menu.querySelectorAll('.mobile-menu-item');
        menuItems.forEach(item => {
            item.addEventListener('click', () => {
                // 如果是链接，等待一小段时间让用户看到反馈
                const href = item.getAttribute('href');
                if (href && href !== '#') {
                    setTimeout(() => this.close(), 150);
                } else if (item.id === 'mobile-theme-toggle') {
                    // 主题切换按钮
                    if (window.themeSwitcher) {
                        window.themeSwitcher.toggle();
                    }
                }
            });
        });

        // 移动端主题切换按钮
        const themeToggle = document.getElementById('mobile-theme-toggle');
        if (themeToggle && window.themeSwitcher) {
            themeToggle.addEventListener('click', () => {
                window.themeSwitcher.toggle();
            });
        }
    },

    toggle() {
        this.isOpen ? this.close() : this.open();
    },

    open() {
        this.isOpen = true;
        this.menu.classList.add('active');
        this.menuBtn.classList.add('open');
        if (this.overlay) {
            this.overlay.classList.add('active');
        }
        // 禁止页面滚动
        document.body.style.overflow = 'hidden';
    },

    close() {
        this.isOpen = false;
        this.menu.classList.remove('active');
        this.menuBtn.classList.remove('open');
        if (this.overlay) {
            this.overlay.classList.remove('active');
        }
        // 恢复页面滚动
        document.body.style.overflow = '';
    }
};

// 页面初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化移动菜单
    MobileMenu.init();

    // 初始化所有格式化时间
    document.querySelectorAll('[data-time]').forEach(el => {
        const time = el.getAttribute('data-time');
        if (time) {
            el.textContent = Utils.formatTime(time);
        }
    });

    // 处理Flash消息自动消失
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // 初始化主题切换
    if (typeof ThemeSwitcher !== 'undefined') {
        window.themeSwitcher = new ThemeSwitcher();
    }
});

// 导出
window.Utils = Utils;
