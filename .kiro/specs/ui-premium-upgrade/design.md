# Design Document: UI Premium Upgrade

## Overview

本设计文档描述了论坛系统UI高端化升级的技术实现方案，包括首页导览页、帖子展示页的视觉重设计，以及AI对话页面的移动端适配优化。设计采用现代化的视觉语言，包含渐变色、毛玻璃效果、流畅动画等高端设计元素，同时确保在移动端的良好体验。

## Architecture

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端架构                                │
├─────────────────────────────────────────────────────────────┤
│  CSS Layer                                                   │
│  ├── base.css (基础样式 + CSS变量)                           │
│  ├── components.css (组件样式)                               │
│  ├── premium.css (新增：高端视觉效果)                         │
│  └── mobile.css (新增：移动端专用样式)                        │
├─────────────────────────────────────────────────────────────┤
│  JavaScript Layer                                            │
│  ├── base.js (基础功能)                                      │
│  ├── ai-chat.js (AI对话功能)                                 │
│  └── mobile-ui.js (新增：移动端交互)                          │
├─────────────────────────────────────────────────────────────┤
│  Template Layer                                              │
│  ├── main/index.html (首页 - 重设计)                         │
│  ├── post/list.html (帖子列表 - 重设计)                      │
│  ├── post/detail.html (帖子详情 - 重设计)                    │
│  └── ai/chat.html (AI对话 - 移动端适配)                      │
└─────────────────────────────────────────────────────────────┘
```

### 设计系统

```
Design Tokens (CSS Variables)
├── Colors
│   ├── --premium-gradient-1: 主渐变色
│   ├── --premium-gradient-2: 次渐变色
│   ├── --glass-bg: 毛玻璃背景色
│   └── --glass-border: 毛玻璃边框色
├── Effects
│   ├── --premium-shadow: 高端阴影
│   ├── --glass-blur: 毛玻璃模糊度
│   └── --hover-lift: 悬停抬升距离
├── Animation
│   ├── --transition-smooth: 平滑过渡
│   ├── --animation-stagger: 交错动画延迟
│   └── --animation-bounce: 弹性动画
└── Spacing
    ├── --card-padding: 卡片内边距
    └── --section-gap: 区块间距
```

## Components and Interfaces

### 1. 高端卡片组件 (Premium Card)

```html
<div class="premium-card">
    <div class="premium-card-glow"></div>
    <div class="premium-card-content">
        <!-- 内容 -->
    </div>
</div>
```

CSS实现：
```css
.premium-card {
    position: relative;
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-xl);
    box-shadow: var(--premium-shadow);
    transition: transform var(--transition-smooth), 
                box-shadow var(--transition-smooth);
}

.premium-card:hover {
    transform: translateY(var(--hover-lift));
    box-shadow: var(--premium-shadow-hover);
}

.premium-card-glow {
    position: absolute;
    inset: -1px;
    background: var(--premium-gradient-1);
    border-radius: inherit;
    opacity: 0;
    transition: opacity var(--transition-smooth);
    z-index: -1;
}

.premium-card:hover .premium-card-glow {
    opacity: 0.1;
}
```

### 2. 移动端底部抽屉组件 (Bottom Drawer)

```html
<div class="bottom-drawer" id="assistant-drawer">
    <div class="drawer-handle"></div>
    <div class="drawer-header">
        <h3>选择助手</h3>
        <button class="drawer-close">×</button>
    </div>
    <div class="drawer-content">
        <!-- 助手列表 -->
    </div>
</div>
<div class="drawer-overlay" id="drawer-overlay"></div>
```

CSS实现：
```css
.bottom-drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-secondary);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    transform: translateY(100%);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 1001;
    max-height: 70vh;
    overflow-y: auto;
}

.bottom-drawer.open {
    transform: translateY(0);
}

.drawer-handle {
    width: 40px;
    height: 4px;
    background: var(--border-color);
    border-radius: 2px;
    margin: 12px auto;
}

.drawer-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s;
    z-index: 1000;
}

.drawer-overlay.active {
    opacity: 1;
    visibility: visible;
}
```

### 3. 移动端侧边抽屉组件 (Side Drawer)

```html
<div class="side-drawer" id="history-drawer">
    <div class="drawer-header">
        <h3>对话历史</h3>
        <button class="drawer-close">×</button>
    </div>
    <div class="drawer-content">
        <!-- 对话列表 -->
    </div>
</div>
```

### 4. 帖子卡片增强组件

```html
<article class="post-card-premium">
    <div class="post-card-image">
        <img src="..." alt="">
        <div class="post-card-category">技术</div>
    </div>
    <div class="post-card-body">
        <div class="post-card-meta">
            <img src="avatar.jpg" class="avatar-sm">
            <span class="author-name">作者名</span>
            <span class="post-time">2小时前</span>
        </div>
        <h3 class="post-card-title">帖子标题</h3>
        <p class="post-card-excerpt">帖子摘要...</p>
        <div class="post-card-stats">
            <span>👁️ 1.2k</span>
            <span>💬 23</span>
            <span>👍 89</span>
        </div>
    </div>
</article>
```

### 5. 视图切换组件

```html
<div class="view-switcher">
    <button class="view-btn active" data-view="list">
        <span>☰</span> 列表
    </button>
    <button class="view-btn" data-view="grid">
        <span>▦</span> 网格
    </button>
</div>
```

### 6. 移动端聊天头部组件

```html
<div class="mobile-chat-header">
    <button class="mobile-menu-trigger" id="history-trigger">
        ☰
    </button>
    <div class="current-assistant" id="assistant-trigger">
        <span class="assistant-icon">🤖</span>
        <span class="assistant-name">通用助手</span>
        <span class="dropdown-indicator">▼</span>
    </div>
    <button class="mobile-action-btn" id="new-chat-btn">
        ➕
    </button>
</div>
```

## Data Models

本次升级主要涉及前端UI，不需要新增数据模型。现有数据模型保持不变：

- Post: 帖子数据
- Board: 版块数据
- User: 用户数据
- AIDialog: AI对话数据

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

由于本功能主要涉及UI视觉设计和交互体验，大部分需求需要人工视觉验证。以下是可自动化测试的属性：

### Property 1: 视图切换功能正确性
*For any* 帖子列表页面，当用户点击视图切换按钮时，页面布局应正确切换到对应的视图模式（列表或网格）
**Validates: Requirements 2.5**

### Property 2: 长文章目录导航显示
*For any* 帖子详情页面，如果文章内容包含多个标题（h2/h3），则应显示目录导航组件
**Validates: Requirements 3.5**

### Property 3: 移动端AI功能可访问性
*For any* 移动端视口（宽度<768px），AI对话页面的所有核心功能（发送消息、切换助手、查看历史）应可访问
**Validates: Requirements 4.1**

### Property 4: 移动端助手选择器显示
*For any* 移动端用户点击助手切换触发器，底部抽屉应显示并包含所有可用助手
**Validates: Requirements 4.3, 5.2**

### Property 5: 助手信息完整性
*For any* 助手选择器中的助手项，应显示图标、名称和描述三个元素
**Validates: Requirements 5.4**

### Property 6: 助手切换状态更新
*For any* 用户选择新助手后，当前助手显示应更新为所选助手的图标和名称
**Validates: Requirements 5.5**

### Property 7: 对话历史抽屉显示
*For any* 移动端用户点击历史按钮，侧边抽屉应显示对话列表
**Validates: Requirements 6.2**

### Property 8: 对话列表信息完整性
*For any* 对话列表中的对话项，应显示对话标题和时间
**Validates: Requirements 6.4**

### Property 9: 响应式布局切换
*For any* 屏幕宽度变化，当宽度小于768px时，页面应自动切换到移动端布局
**Validates: Requirements 7.2**

### Property 10: 触摸目标尺寸
*For any* 可交互元素（按钮、链接等），在移动端视口下其触摸目标尺寸应至少为44x44像素
**Validates: Requirements 7.3**

### Property 11: 移动端字体可读性
*For any* 移动端视口下的文本内容，字体大小应不小于14px
**Validates: Requirements 7.4**

## Error Handling

### 1. 动画性能降级
```javascript
// 检测设备性能，低端设备禁用复杂动画
if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.body.classList.add('reduce-motion');
}
```

### 2. 毛玻璃效果降级
```css
/* 不支持backdrop-filter的浏览器降级 */
@supports not (backdrop-filter: blur(10px)) {
    .glass-effect {
        background: var(--bg-secondary);
        opacity: 0.95;
    }
}
```

### 3. 触摸手势失败处理
```javascript
// 触摸手势失败时提供备用关闭方式
drawer.addEventListener('touchend', () => {
    // 如果滑动手势未触发关闭，显示关闭按钮
    if (!gestureHandled) {
        showCloseButton();
    }
});
```

### 4. 视口变化处理
```javascript
// 监听视口变化，动态调整布局
const mediaQuery = window.matchMedia('(max-width: 768px)');
mediaQuery.addEventListener('change', (e) => {
    if (e.matches) {
        switchToMobileLayout();
    } else {
        switchToDesktopLayout();
    }
});
```

## Testing Strategy

### 单元测试
- 测试视图切换逻辑
- 测试抽屉组件的打开/关闭状态
- 测试助手切换功能
- 测试响应式断点检测

### 属性测试
- 使用 Playwright 或 Cypress 进行端到端测试
- 测试不同视口尺寸下的布局正确性
- 测试触摸目标尺寸
- 测试交互元素的可访问性

### 视觉回归测试
- 使用 Percy 或 Chromatic 进行视觉回归测试
- 对比不同主题（浅色/深色）下的视觉效果
- 对比不同设备尺寸下的布局

### 性能测试
- 使用 Lighthouse 测试页面性能
- 确保动画不造成帧率下降
- 测试首屏加载时间

### 手动测试
- 在真实移动设备上测试触摸交互
- 测试键盘弹出时的布局调整
- 验证视觉效果的"高端感"
