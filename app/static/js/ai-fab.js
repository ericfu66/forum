/**
 * AI功能悬浮球 (Floating Action Button)
 * 移动端快捷访问AI功能
 */

(function() {
    'use strict';

    // 检测是否为移动设备
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    // 仅在移动端启用
    if (!isMobile) {
        return;
    }

    // AI功能配置
    const AI_FEATURES = [
        {
            id: 'chat',
            name: 'AI对话',
            icon: '💬',
            url: '/ai/chat',
            color: '#E91E63',
            enabled: true // 将由后端数据控制
        },
        {
            id: 'write',
            name: 'AI写稿',
            icon: '✍️',
            url: '/ai/write',
            color: '#9C27B0',
            enabled: true
        },
        {
            id: 'image',
            name: 'AI绘图',
            icon: '🎨',
            url: '/ai/image',
            color: '#3F51B5',
            enabled: true
        },
        {
            id: 'gallery',
            name: '图片广场',
            icon: '🖼️',
            url: '/ai/gallery',
            color: '#00BCD4',
            enabled: true
        }
    ];

    class AIFloatingButton {
        constructor() {
            this.isOpen = false;
            this.fabElement = null;
            this.menuElement = null;
            this.overlayElement = null;
            
            this.init();
        }

        init() {
            this.createElements();
            this.attachEvents();
            this.loadEnabledFeatures();
        }

        loadEnabledFeatures() {
            // 从页面中读取AI功能启用状态
            const navItems = document.querySelectorAll('.nav-item');
            const enabledUrls = new Set();
            
            navItems.forEach(item => {
                const href = item.getAttribute('href');
                if (href && href.startsWith('/ai/')) {
                    enabledUrls.add(href);
                }
            });

            // 更新功能启用状态
            AI_FEATURES.forEach(feature => {
                feature.enabled = enabledUrls.has(feature.url);
            });
        }

        createElements() {
            // 创建样式
            this.injectStyles();

            // 创建遮罩层
            this.overlayElement = document.createElement('div');
            this.overlayElement.className = 'ai-fab-overlay';
            document.body.appendChild(this.overlayElement);

            // 创建菜单容器
            this.menuElement = document.createElement('div');
            this.menuElement.className = 'ai-fab-menu';
            
            // 创建菜单项
            const enabledFeatures = AI_FEATURES.filter(f => f.enabled);
            enabledFeatures.forEach((feature, index) => {
                const item = document.createElement('a');
                item.className = 'ai-fab-menu-item';
                item.href = feature.url;
                item.style.transitionDelay = `${index * 50}ms`;
                item.innerHTML = `
                    <div class="ai-fab-menu-icon" style="background: ${feature.color}">
                        ${feature.icon}
                    </div>
                    <span class="ai-fab-menu-label">${feature.name}</span>
                `;
                this.menuElement.appendChild(item);
            });
            
            document.body.appendChild(this.menuElement);

            // 创建主按钮
            this.fabElement = document.createElement('button');
            this.fabElement.className = 'ai-fab-button';
            this.fabElement.innerHTML = `
                <div class="ai-fab-icon">
                    <span class="ai-fab-icon-default">🤖</span>
                    <span class="ai-fab-icon-close">✕</span>
                </div>
            `;
            document.body.appendChild(this.fabElement);
        }

        injectStyles() {
            const style = document.createElement('style');
            style.textContent = `
                /* AI悬浮球样式 */
                .ai-fab-button {
                    position: fixed;
                    right: 20px;
                    bottom: 80px;
                    width: 56px;
                    height: 56px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #E91E63 0%, #9C27B0 100%);
                    border: none;
                    box-shadow: 0 4px 12px rgba(233, 30, 99, 0.4);
                    cursor: pointer;
                    z-index: 1000;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    -webkit-tap-highlight-color: transparent;
                }

                .ai-fab-button:active {
                    transform: scale(0.95);
                }

                .ai-fab-button.open {
                    background: linear-gradient(135deg, #f44336 0%, #e91e63 100%);
                    box-shadow: 0 6px 20px rgba(244, 67, 54, 0.5);
                }

                .ai-fab-icon {
                    position: relative;
                    width: 28px;
                    height: 28px;
                    font-size: 28px;
                    line-height: 1;
                }

                .ai-fab-icon span {
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }

                .ai-fab-icon-default {
                    opacity: 1;
                    transform: translate(-50%, -50%) rotate(0deg);
                }

                .ai-fab-icon-close {
                    opacity: 0;
                    transform: translate(-50%, -50%) rotate(-90deg);
                    font-size: 24px;
                    color: white;
                }

                .ai-fab-button.open .ai-fab-icon-default {
                    opacity: 0;
                    transform: translate(-50%, -50%) rotate(90deg);
                }

                .ai-fab-button.open .ai-fab-icon-close {
                    opacity: 1;
                    transform: translate(-50%, -50%) rotate(0deg);
                }

                /* 遮罩层 */
                .ai-fab-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.5);
                    z-index: 999;
                    opacity: 0;
                    pointer-events: none;
                    transition: opacity 0.3s ease;
                    backdrop-filter: blur(2px);
                }

                .ai-fab-overlay.show {
                    opacity: 1;
                    pointer-events: auto;
                }

                /* 菜单 */
                .ai-fab-menu {
                    position: fixed;
                    right: 20px;
                    bottom: 150px;
                    z-index: 1000;
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                    pointer-events: none;
                }

                .ai-fab-menu-item {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    background: var(--bg-secondary);
                    padding: 12px 16px;
                    border-radius: 28px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
                    text-decoration: none;
                    color: var(--text-primary);
                    opacity: 0;
                    transform: translateY(20px) scale(0.8);
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    pointer-events: none;
                    white-space: nowrap;
                }

                .ai-fab-menu.show .ai-fab-menu-item {
                    opacity: 1;
                    transform: translateY(0) scale(1);
                    pointer-events: auto;
                }

                .ai-fab-menu-item:active {
                    transform: scale(0.95);
                }

                .ai-fab-menu-icon {
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 20px;
                    flex-shrink: 0;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }

                .ai-fab-menu-label {
                    font-size: 14px;
                    font-weight: 500;
                }

                /* 动画效果 */
                @keyframes fabPulse {
                    0%, 100% {
                        box-shadow: 0 4px 12px rgba(233, 30, 99, 0.4);
                    }
                    50% {
                        box-shadow: 0 4px 20px rgba(233, 30, 99, 0.6);
                    }
                }

                .ai-fab-button:not(.open) {
                    animation: fabPulse 2s ease-in-out infinite;
                }

                /* 响应式调整 */
                @media (max-width: 480px) {
                    .ai-fab-button {
                        right: 16px;
                        bottom: 70px;
                        width: 52px;
                        height: 52px;
                    }

                    .ai-fab-menu {
                        right: 16px;
                        bottom: 135px;
                    }

                    .ai-fab-menu-item {
                        padding: 10px 14px;
                    }

                    .ai-fab-menu-icon {
                        width: 36px;
                        height: 36px;
                        font-size: 18px;
                    }

                    .ai-fab-menu-label {
                        font-size: 13px;
                    }
                }
            `;
            document.head.appendChild(style);
        }

        attachEvents() {
            // 主按钮点击
            this.fabElement.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggle();
            });

            // 遮罩层点击关闭
            this.overlayElement.addEventListener('click', () => {
                this.close();
            });

            // 菜单项点击
            this.menuElement.addEventListener('click', () => {
                this.close();
            });

            // 阻止菜单项的事件冒泡
            const menuItems = this.menuElement.querySelectorAll('.ai-fab-menu-item');
            menuItems.forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            });
        }

        toggle() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }

        open() {
            this.isOpen = true;
            this.fabElement.classList.add('open');
            this.menuElement.classList.add('show');
            this.overlayElement.classList.add('show');
            document.body.style.overflow = 'hidden';
        }

        close() {
            this.isOpen = false;
            this.fabElement.classList.remove('open');
            this.menuElement.classList.remove('show');
            this.overlayElement.classList.remove('show');
            document.body.style.overflow = '';
        }
    }

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new AIFloatingButton();
        });
    } else {
        new AIFloatingButton();
    }
})();
