/**
 * 后台管理功能
 */

class AdminPanel {
    constructor() {
        this.init();
    }

    init() {
        this.initConfigEditor();
        this.initUserActions();
        this.initPostActions();
        this.initStatsChart();
    }

    // 配置编辑器
    initConfigEditor() {
        const configSections = document.querySelectorAll('[data-config-section]');

        configSections.forEach(section => {
            const toggle = section.querySelector('.config-section-toggle');
            const content = section.querySelector('.config-section-content');

            if (toggle && content) {
                toggle.addEventListener('click', () => {
                    content.classList.toggle('d-none');
                });
            }

            // 保存配置按钮
            const saveBtn = section.querySelector('.btn-save-config');
            if (saveBtn) {
                saveBtn.addEventListener('click', () => this.saveConfig(section));
            }
        });
    }

    async saveConfig(section) {
        const category = section.getAttribute('data-config-section');
        const inputs = section.querySelectorAll('input, select');
        const updates = {};

        inputs.forEach(input => {
            const key = input.getAttribute('data-config-key');
            if (key) {
                updates[key] = input.value;
            }
        });

        const saveBtn = section.querySelector('.btn-save-config');
        const originalText = saveBtn.textContent;
        saveBtn.textContent = '保存中...';
        saveBtn.disabled = true;

        try {
            const response = await Utils.post('/admin/api/config/update', {
                category,
                updates
            });

            if (response.success) {
                Utils.showToast('配置已更新并重载', 'success');
            } else {
                Utils.showToast(response.message || '保存失败', 'danger');
            }
        } catch (e) {
            Utils.showToast('保存失败', 'danger');
        } finally {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }
    }

    // 用户操作
    initUserActions() {
        // 封禁用户
        document.querySelectorAll('[data-action="ban-user"]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const userId = btn.getAttribute('data-user-id');
                if (Utils.confirm('确定要封禁此用户吗？')) {
                    await this.banUser(userId, btn);
                }
            });
        });

        // 解封用户
        document.querySelectorAll('[data-action="unban-user"]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const userId = btn.getAttribute('data-user-id');
                await this.unbanUser(userId, btn);
            });
        });

        // 修改角色
        document.querySelectorAll('[data-action="change-role"]').forEach(select => {
            select.addEventListener('change', async (e) => {
                const userId = select.getAttribute('data-user-id');
                const role = select.value;
                await this.changeRole(userId, role);
            });
        });
    }

    async banUser(userId, btn) {
        const response = await Utils.post(`/admin/users/${userId}/ban`, {});
        if (response.success) {
            Utils.showToast('用户已封禁', 'success');
            location.reload();
        } else {
            Utils.showToast(response.message, 'danger');
        }
    }

    async unbanUser(userId, btn) {
        const response = await Utils.post(`/admin/users/${userId}/unban`, {});
        if (response.success) {
            Utils.showToast('用户已解封', 'success');
            location.reload();
        } else {
            Utils.showToast(response.message, 'danger');
        }
    }

    async changeRole(userId, role) {
        const response = await Utils.post(`/admin/users/${userId}/role`, { role });
        if (response.success) {
            Utils.showToast('角色已修改', 'success');
        } else {
            Utils.showToast(response.message, 'danger');
        }
    }

    // 帖子操作
    initPostActions() {
        // 删除帖子
        document.querySelectorAll('[data-action="delete-post"]').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const postId = btn.getAttribute('data-post-id');
                if (Utils.confirm('确定要删除此帖子吗？')) {
                    await this.deletePost(postId, btn);
                }
            });
        });

        // 置顶帖子
        document.querySelectorAll('[data-action="pin-post"]').forEach(checkbox => {
            checkbox.addEventListener('change', async (e) => {
                const postId = checkbox.getAttribute('data-post-id');
                await this.pinPost(postId, checkbox.checked);
            });
        });
    }

    async deletePost(postId, btn) {
        const response = await Utils.post(`/admin/posts/${postId}/delete`, {});
        if (response.success) {
            Utils.showToast('帖子已删除', 'success');
            location.reload();
        } else {
            Utils.showToast(response.message, 'danger');
        }
    }

    async pinPost(postId, isPinned) {
        const response = await Utils.post(`/admin/posts/${postId}/pin`, { is_pinned: isPinned });
        if (response.success) {
            Utils.showToast(isPinned ? '已置顶' : '已取消置顶', 'success');
        } else {
            Utils.showToast(response.message, 'danger');
        }
    }

    // 统计图表
    initStatsChart() {
        const canvas = document.getElementById('stats-chart');
        if (!canvas) return;

        // 简单的统计显示（可以使用Chart.js等库增强）
        this.loadStats();
    }

    async loadStats() {
        const response = await Utils.get('/admin/api/stats');
        if (response.success) {
            this.renderStats(response.stats);
        }
    }

    renderStats(stats) {
        // 更新统计数字
        const updateStat = (selector, value) => {
            const el = document.querySelector(selector);
            if (el) {
                el.textContent = value.toLocaleString();
            }
        };

        updateStat('[data-stat="total-users"]', stats.total.users);
        updateStat('[data-stat="total-posts"]', stats.total.posts);
        updateStat('[data-stat="total-comments"]', stats.total.comments);
        updateStat('[data-stat="today-users"]', stats.today.users);
        updateStat('[data-stat="today-posts"]', stats.today.posts);
        updateStat('[data-stat="ai-calls"]', stats.ai.total_calls);
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.admin-panel')) {
        window.adminPanel = new AdminPanel();
    }
});
