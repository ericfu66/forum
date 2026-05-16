/**
 * 落英动效 - 飘落的花瓣/树叶/雪花
 * 支持多主题、性能自适应、视差效果
 */

// 主题配置
const PETAL_THEMES = {
    sakura: {
        name: '樱花',
        colors: [
            'linear-gradient(135deg, #ffb7c5 0%, #ff69b4 50%, #ff1493 100%)',
            'linear-gradient(135deg, #ffc0cb 0%, #ffb6c1 50%, #ff69b4 100%)',
            'linear-gradient(135deg, #ffe4e9 0%, #ffb7c5 50%, #ff69b4 100%)'
        ],
        shapes: ['petal-sakura'],
        shadowColor: 'rgba(255, 105, 180, 0.3)'
    },
    autumn: {
        name: '秋叶',
        colors: [
            'linear-gradient(135deg, #ff6b35 0%, #f7931e 50%, #fbb03b 100%)',
            'linear-gradient(135deg, #c1440e 0%, #e25822 50%, #ff6b35 100%)',
            'linear-gradient(135deg, #8b4513 0%, #a0522d 50%, #cd853f 100%)'
        ],
        shapes: ['petal-leaf'],
        shadowColor: 'rgba(255, 107, 53, 0.3)'
    },
    snow: {
        name: '雪花',
        colors: [
            'linear-gradient(135deg, #ffffff 0%, #e8f4f8 50%, #d4e9f0 100%)',
            'linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 50%, #cce5ff 100%)',
            'linear-gradient(135deg, #ffffff 0%, #f5f5f5 50%, #e0e0e0 100%)'
        ],
        shapes: ['petal-snow'],
        shadowColor: 'rgba(200, 220, 255, 0.4)'
    }
};

class PetalsEffect {
    constructor(options = {}) {
        this.options = {
            count: options.count || 15,
            minDuration: options.minDuration || 8,
            maxDuration: options.maxDuration || 15,
            enabled: options.enabled !== false,
            theme: options.theme || 'sakura',
            parallaxEnabled: options.parallaxEnabled !== false,
            performanceMode: options.performanceMode || 'auto',
            ...options
        };

        this.container = null;
        this.petals = [];
        this.isEnabled = this.loadPreference();
        this.currentTheme = this.loadThemePreference();
        this.performanceLevel = 'high';
        this.scrollY = 0;
        this.animationFrame = null;

        if (this.isEnabled) {
            this.init();
        }
    }

    loadPreference() {
        const pref = localStorage.getItem('petals-enabled');
        return pref === null ? this.options.enabled : pref === 'true';
    }

    savePreference(enabled) {
        localStorage.setItem('petals-enabled', enabled.toString());
    }

    loadThemePreference() {
        return localStorage.getItem('petals-theme') || this.options.theme;
    }

    saveThemePreference(theme) {
        localStorage.setItem('petals-theme', theme);
    }

    init() {
        // 检测性能
        this.detectPerformance();
        
        // 创建容器
        this.container = document.createElement('div');
        this.container.className = 'petals-container';
        this.container.id = 'petals-container';
        document.body.appendChild(this.container);

        // 创建花瓣
        this.createPetals();

        // 绑定滚动事件（视差效果）
        if (this.options.parallaxEnabled) {
            this.bindScrollEvent();
        }
    }

    detectPerformance() {
        if (this.options.performanceMode !== 'auto') {
            this.performanceLevel = this.options.performanceMode;
            return;
        }

        // 检测设备性能
        const start = performance.now();
        let count = 0;
        while (performance.now() - start < 5) {
            count++;
        }

        // 根据计算能力判断性能等级
        if (count < 50000) {
            this.performanceLevel = 'low';
        } else {
            this.performanceLevel = 'high';
        }

        // 移动设备默认低性能模式
        if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
            this.performanceLevel = 'low';
        }
    }

    getAdjustedCount() {
        const baseCount = this.options.count;
        if (this.performanceLevel === 'low') {
            return Math.max(5, Math.floor(baseCount * 0.5));
        }
        return baseCount;
    }

    createPetals() {
        const count = this.getAdjustedCount();
        const theme = PETAL_THEMES[this.currentTheme] || PETAL_THEMES.sakura;

        for (let i = 0; i < count; i++) {
            this.createPetal(i, theme);
        }
    }

    createPetal(index, theme) {
        const petal = document.createElement('div');
        petal.className = `petal ${theme.shapes[0]}`;
        petal.dataset.depth = (Math.random() * 0.5 + 0.5).toFixed(2); // 0.5-1.0 深度

        // 随机属性
        const left = Math.random() * 100;
        const delay = Math.random() * 10;
        const duration = this.options.minDuration +
            Math.random() * (this.options.maxDuration - this.options.minDuration);
        const size = 10 + Math.random() * 10;
        const colorIndex = Math.floor(Math.random() * theme.colors.length);

        petal.style.cssText = `
            left: ${left}%;
            width: ${size}px;
            height: ${size}px;
            background: ${theme.colors[colorIndex]};
            box-shadow: 0 2px 4px ${theme.shadowColor};
            animation-duration: ${duration}s;
            animation-delay: ${delay}s;
            --depth: ${petal.dataset.depth};
        `;

        // 动画结束后重新定位
        petal.addEventListener('animationiteration', () => {
            petal.style.left = `${Math.random() * 100}%`;
        });

        this.container.appendChild(petal);
        this.petals.push(petal);
    }

    bindScrollEvent() {
        let ticking = false;
        
        window.addEventListener('scroll', () => {
            this.scrollY = window.scrollY;
            
            if (!ticking) {
                requestAnimationFrame(() => {
                    this.applyParallax();
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }

    applyParallax() {
        if (!this.options.parallaxEnabled || this.performanceLevel === 'low') return;

        this.petals.forEach(petal => {
            const depth = parseFloat(petal.dataset.depth);
            const movement = this.scrollY * (1 - depth) * 0.1;
            petal.style.transform = `translateY(${movement}px)`;
        });
    }

    setTheme(themeName) {
        if (!PETAL_THEMES[themeName]) {
            console.warn(`Unknown theme: ${themeName}`);
            return;
        }

        this.currentTheme = themeName;
        this.saveThemePreference(themeName);

        // 重新创建花瓣
        this.clearPetals();
        this.createPetals();
    }

    clearPetals() {
        this.petals.forEach(petal => petal.remove());
        this.petals = [];
    }

    enable() {
        this.isEnabled = true;
        this.savePreference(true);

        if (!this.container) {
            this.init();
        } else {
            this.container.style.display = 'block';
        }
    }

    disable() {
        this.isEnabled = false;
        this.savePreference(false);

        if (this.container) {
            this.container.style.display = 'none';
        }
    }

    toggle() {
        if (this.isEnabled) {
            this.disable();
        } else {
            this.enable();
        }
        return this.isEnabled;
    }

    updateOptions(newOptions) {
        Object.assign(this.options, newOptions);
        
        if (newOptions.theme && newOptions.theme !== this.currentTheme) {
            this.setTheme(newOptions.theme);
        }
        
        if (newOptions.count !== undefined) {
            this.clearPetals();
            this.createPetals();
        }
    }

    destroy() {
        if (this.container) {
            this.container.remove();
            this.container = null;
            this.petals = [];
        }
    }

    // 获取当前状态
    getStatus() {
        return {
            enabled: this.isEnabled,
            theme: this.currentTheme,
            petalCount: this.petals.length,
            performanceLevel: this.performanceLevel
        };
    }
}

// 初始化落英效果
document.addEventListener('DOMContentLoaded', () => {
    // 从服务器配置或默认值初始化
    const config = window.PETALS_CONFIG || {
        count: 12,
        minDuration: 10,
        maxDuration: 18,
        theme: 'sakura',
        parallaxEnabled: true
    };

    window.petalsEffect = new PetalsEffect(config);
    
    // 提供全局控制接口
    window.PetalEffect = {
        enable: function() {
            if (window.petalsEffect) {
                window.petalsEffect.enable();
            }
        },
        disable: function() {
            if (window.petalsEffect) {
                window.petalsEffect.disable();
            }
        },
        toggle: function() {
            if (window.petalsEffect) {
                return window.petalsEffect.toggle();
            }
            return false;
        },
        isEnabled: function() {
            return window.petalsEffect ? window.petalsEffect.isEnabled : false;
        },
        setTheme: function(theme) {
            if (window.petalsEffect) {
                window.petalsEffect.setTheme(theme);
            }
        }
    };
});

// 导出供外部使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PetalsEffect, PETAL_THEMES };
}
