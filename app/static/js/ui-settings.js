/**
 * UI设置面板
 * 控制鼠标拖尾等视觉效果
 */

(function() {
    'use strict';

    class UISettingsPanel {
        constructor() {
            this.isOpen = false;
            this.panelElement = null;
            this.buttonElement = null;
            
            this.init();
        }

        init() {
            this.createElements();
            this.attachEvents();
            this.loadSettings();
        }

        createElements() {
            // 创建样式
            this.injectStyles();

            // 创建设置按钮
            this.buttonElement = document.createElement('button');
            this.buttonElement.className = 'ui-settings-button';
            this.buttonElement.innerHTML = '⚙️';
            this.buttonElement.title = '界面设置';
            document.body.appendChild(this.buttonElement);

            // 创建设置面板
            this.panelElement = document.createElement('div');
            this.panelElement.className = 'ui-settings-panel';
            this.panelElement.innerHTML = `
                <div class="ui-settings-header">
                    <h3>界面设置</h3>
                    <button class="ui-settings-close">✕</button>
                </div>
                <div class="ui-settings-body">
                    <div class="ui-settings-item">
                        <div class="ui-settings-item-info">
                            <div class="ui-settings-item-title">鼠标拖尾效果</div>
                            <div class="ui-settings-item-desc">跟随鼠标的彩色粒子轨迹</div>
                        </div>
                        <label class="ui-settings-switch">
                            <input type="checkbox" id="cursor-trail-toggle">
                            <span class="ui-settings-slider"></span>
                        </label>
                    </div>
                    <div class="ui-settings-item">
                        <div class="ui-settings-item-info">
                            <div class="ui-settings-item-title">花瓣飘落效果</div>
                            <div class="ui-settings-item-desc">页面背景的装饰动画</div>
                        </div>
                        <label class="ui-settings-switch">
                            <input type="checkbox" id="petals-toggle">
                            <span class="ui-settings-slider"></span>
                        </label>
                    </div>
                </div>
            `;
            document.body.appendChild(this.panelElement);
        }

        injectStyles() {
            const style = document.createElement('style');
            style.textContent = `
                /* 设置按钮 */
                .ui-settings-button {
                    position: fixed;
                    left: 20px;
                    bottom: 20px;
                    width: 48px;
                    height: 48px;
                    border-radius: 50%;
                    background: var(--bg-secondary);
                    border: 1px solid var(--border-color);
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                    cursor: pointer;
                    z-index: 998;
                    font-size: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.3s ease;
                }

                .ui-settings-button:hover {
                    transform: rotate(90deg);
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                }

                /* 设置面板 */
                .ui-settings-panel {
                    position: fixed;
                    left: 20px;
                    bottom: 80px;
                    width: 320px;
                    max-width: calc(100vw - 40px);
                    background: var(--bg-secondary);
                    border: 1px solid var(--border-color);
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
                    z-index: 999;
                    opacity: 0;
                    transform: translateY(20px);
                    pointer-events: none;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }

                .ui-settings-panel.show {
                    opacity: 1;
                    transform: translateY(0);
                    pointer-events: auto;
                }

                .ui-settings-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 16px;
                    border-bottom: 1px solid var(--border-color);
                }

                .ui-settings-header h3 {
                    margin: 0;
                    font-size: 16px;
                    font-weight: 600;
                    color: var(--text-primary);
                }

                .ui-settings-close {
                    background: none;
                    border: none;
                    font-size: 20px;
                    color: var(--text-muted);
                    cursor: pointer;
                    padding: 4px;
                    line-height: 1;
                    transition: color 0.2s;
                }

                .ui-settings-close:hover {
                    color: var(--text-primary);
                }

                .ui-settings-body {
                    padding: 8px;
                }

                .ui-settings-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px;
                    border-radius: 8px;
                    transition: background 0.2s;
                }

                .ui-settings-item:hover {
                    background: var(--bg-tertiary);
                }

                .ui-settings-item-info {
                    flex: 1;
                }

                .ui-settings-item-title {
                    font-size: 14px;
                    font-weight: 500;
                    color: var(--text-primary);
                    margin-bottom: 4px;
                }

                .ui-settings-item-desc {
                    font-size: 12px;
                    color: var(--text-muted);
                }

                /* 开关按钮 */
                .ui-settings-switch {
                    position: relative;
                    display: inline-block;
                    width: 48px;
                    height: 28px;
                    flex-shrink: 0;
                }

                .ui-settings-switch input {
                    opacity: 0;
                    width: 0;
                    height: 0;
                }

                .ui-settings-slider {
                    position: absolute;
                    cursor: pointer;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: #ccc;
                    transition: 0.3s;
                    border-radius: 28px;
                }

                .ui-settings-slider:before {
                    position: absolute;
                    content: "";
                    height: 20px;
                    width: 20px;
                    left: 4px;
                    bottom: 4px;
                    background-color: white;
                    transition: 0.3s;
                    border-radius: 50%;
                }

                .ui-settings-switch input:checked + .ui-settings-slider {
                    background-color: var(--primary-color);
                }

                .ui-settings-switch input:checked + .ui-settings-slider:before {
                    transform: translateX(20px);
                }

                /* 移动端适配 */
                @media (max-width: 768px) {
                    .ui-settings-button {
                        left: 16px;
                        bottom: 16px;
                        width: 44px;
                        height: 44px;
                        font-size: 22px;
                    }

                    .ui-settings-panel {
                        left: 16px;
                        bottom: 72px;
                        width: calc(100vw - 32px);
                    }
                }
            `;
            document.head.appendChild(style);
        }

        attachEvents() {
            // 设置按钮点击
            this.buttonElement.addEventListener('click', () => {
                this.toggle();
            });

            // 关闭按钮
            const closeBtn = this.panelElement.querySelector('.ui-settings-close');
            closeBtn.addEventListener('click', () => {
                this.close();
            });

            // 点击面板外部关闭
            document.addEventListener('click', (e) => {
                if (this.isOpen && 
                    !this.panelElement.contains(e.target) && 
                    !this.buttonElement.contains(e.target)) {
                    this.close();
                }
            });

            // 鼠标拖尾开关
            const cursorTrailToggle = document.getElementById('cursor-trail-toggle');
            cursorTrailToggle.addEventListener('change', (e) => {
                if (window.CursorTrail) {
                    if (e.target.checked) {
                        window.CursorTrail.enable();
                    } else {
                        window.CursorTrail.disable();
                    }
                }
            });

            // 花瓣效果开关
            const petalsToggle = document.getElementById('petals-toggle');
            petalsToggle.addEventListener('change', (e) => {
                if (window.PetalEffect) {
                    if (e.target.checked) {
                        window.PetalEffect.enable();
                    } else {
                        window.PetalEffect.disable();
                    }
                }
            });
        }

        loadSettings() {
            // 加载鼠标拖尾设置
            const cursorTrailToggle = document.getElementById('cursor-trail-toggle');
            if (window.CursorTrail) {
                cursorTrailToggle.checked = window.CursorTrail.isEnabled();
            } else {
                const enabled = localStorage.getItem('cursorTrailEnabled') !== 'false';
                cursorTrailToggle.checked = enabled;
            }

            // 加载花瓣效果设置
            const petalsToggle = document.getElementById('petals-toggle');
            if (window.PetalEffect && window.PetalEffect.isEnabled) {
                petalsToggle.checked = window.PetalEffect.isEnabled();
            } else {
                const enabled = localStorage.getItem('petalsEnabled') !== 'false';
                petalsToggle.checked = enabled;
            }
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
            this.panelElement.classList.add('show');
        }

        close() {
            this.isOpen = false;
            this.panelElement.classList.remove('show');
        }
    }

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            new UISettingsPanel();
        });
    } else {
        new UISettingsPanel();
    }
})();
