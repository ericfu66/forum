/**
 * 移动端 UI 组件
 * 包含底部抽屉、侧边抽屉和触摸手势处理
 */

// 底部抽屉组件
class BottomDrawer {
    constructor(options = {}) {
        this.id = options.id || 'bottom-drawer-' + Date.now();
        this.title = options.title || '';
        this.content = options.content || '';
        this.onOpen = options.onOpen || null;
        this.onClose = options.onClose || null;
        this.maxHeight = options.maxHeight || '70vh';
        
        this.isOpen = false;
        this.startY = 0;
        this.currentY = 0;
        this.isDragging = false;
        
        this.create();
        this.bindEvents();
    }
    
    create() {
        // 创建遮罩层
        if (!document.getElementById('drawer-overlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'drawer-overlay';
            overlay.className = 'drawer-overlay';
            document.body.appendChild(overlay);
        }
        
        // 创建抽屉
        const drawer = document.createElement('div');
        drawer.id = this.id;
        drawer.className = 'bottom-drawer';
        drawer.style.maxHeight = this.maxHeight;
        drawer.innerHTML = `
            <div class="drawer-handle"></div>
            <div class="drawer-header">
                <h3 class="drawer-title">${this.title}</h3>
                <button class="drawer-close" aria-label="关闭">&times;</button>
            </div>
            <div class="drawer-content">${this.content}</div>
        `;
        
        document.body.appendChild(drawer);
        
        this.element = drawer;
        this.overlay = document.getElementById('drawer-overlay');
        this.handle = drawer.querySelector('.drawer-handle');
        this.closeBtn = drawer.querySelector('.drawer-close');
    }
    
    bindEvents() {
        // 关闭按钮
        this.closeBtn.addEventListener('click', () => this.close());
        
        // 遮罩层点击关闭
        this.overlay.addEventListener('click', () => this.close());
        
        // 触摸手势
        this.handle.addEventListener('touchstart', (e) => this.onTouchStart(e), { passive: true });
        this.element.addEventListener('touchmove', (e) => this.onTouchMove(e), { passive: false });
        this.element.addEventListener('touchend', (e) => this.onTouchEnd(e));
        
        // 键盘事件 - ESC 关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }
    
    onTouchStart(e) {
        this.isDragging = true;
        this.startY = e.touches[0].clientY;
        this.element.style.transition = 'none';
    }
    
    onTouchMove(e) {
        if (!this.isDragging) return;
        
        this.currentY = e.touches[0].clientY;
        const deltaY = this.currentY - this.startY;
        
        // 只允许向下拖动
        if (deltaY > 0) {
            this.element.style.transform = `translateY(${deltaY}px)`;
            e.preventDefault();
        }
    }
    
    onTouchEnd(e) {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.element.style.transition = '';
        
        const deltaY = this.currentY - this.startY;
        
        // 如果拖动超过 100px，关闭抽屉
        if (deltaY > 100) {
            this.close();
        } else {
            this.element.style.transform = '';
        }
    }
    
    open() {
        this.isOpen = true;
        this.element.classList.add('open');
        this.overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        if (this.onOpen) this.onOpen();
    }
    
    close() {
        this.isOpen = false;
        this.element.classList.remove('open');
        this.element.style.transform = '';
        this.overlay.classList.remove('active');
        document.body.style.overflow = '';
        
        if (this.onClose) this.onClose();
    }
    
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }
    
    setContent(html) {
        this.element.querySelector('.drawer-content').innerHTML = html;
    }
    
    destroy() {
        this.element.remove();
    }
}

// 侧边抽屉组件
class SideDrawer {
    constructor(options = {}) {
        this.id = options.id || 'side-drawer-' + Date.now();
        this.title = options.title || '';
        this.content = options.content || '';
        this.position = options.position || 'left'; // 'left' or 'right'
        this.width = options.width || '280px';
        this.onOpen = options.onOpen || null;
        this.onClose = options.onClose || null;
        
        this.isOpen = false;
        this.startX = 0;
        this.currentX = 0;
        this.isDragging = false;
        
        this.create();
        this.bindEvents();
    }
    
    create() {
        // 创建遮罩层
        if (!document.getElementById('drawer-overlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'drawer-overlay';
            overlay.className = 'drawer-overlay';
            document.body.appendChild(overlay);
        }
        
        // 创建抽屉
        const drawer = document.createElement('div');
        drawer.id = this.id;
        drawer.className = `side-drawer side-drawer-${this.position}`;
        drawer.style.width = this.width;
        drawer.innerHTML = `
            <div class="drawer-header">
                <h3 class="drawer-title">${this.title}</h3>
                <button class="drawer-close" aria-label="关闭">&times;</button>
            </div>
            <div class="drawer-content">${this.content}</div>
        `;
        
        document.body.appendChild(drawer);
        
        this.element = drawer;
        this.overlay = document.getElementById('drawer-overlay');
        this.closeBtn = drawer.querySelector('.drawer-close');
    }
    
    bindEvents() {
        // 关闭按钮
        this.closeBtn.addEventListener('click', () => this.close());
        
        // 遮罩层点击关闭
        this.overlay.addEventListener('click', () => this.close());
        
        // 触摸手势
        this.element.addEventListener('touchstart', (e) => this.onTouchStart(e), { passive: true });
        this.element.addEventListener('touchmove', (e) => this.onTouchMove(e), { passive: false });
        this.element.addEventListener('touchend', (e) => this.onTouchEnd(e));
        
        // 键盘事件 - ESC 关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }
    
    onTouchStart(e) {
        this.isDragging = true;
        this.startX = e.touches[0].clientX;
        this.element.style.transition = 'none';
    }
    
    onTouchMove(e) {
        if (!this.isDragging) return;
        
        this.currentX = e.touches[0].clientX;
        const deltaX = this.currentX - this.startX;
        
        // 根据位置决定拖动方向
        if (this.position === 'left' && deltaX < 0) {
            this.element.style.transform = `translateX(${deltaX}px)`;
            e.preventDefault();
        } else if (this.position === 'right' && deltaX > 0) {
            this.element.style.transform = `translateX(${deltaX}px)`;
            e.preventDefault();
        }
    }
    
    onTouchEnd(e) {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        this.element.style.transition = '';
        
        const deltaX = this.currentX - this.startX;
        const threshold = 80;
        
        // 根据位置和拖动距离决定是否关闭
        if ((this.position === 'left' && deltaX < -threshold) ||
            (this.position === 'right' && deltaX > threshold)) {
            this.close();
        } else {
            this.element.style.transform = '';
        }
    }
    
    open() {
        this.isOpen = true;
        this.element.classList.add('open');
        this.overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
        
        if (this.onOpen) this.onOpen();
    }
    
    close() {
        this.isOpen = false;
        this.element.classList.remove('open');
        this.element.style.transform = '';
        this.overlay.classList.remove('active');
        document.body.style.overflow = '';
        
        if (this.onClose) this.onClose();
    }
    
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }
    
    setContent(html) {
        this.element.querySelector('.drawer-content').innerHTML = html;
    }
    
    destroy() {
        this.element.remove();
    }
}


// 移动端检测
function isMobile() {
    return window.innerWidth <= 768;
}

// 视口变化监听
function onViewportChange(callback) {
    const mediaQuery = window.matchMedia('(max-width: 768px)');
    
    // 初始调用
    callback(mediaQuery.matches);
    
    // 监听变化
    mediaQuery.addEventListener('change', (e) => {
        callback(e.matches);
    });
}

// 触摸目标尺寸检查
function checkTouchTargets() {
    if (!isMobile()) return;
    
    const minSize = 44;
    const interactiveElements = document.querySelectorAll('button, a, input, select, textarea, [role="button"]');
    
    interactiveElements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width < minSize || rect.height < minSize) {
            console.warn('Touch target too small:', el, `${rect.width}x${rect.height}`);
        }
    });
}

// 键盘弹出处理
function handleKeyboardVisibility() {
    if (!isMobile()) return;
    
    const initialHeight = window.innerHeight;
    
    window.addEventListener('resize', () => {
        const currentHeight = window.innerHeight;
        const keyboardVisible = currentHeight < initialHeight * 0.75;
        
        document.body.classList.toggle('keyboard-visible', keyboardVisible);
        
        // 触发自定义事件
        window.dispatchEvent(new CustomEvent('keyboardVisibilityChange', {
            detail: { visible: keyboardVisible }
        }));
    });
}

// 初始化移动端 UI
function initMobileUI() {
    // 检测动画偏好
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        document.body.classList.add('reduce-motion');
    }
    
    // 处理键盘
    handleKeyboardVisibility();
    
    // 开发模式下检查触摸目标
    if (window.location.hostname === 'localhost') {
        setTimeout(checkTouchTargets, 1000);
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initMobileUI);

// 导出到全局
window.BottomDrawer = BottomDrawer;
window.SideDrawer = SideDrawer;
window.isMobile = isMobile;
window.onViewportChange = onViewportChange;
