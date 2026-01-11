/**
 * 鼠标拖尾动效
 * 创建跟随鼠标的粒子轨迹效果
 */

(function() {
    'use strict';

    // 配置
    const CONFIG = {
        particleCount: 15,        // 拖尾粒子数量
        particleSize: 8,          // 粒子大小
        particleLifetime: 800,    // 粒子生命周期（毫秒）
        colors: [                 // 粒子颜色池
            '#E91E63', '#FF6B9D', '#FFC1E3',
            '#9C27B0', '#BA68C8', '#CE93D8',
            '#3F51B5', '#7986CB', '#9FA8DA',
            '#00BCD4', '#4DD0E1', '#80DEEA'
        ],
        enabled: true,            // 是否启用
        mobileEnabled: false      // 移动端是否启用
    };

    // 检测是否为移动设备
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    // 移动端默认禁用
    if (isMobile && !CONFIG.mobileEnabled) {
        return;
    }

    // 粒子类
    class Particle {
        constructor(x, y) {
            this.x = x;
            this.y = y;
            this.size = CONFIG.particleSize;
            this.color = CONFIG.colors[Math.floor(Math.random() * CONFIG.colors.length)];
            this.life = CONFIG.particleLifetime;
            this.maxLife = CONFIG.particleLifetime;
            this.vx = (Math.random() - 0.5) * 2;
            this.vy = (Math.random() - 0.5) * 2;
            this.element = this.createElement();
        }

        createElement() {
            const el = document.createElement('div');
            el.className = 'cursor-particle';
            el.style.cssText = `
                position: fixed;
                pointer-events: none;
                z-index: 9999;
                width: ${this.size}px;
                height: ${this.size}px;
                background: ${this.color};
                border-radius: 50%;
                left: ${this.x}px;
                top: ${this.y}px;
                opacity: 1;
                transition: opacity 0.1s ease;
                box-shadow: 0 0 10px ${this.color};
            `;
            document.body.appendChild(el);
            return el;
        }

        update(deltaTime) {
            this.life -= deltaTime;
            this.x += this.vx;
            this.y += this.vy;
            
            const opacity = this.life / this.maxLife;
            const scale = 0.5 + (opacity * 0.5);
            
            this.element.style.left = this.x + 'px';
            this.element.style.top = this.y + 'px';
            this.element.style.opacity = opacity;
            this.element.style.transform = `scale(${scale})`;
            
            return this.life > 0;
        }

        destroy() {
            if (this.element && this.element.parentNode) {
                this.element.parentNode.removeChild(this.element);
            }
        }
    }

    // 粒子管理器
    class ParticleManager {
        constructor() {
            this.particles = [];
            this.lastTime = Date.now();
            this.mouseX = 0;
            this.mouseY = 0;
            this.lastMouseX = 0;
            this.lastMouseY = 0;
            this.lastEmitTime = 0;
            this.emitInterval = 30; // 发射间隔（毫秒）
            this.isMoving = false;
            this.moveTimeout = null;
            
            this.init();
        }

        init() {
            // 监听鼠标移动
            document.addEventListener('mousemove', (e) => {
                this.mouseX = e.clientX;
                this.mouseY = e.clientY;
                
                // 检测鼠标是否真的在移动
                const moved = Math.abs(this.mouseX - this.lastMouseX) > 1 || 
                              Math.abs(this.mouseY - this.lastMouseY) > 1;
                
                if (moved) {
                    this.isMoving = true;
                    this.lastMouseX = this.mouseX;
                    this.lastMouseY = this.mouseY;
                    
                    // 清除之前的超时
                    if (this.moveTimeout) {
                        clearTimeout(this.moveTimeout);
                    }
                    
                    // 设置超时，停止移动后100ms标记为不移动
                    this.moveTimeout = setTimeout(() => {
                        this.isMoving = false;
                    }, 100);
                }
            });

            // 启动动画循环
            this.animate();
        }

        emit() {
            // 只在鼠标移动时发射粒子
            if (!this.isMoving) {
                return;
            }
            
            const now = Date.now();
            if (now - this.lastEmitTime < this.emitInterval) {
                return;
            }
            this.lastEmitTime = now;

            // 限制粒子数量
            if (this.particles.length >= CONFIG.particleCount) {
                const oldest = this.particles.shift();
                oldest.destroy();
            }

            this.particles.push(new Particle(this.mouseX, this.mouseY));
        }

        update() {
            const now = Date.now();
            const deltaTime = now - this.lastTime;
            this.lastTime = now;

            // 更新所有粒子
            this.particles = this.particles.filter(particle => {
                const alive = particle.update(deltaTime);
                if (!alive) {
                    particle.destroy();
                }
                return alive;
            });
        }

        animate() {
            this.emit();
            this.update();
            requestAnimationFrame(() => this.animate());
        }

        destroy() {
            this.particles.forEach(p => p.destroy());
            this.particles = [];
        }
    }

    // 初始化
    let manager = null;

    function init() {
        if (!CONFIG.enabled) return;
        
        // 从localStorage读取用户偏好
        const userPreference = localStorage.getItem('cursorTrailEnabled');
        if (userPreference === 'false') {
            return;
        }

        manager = new ParticleManager();
    }

    // 提供全局控制接口
    window.CursorTrail = {
        enable: function() {
            if (!manager) {
                CONFIG.enabled = true;
                localStorage.setItem('cursorTrailEnabled', 'true');
                init();
            }
        },
        disable: function() {
            if (manager) {
                manager.destroy();
                manager = null;
                CONFIG.enabled = false;
                localStorage.setItem('cursorTrailEnabled', 'false');
            }
        },
        toggle: function() {
            if (manager) {
                this.disable();
            } else {
                this.enable();
            }
        },
        isEnabled: function() {
            return manager !== null;
        }
    };

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
