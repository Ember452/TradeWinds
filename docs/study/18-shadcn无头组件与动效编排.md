# 18 · shadcn 无头组件与 framer-motion 动效编排

## 这个知识点是什么

**无头组件(headless component)**是把"行为"与"外观"拆开的组件形态:行为部分(焦点管理、键盘导航、Escape 关闭弹窗、aria 属性)由底层库(Radix UI)保证,外观完全由使用者决定。shadcn/ui 的做法更进一步:它不是 npm 依赖,而是把组件**源码生成到你的仓库里**,你可以随意改样式、删功能——组件是你的代码,不是黑盒。**framer-motion** 则是声明式动画库:用 `animate`/`whileInView` 等属性描述目标状态,库负责插值、时序、中断衔接,还能用 `useReducedMotion` 感知系统的"减弱动效"偏好。

类比:Radix 像一台装好发动机和气囊的裸车(sham),shadcn 帮你开模了车身(源码进仓库),framer-motion 是让车动起来的传动系统。

## TradeWinds 为什么需要它

产品级前端的差距主要在交互细节:确认删除要有确认弹窗且焦点不被困住、下拉菜单要支持键盘操作、Toast 要有序堆叠不重叠——这些自己手写每一个都是几百行且容易漏无障碍。宣传页的"华丽"则依赖动效编排:纸飞机公转+自转抵消、云朵视差、滚动浮现,手写 requestAnimationFrame 的成本与出错率都高。两者都属"高频重复问题,业界已有最优解"。

## 本项目怎么实现的

**基础组件层**(`frontend/src/components/ui/`):经 shadcn CLI 生成 button/card/dialog/tabs/dropdown-menu/tooltip/popover/alert-dialog/skeleton 等 15 个组件的源码,统一使用第 17 篇的语义 token。业务侧只 import 这一层,不直接触 Radix API。全局反馈用 sonner 的 Toast(`<Toaster>` 挂 App 根部,任意组件 `toast.success(...)`),它的主题读自本项目的 `useTheme` 而非默认的 next-themes(减少一套主题状态源)。

**动效编排**以宣传页 `Hero.tsx` 的纸飞机为例,一个"公转不换头"用嵌套动画实现:

```tsx
<motion.div  // 外层:绕轨道公转
  animate={{ rotate: [0, 360] }}
  transition={{ duration: 8, repeat: Infinity, ease: "linear" }}>
  <motion.svg  // 内层:反向自转抵消,机头朝向不变
    style={{ x: radius / 2, y: -size / 2 }}   // 半径偏移 = 轨道
    animate={{ rotate: [0, -360] }}
    transition={{ duration: 8, repeat: Infinity, ease: "linear" }} />
</motion.div>
```

滚动叙事用 `whileInView` + `viewport={{ once: true, margin: "-80px" }}`(进入视口才播,播过不重播),步骤间用 `delay: i * 0.15` 编排节奏。**所有动效组件都调 `useReducedMotion()`,为真时不注入动画属性**——配合全局 CSS 的 `prefers-reduced-motion` 兜底,尊重系统偏好。

反馈闭环模式:写操作(创建/退订/删除/分享)统一"AlertDialog 确认 → 执行 → `toast.success/error` 结果",定义在 `TopicHeader`/`FeedsPanel`/`CreateTopicDialog` 中,失败不打断界面。

## 踩过的坑

- **lucide-react 新版移除品牌图标**:`Github` 图标在 v1.x 已删除,编译期 TS 报错才发现。改用语义近似的 `GitBranch`(GitHub 源)和纯文字链接(页脚)。教训:图标这类"看起来肯定有"的资产,引用前确认当前版本导出。
- **会话列表跳转误用 history API**:最初用 `window.history.pushState` + 手动派发 PopStateEvent 绕过 react-router,行为怪异;改回 `useNavigate()` 一行解决。教训:在 react-router 项目里绝不要绕过它的导航 API。
- **无限滚动的 IntersectionObserver 依赖数组**:哨兵 effect 依赖 `hasMore/loading/cursor/loadPage`,漏掉 `cursor` 会在翻一页后停止加载;这是旧代码遗留的正确写法,重构时原样保留并补了注释,验证走查确认翻页正常。

## 延伸阅读

- shadcn/ui:组件即代码的理念与 CLI(https://ui.shadcn.com/docs)
- Radix UI Primitives:可访问性行为清单(https://www.radix-ui.com/primitives)
- framer-motion 文档:animations 与 useReducedMotion(https://motion.dev/docs/react-animation)
- MDN:prefers-reduced-motion(https://developer.mozilla.org/docs/Web/CSS/@media/prefers-reduced-motion)
