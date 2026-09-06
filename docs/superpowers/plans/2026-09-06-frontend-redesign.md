# 前端产品化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TradeWinds React 前端从 MVP 级重构为成熟产品级:华丽动漫风宣传页(新海诚晴空)、六界面全面重构、亮暗双主题、完整交互反馈闭环。

**Architecture:** 保留 Vite + React 19 骨架与 `api.ts`/`auth.tsx` 认证逻辑;新建 `src/components/ui/`(shadcn/ui 源码)与语义 token 双主题体系(`.dark` class),`src/features/` 下页面全部重写。后端契约零改动。

**Tech Stack:** Tailwind CSS v4 + shadcn/ui(radix-ui 原语)+ framer-motion + lucide-react + sonner(Toast)

**Spec:** [docs/superpowers/specs/2026-09-06-frontend-redesign-design.md](../specs/2026-09-06-frontend-redesign-design.md) —— 本计划从 spec 出发,执行者两份都要读。

## Global Constraints(每个 Task 隐含遵守)

- 后端 API 契约零改动;`src/shared/api.ts`、`src/shared/auth.tsx` 的对外行为不变(允许文件内微调注释)
- 路径别名 `@/` 指向 `src/`;shadcn/ui 组件源码入 `src/components/ui/`,必须可改(不当作黑盒)
- 双主题:语义 token 定义于 `src/index.css`(CSS 变量),浅色=晴空、深色=星夜;所有新组件只用语义色,禁止硬编码 hex(宣传页 hero 插画层除外,集中在一处)
- 动效必须响应 `prefers-reduced-motion: reduce`(降级为静态/直接到达终态)
- 中文文案;评分徽章三档:≥8 强调(琥珀)、≥6 中性(蓝)、其余弱化(灰)
- 每个 Task 结束:`npm run lint` + `npx tsc --noEmit` + `npm run build` 三条全绿;运行时走查用 `node mock-server.mjs`(8000 端口)+ `npm run dev`(5173)
- 提交按 AGENTS.md 第 8 节 Conventional Commits,一 Task 一提交(含当日 study 文档的提交除外,收尾 Task 统一处理)
- 开发验证环境:mock 服务器任意凭据可登录,预置 2 主题/12 条目/1 报告/1 会话(见 `frontend/mock-server.mjs`)

---

### Task 1: Tailwind v4 接入与双主题 token 基建

**Files:**
- Modify: `frontend/package.json`(新增 devDependencies: `tailwindcss@^4`、`@tailwindcss/vite@^4`;dependencies: `framer-motion`、`lucide-react`、`sonner`)
- Modify: `frontend/vite.config.ts`(加 `tailwindcss()` 插件与 `@` 别名)
- Modify: `frontend/tsconfig.json`(加 `"paths": {"@/*": ["./src/*"]}`)
- Create: `frontend/src/index.css`(全量重写:tailwind 引入 + 语义 token + 双主题)
- Create: `frontend/src/shared/theme.tsx`(ThemeProvider + useTheme)
- Modify: `frontend/src/main.tsx`(挂 ThemeProvider)
- Modify: `frontend/src/App.tsx`、`frontend/src/features/*`:仅把旧 `styles.css` import 移除,类名暂不重构(后续 Task 处理)

**Interfaces (Produces):**
- `useTheme(): { theme: "light" | "dark"; setTheme(t): void; toggle(): void }`——初始读 localStorage `tradewinds_theme`,缺省跟随 `prefers-color-scheme`;切换时在 `document.documentElement` 上增删 `.dark` class 并写 localStorage
- 语义 token 名称(后续所有 Task 引用):`background / surface / surface-strong / border / primary / primary-foreground / accent / accent-foreground / muted / muted-foreground / success / warning / danger / sky-1 / sky-2 / sky-3`(sky-* 为 hero 天空渐变三档)

- [ ] **Step 1: 安装依赖**

```bash
cd frontend
npm install -D tailwindcss @tailwindcss/vite
npm install framer-motion lucide-react sonner
```

- [ ] **Step 2: vite/tsconfig 配置别名与插件**

```ts
// vite.config.ts
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
```

`tsconfig.json` compilerOptions 增加:`"baseUrl": ".", "paths": { "@/*": ["./src/*"] }`。

- [ ] **Step 3: 编写 token 体系(src/index.css 全量替换)**

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@theme inline {
  --color-background: var(--c-background);
  --color-surface: var(--c-surface);
  --color-surface-strong: var(--c-surface-strong);
  --color-border-soft: var(--c-border);
  --color-primary: var(--c-primary);
  --color-primary-foreground: var(--c-primary-fg);
  --color-accent: var(--c-accent);
  --color-accent-foreground: var(--c-accent-fg);
  --color-muted: var(--c-muted);
  --color-muted-foreground: var(--c-muted-fg);
  --color-success: var(--c-success);
  --color-warning: var(--c-warning);
  --color-danger: var(--c-danger);
  --color-sky-1: var(--c-sky-1);
  --color-sky-2: var(--c-sky-2);
  --color-sky-3: var(--c-sky-3);
}

:root {
  /* 晴空(浅色) */
  --c-background: #eef5fc;  --c-surface: #ffffff;  --c-surface-strong: #f7fafd;
  --c-border: #dbe5f0;
  --c-primary: #2a5ca8;     --c-primary-fg: #ffffff;
  --c-accent: #e8590c;      --c-accent-fg: #ffffff;
  --c-muted: #e8eef6;       --c-muted-fg: #5b6b80;
  --c-success: #2f9e44; --c-warning: #b0741a; --c-danger: #c92a2a;
  --c-sky-1: #3d7fd9; --c-sky-2: #7fb5ec; --c-sky-3: #fdf2dd;
}

.dark {
  /* 星夜(深色) */
  --c-background: #0b1026;  --c-surface: #131b38;  --c-surface-strong: #1a2450;
  --c-border: #26325c;
  --c-primary: #7c9bff;     --c-primary-fg: #0b1026;
  --c-accent: #fca311;      --c-accent-fg: #0b1026;
  --c-muted: #1c2749;       --c-muted-fg: #9db0d0;
  --c-success: #51cf66; --c-warning: #ffc078; --c-danger: #ff6b6b;
  --c-sky-1: #0b1026; --c-sky-2: #1a2450; --c-sky-3: #2c3a70;
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--c-background);
  color: var(--c-primary-fg);
}
.dark body { color: #dfe7ff; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

- [ ] **Step 4: ThemeProvider(src/shared/theme.tsx)**

```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";
const STORAGE_KEY = "tradewinds_theme";

function initialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

const ThemeContext = createContext<{ theme: Theme; setTheme: (t: Theme) => void; toggle: () => void } | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);
  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  const toggle = useCallback(() => setThemeState((t) => (t === "dark" ? "light" : "dark")), []);
  return <ThemeContext.Provider value={{ theme, setTheme, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme 必须在 ThemeProvider 内使用");
  return value;
}
```

`main.tsx` 在 `<AuthProvider>` 外再包一层 `<ThemeProvider>`。

- [ ] **Step 5: 三命令验证**

Run: `npm run lint && npx tsc --noEmit && npm run build`
Expected: 全绿(旧页面样式此时会"裸奔",属预期,后续 Task 重写)

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/tsconfig.json frontend/src/index.css frontend/src/shared/theme.tsx frontend/src/main.tsx
git commit -m "feat(frontend): Tailwind v4 接入与晴空/星夜双主题 token 体系"
```

---

### Task 2: shadcn/ui 初始化与基础组件集

**Files:**
- Create: `frontend/components.json`(shadcn CLI 配置,style: "new-york",rsc: false,tsx: true,alias 前缀 `@/`)
- Create: `frontend/src/components/ui/`:button、card、dialog、alert-dialog、tabs、dropdown-menu、tooltip、popover、badge、skeleton、input、textarea、label、separator(经 CLI 生成后按需微调)
- Create: `frontend/src/components/ui/sonner.tsx`(Toaster 封装,挂 App 顶层)

**Interfaces (Produces):** 后续 Task 以 `@/components/ui/*` 引用上述组件;Toast 统一用 `sonner` 的 `toast.success()/toast.error()`,`<Toaster richColors position="top-center" />` 挂在 App.tsx 根部。

- [ ] **Step 1: CLI 初始化与组件生成**

```bash
cd frontend
npx shadcn@latest init        # 选 neutral 基色、css variables 模式;若询问 Tailwind config 指向 src/index.css
npx shadcn@latest add button card dialog alert-dialog tabs dropdown-menu tooltip popover badge skeleton input textarea label separator sonner
```

- [ ] **Step 2: 对齐语义 token**

把生成组件里 shadcn 默认的 `bg-background`、`text-foreground`、`border-input` 等类保持原样(tailwind 默认 token 已被 `@theme inline` 桥接);逐一检查 `button.tsx`、`badge.tsx`、`dialog.tsx` 中出现的写死色(如 `bg-primary text-primary-foreground`)在本项目 token 下显示正常——shadcn 的语义名与我们的 token 名在 Tailwind v4 下需在 `@theme inline` 中补齐映射(`--color-primary-foreground` 已定义,缺的映射在此步补)。

- [ ] **Step 3: Toaster 挂载 + 冒烟页面**

`App.tsx` 根部加 `<Toaster richColors position="top-center" />`;临时在任意已挂载组件放一个 `toast.success("冒烟")` 按钮验证后删除。

- [ ] **Step 4: 三命令验证**

Run: `npm run lint && npx tsc --noEmit && npm run build`
Expected: 全绿

- [ ] **Step 5: Commit**

```bash
git add frontend/components.json frontend/src/components/ui frontend/src/App.tsx frontend/package.json frontend/package-lock.json frontend/src/index.css
git commit -m "feat(frontend): shadcn/ui 基础组件集与全局 Toast"
```

---

### Task 3: 路由重构与 AppShell

**Files:**
- Modify: `frontend/src/App.tsx`(路由表重排)
- Create: `frontend/src/shared/AppShell.tsx`(替代现 Layout:玻璃拟态 sticky 顶栏 + 主题切换 + 用户下拉菜单)
- Create: `frontend/src/shared/PageTransition.tsx`(framer-motion 淡入上移包裹 `<Outlet/>`)
- Delete: `frontend/src/shared/Layout.tsx`(职责被 AppShell 取代)
- Create: `frontend/src/features/landing/LandingPage.tsx`(本 Task 仅占位:`<h1>TradeWinds</h1>` + "建设中",Task 4 重写)
- Modify: `frontend/src/features/topics/TopicsPage.tsx` 等六页:路径引用从 `./shared/` 改 `@/shared/`(仅 import 调整,内容后续 Task 重写)

**Interfaces (Produces):**
- 路由表:`/`(未登录→Landing,已登录→`<Navigate to="/topics"/>`)、`/login`、`/register`、`/share/reports/:token` 公开;`/topics`、`/topics/:id`、`/chat`、`/chat/:id` 在 RequireAuth 下
- `AppShell`:顶栏含品牌(⛵ TradeWinds → /topics)、NavLink(主题/对话研究)、`Sun`/`Moon` 图标主题切换按钮(useTheme.toggle)、DropdownMenu(用户邮箱 + 登出,登出后 `navigate("/login")`)

- [ ] **Step 1: 路由表重写(App.tsx)**

```tsx
export default function App() {
  return (
    <ThemeProvider>
      <Toaster richColors position="top-center" />
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingGate />} />
            <Route path="/login" element={<AuthForm mode="login" />} />
            <Route path="/register" element={<AuthForm mode="register" />} />
            <Route path="/share/reports/:token" element={<SharedReportPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<AppShell />}>
                <Route path="/topics" element={<TopicsPage />} />
                <Route path="/topics/:topicId" element={<TopicDetailPage />} />
                <Route path="/chat" element={<ChatListPage />} />
                <Route path="/chat/:conversationId" element={<ChatPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

function LandingGate() {
  const { user, loading } = useAuth();
  if (loading) return <p className="loading">加载中…</p>;
  if (user) return <Navigate to="/topics" replace />;
  return <LandingPage />;
}
```

- [ ] **Step 2: AppShell(src/shared/AppShell.tsx)**

顶栏:`sticky top-0 z-40 backdrop-blur-md bg-surface/80 border-b border-border-soft`;内容 `<main className="mx-auto max-w-5xl px-4 pb-24 pt-8"><PageTransition><Outlet/></PageTransition></main>`。导航用 NavLink 的 `className={({isActive}) => isActive ? "text-primary font-semibold" : "text-muted-foreground hover:text-foreground"}`。主题切换按钮按 `theme` 渲染 `Sun`/`Moon`(lucide)。

- [ ] **Step 3: PageTransition**

```tsx
import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: "easeOut" }}>
      {children}
    </motion.div>
  );
}
```

- [ ] **Step 4: 运行时走查**

起 mock + dev:未登录访问 `/` 见 Landing 占位;登录后自动落 `/topics`;顶栏主题切换在亮暗间生效且刷新后记忆;`/login`、`/share/reports/mock-share-token` 公开可达;旧页面(暂未重构)在无旧 styles.css 下仍可操作。

- [ ] **Step 5: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src/App.tsx frontend/src/shared/AppShell.tsx frontend/src/shared/PageTransition.tsx frontend/src/features/landing/LandingPage.tsx frontend/src/features
git rm frontend/src/shared/Layout.tsx
git commit -m "feat(frontend): 路由重构、AppShell 与主题切换"
```

---

### Task 4: Landing 宣传页(重点交付)

**Files:**
- Create: `frontend/src/features/landing/LandingPage.tsx`(页面组装)
- Create: `frontend/src/features/landing/components/Hero.tsx`(天空场景 + 纸飞机动效)
- Create: `frontend/src/features/landing/components/PipelineSection.tsx`(三步管道滚动叙事)
- Create: `frontend/src/features/landing/components/FeatureGrid.tsx`(六特性卡片)
- Create: `frontend/src/features/landing/components/ReportShowcase.tsx`(样例报告展示)
- Create: `frontend/src/features/landing/components/SiteFooter.tsx`
- Replace: `frontend/src/index.html` 的 `<title>` 与 favicon(内联 SVG 纸飞机 data URL)

**Interfaces (Consumes):** 路由占位(已存在);`Link`(react-router)指向 `/register`、`/login`、`/share/reports/mock-share-token`。

**设计规格(实现者按此执行,色值用 token):**

- **Hero**:`min-h-[92vh]`,背景 `linear-gradient(180deg, var(--c-sky-1), var(--c-sky-2) 55%, var(--c-sky-3) 100%)` + 顶部径向暖光斑(radial-gradient,`pointer-events-none`)。中央动效组(framer-motion):
  - 核心:`⛵` 徽标置于 96px 圆角容器(玻璃拟态:`bg-white/15 backdrop-blur border-white/30`),`animate` 呼吸浮动(y: [0,-8,0], 4s 循环)
  - 纸飞机:SVG 白色带描边(路径 `M2 12 L22 3 L15 21 L11 14 Z`),沿 220px 半径虚线圆轨道盘旋——外层 `motion.div` `rotate: 360` 8s linear infinite,内层反向 `rotate: -360` 抵消自转,加 `drop-shadow(0 0 12px rgba(255,255,255,.5))` 发光尾迹
  - 云朵:3 个白色圆角长条 div,`x: ["-10vw","110vw"]` 不同时长(18s/26s/34s)线性循环,`blur-sm opacity-80`
  - 文案:主标题"让纸飞机替你飞遍技术的天空"(36-48px,font-extrabold,白字带轻投影);副标题"订阅主题 · 多源检索 · AI 评分聚类 · 每日情报送达";CTA 双按钮:实心"免费开始"(→/register,accent 色)、描边"查看示例报告"(→ 公开分享页)
  - 滚动提示:底部居中 `ChevronDown` 上下浮动
- **PipelineSection**:三步卡片(订阅主题 → 多源检索 AI 评分 → 简报送达),`whileInView` 依次浮现(`viewport={{ once: true, margin: "-80px" }}`,`transition.delay: i * 0.15`);步与步之间虚线连接线
- **FeatureGrid**:2×3 卡片(MultipleSource 聚合 / 评分与聚类 / 周期报告 / 对话研究 / 已读检索 / 偏好记忆),图标 lucide:`Rss`、`Gauge`、`Mail`、`MessageCircle`、`Search`、`Brain`
- **ReportShowcase**:左侧文案"每周一封,把一周噪音压缩成一页精华",右侧一张静态报告卡片(标题/区间/条数/摘要三行),底部"阅读公开示例"链接
- **SiteFooter**:深色条(`bg-surface-strong`),"TradeWinds — AI 驱动的技术情报管道 · 面试演示项目",GitHub 图标占位链接

- [ ] **Step 1: 实现五个子组件(按上述规格,动效一律 framer-motion + 尊重 prefers-reduced-motion)**
- [ ] **Step 2: 组装 LandingPage 并替换占位**
- [ ] **Step 3: 运行时走查(双主题)**

亮/暗主题下 hero 天空分别呈"晴空/星夜"氛围;`prefers-reduced-motion: reduce` 时(DevTools Rendering 面板模拟)纸飞机静止但页面完整可读;CTA 跳转正确。

- [ ] **Step 4: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src/features/landing frontend/index.html
git commit -m "feat(frontend): 新海诚晴空宣传页与纸飞机动效"
```

---

### Task 5: 认证页重构(晴空背景 + 演示账号)

**Files:**
- Modify: `frontend/src/features/auth/AuthForm.tsx`(全量重写)

**规格:** 左右双栏(移动端上下堆叠):左侧为 hero 同款天空插画层(纸飞机 + 云朵,静态或轻动效)+ 一句产品文案;右侧 `Card` 表单(邮箱/密码/提交/切换注册链接)。表单下方 `Button variant="ghost"` "一键填充演示账号"——点击填入 `demo@tradewinds.local / demo12345` 并 `toast.info("已填充,点击登录即可")`。错误提示沿用现有 ApiError 逻辑展示在表单内。

- [ ] **Step 1: 重写 AuthForm(保留 useAuth 的 login/register 调用与错误处理逻辑不变)**
- [ ] **Step 2: 运行时走查**:演示账号一键填充→登录→落 /topics;错误密码显示后端(mock)错误文案;亮暗双主题检查
- [ ] **Step 3: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src/features/auth/AuthForm.tsx
git commit -m "feat(frontend): 认证页重构与演示账号一键填充"
```

---

### Task 6: 主题列表页(卡片网格 + 创建对话框)

**Files:**
- Modify: `frontend/src/features/topics/TopicsPage.tsx`(全量重写)
- Create: `frontend/src/features/topics/components/CreateTopicDialog.tsx`
- Create: `frontend/src/features/topics/components/PlanPreview.tsx`(从旧 TopicsPage 抽出,重设计)
- Create: `frontend/src/shared/EmptyState.tsx`(通用空状态:插图 emoji 圆底 + 标题 + 描述 + 行动按钮)

**Interfaces (Produces):**
- `PlanPreview({ plan }: { plan: Record<string, unknown> | null })`——TopicDetailPage 复用
- `EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description: string; action?: ReactNode })`
- `CreateTopicDialog({ open, onOpenChange, onCreated })`——两步:Step1 表单(名称/描述/频率)→ 调 `POST /api/v1/topics` → Step2 展示返回的 plan 预览 + "完成"按钮;成功 `toast.success("主题已创建")`;失败 toast.error(err.message)

**规格:** 页头"我的主题" + 主按钮"新建主题"(打开 Dialog);主题卡片 `Card` 网格(`grid gap-4 md:grid-cols-2`),含:名称、`Badge`(每天/每周)、`Badge variant=secondary`(订阅中/已退订)、描述两行截断、右下"查看"箭头;加载时 3 张 `Skeleton`;空状态用 EmptyState(`Inbox` 图标,"还没有主题","创建第一个订阅,让情报开始飞","新建主题"按钮)。

- [ ] **Step 1: 实现三个组件与页面重写**
- [ ] **Step 2: 运行时走查**:mock 下两主题卡片;创建两步流程(含计划预览);空状态(临时过滤数组模拟);Toast 成功/失败;双主题
- [ ] **Step 3: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src/features/topics frontend/src/shared/EmptyState.tsx
git commit -m "feat(frontend): 主题列表重构与两步创建对话框"
```

---

### Task 7: 主题详情页(Tabs 三分区 + Feed 重构)

**Files:**
- Modify: `frontend/src/features/topics/TopicDetailPage.tsx`(全量重写,拆出四个子组件文件)
- Create: `frontend/src/features/topics/components/FeedPanel.tsx`
- Create: `frontend/src/features/topics/components/ReportsPanel.tsx`
- Create: `frontend/src/features/topics/components/FeedsPanel.tsx`(自定义订阅源)
- Create: `frontend/src/shared/ScoreBadge.tsx`、`frontend/src/shared/SourceIcon.tsx`
- Create: `frontend/src/features/topics/components/TopicHeader.tsx`(标题/元信息/操作区/编辑表单)

**Interfaces (Produces):**
- `ScoreBadge({ score }: { score: number | null })`:null 不渲染;≥8 `bg-accent/15 text-accent border-accent/30`、≥6 `bg-primary/10 text-primary border-primary/30`、其余 `bg-muted text-muted-foreground border-border-soft`
- `SourceIcon({ source }: { source: string })`:arxiv→`FileText`、hackernews→`Flame`、github→`Github`、rss→`Rss`,未知→`Globe`;附 `title` 原文

**规格:**
- TopicHeader:`Button` 立即执行(执行中 Loader2 旋转)/ 退订(`AlertDialog` 确认,成功后 `toast.success`)/ 编辑描述频率(inline Card 表单,PATCH 后 `toast.success("已保存,计划已重新编译")`);执行结果行(检索/新增/采纳/拒绝计数)用 muted 小字
- Tabs:`<Tabs defaultValue="feed">`,三个 `TabsTrigger`:信息流 / 周期报告 / 订阅源
- FeedPanel:筛选(全部/6+/8+,`Select` 或原生 select)+ 无限滚动(保留 IntersectionObserver + 游标逻辑);条目 `Card`:首行 SourceIcon + 标题(外链,点击保留 fire-and-forget click 上报)+ ScoreBadge;次行 muted(来源名 · 发布日期 `toLocaleDateString`);summary 正文;reason 用左侧 accent 竖线引用样式;首屏加载 4 张 Skeleton;空态 EmptyState("暂无内容","执行一次主题,让第一批情报飞进来")
- ReportsPanel:报告行(类型徽章 日报/周报 · 起止日期 · N 条)+ 两个操作:查看(Dialog 内 `<pre>` 正文,同公开分享页样式)/ 生成分享链接(POST 后展示可复制链接,`toast.success("分享链接已生成")`)
- FeedsPanel:添加表单 + 列表(healthy/broken 状态点:success/danger 圆点 + 文字),删除经 AlertDialog 确认

- [ ] **Step 1: 实现五个子组件与页面组装**
- [ ] **Step 2: 运行时走查**:mock 数据下三分区全部可用;评分徽章三档配色(9.2/7.4/5.5 各一档);无限滚动翻页(min_score 筛选变化时重置);报告查看与分享;删除确认;双主题
- [ ] **Step 3: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src/features/topics frontend/src/shared/ScoreBadge.tsx frontend/src/shared/SourceIcon.tsx
git commit -m "feat(frontend): 主题详情 Tabs 重构与 Feed 视觉升级"
```

---

### Task 8: 对话页(流式体验完整化)

**Files:**
- Modify: `frontend/src/features/chat/ChatListPage.tsx`(重写:卡片列表 + 新建)
- Modify: `frontend/src/features/chat/ChatPage.tsx`(重写,拆出两个子组件)
- Create: `frontend/src/features/chat/components/ChatMessage.tsx`(气泡 + 引用区)
- Create: `frontend/src/features/chat/components/CitationText.tsx`(从旧 Markdownish 迁移升级:[n] → 触发 Popover 的引用上标)
- Create: `frontend/src/features/chat/components/useAutoScroll.ts`(新消息/流式增量时滚底)

**Interfaces (Produces):**
- `CitationText({ text, citations }: { text: string; citations: { index: number; url: string }[] | null })`——`[n]` 渲染为 `Popover` 触发的橙色上标(悬浮显示 URL 首段,点击新标签打开原文);无 citations 时纯文本
- `useAutoScroll(deps: unknown[]): { containerRef: RefObject<HTMLDivElement>; scrollToBottom(): void }`——内容变化时若用户未主动上滚(距底 > 120px 视为主动上滚,不强制拉回),平滑滚到底

**规格:**
- ChatListPage:会话卡片列表(标题 + 时间)+ 顶部新建表单(Enter 提交);空态 EmptyState
- ChatPage:消息区 `ref={containerRef}` 可滚动容器;用户气泡右对齐(`bg-primary text-primary-foreground`)、助手左对齐(`bg-surface border`);流式中最后一条助手消息尾部显示三点跳动 typing 指示(三个 span,framer-motion `opacity` 交错);输入区 `Textarea`(1-4 行自适应,`rows=1`,Enter 发送 / Shift+Enter 换行)+ 发送按钮;流式期间输入 disabled + 按钮"停止"(`AbortController` 已有 signal 传给 streamSSE,点击 abort);interrupted 时保留现有 retry-hint 交互但样式升级(红条 + 重新提问按钮);citations 事件先行的顺序逻辑保持不变
- 消息区高度:`h-[calc(100vh-220px)] overflow-y-auto`,输入区 sticky 底部

- [ ] **Step 1: 实现三个子组件与两页重写**
- [ ] **Step 2: 运行时走查**:mock SSE 逐字输出 + typing 指示 + 自动滚底;引用上标 Popover 悬浮与跳转;停止按钮中断流(已生成内容保留);上滚阅读历史时不被拉回;双主题
- [ ] **Step 3: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src/features/chat
git commit -m "feat(frontend): 对话页流式体验与引用悬浮升级"
```

---

### Task 9: 公开分享页重构 + 全局收尾打磨

**Files:**
- Modify: `frontend/src/features/reports/SharedReportPage.tsx`(重写:晴空 header 条 + 卡片化正文 + "由 TradeWinds 生成"页脚链接)
- Modify: `frontend/src/styles.css`(删除——旧样式残留清零,确认无 import)
- Create: `frontend/src/shared/LoadingScreen.tsx`(全页加载态:Landing 同款天空渐变 + 纸飞机轻浮动,替换 RequireAuth/AuthProvider 的"加载中…"文字)
- Modify: `frontend/src/shared/RequireAuth.tsx`(loading 分支换用 LoadingScreen)

- [ ] **Step 1: 实现分享页与 LoadingScreen,清理 styles.css**
- [ ] **Step 2: 全局走查清单(双主题逐页)**:`/`(宣传页完整叙事)→ 注册/登录(含演示填充)→ 主题列表/创建 → 详情三分区 → 对话流式 → 分享页;`/api` 未知路径 404 行为不受前端影响;移动端宽度(DevTools 375px)逐页不破版
- [ ] **Step 3: 三命令验证 + Commit**

```bash
npm run lint && npx tsc --noEmit && npm run build
git add frontend/src
git rm frontend/src/styles.css
git commit -m "feat(frontend): 分享页重构、全局加载态与样式收尾"
```

---

### Task 10: 验收、文档同步与学习文档

**Files:**
- Modify: `docs/design.md`、`docs/architecture.md`(前端节:技术栈补 Tailwind/shadcn/framer-motion,路由与双主题描述)
- Modify: `frontend/README.md` 或 README.md 前端段(启动方式不变,补双主题/宣传页说明)
- Create: `docs/study/17-Tailwind-v4-主题token与双主题.md`
- Create: `docs/study/18-shadcn-无头组件与Toast反馈闭环.md`(标题按实际内容定,遵循 AGENTS.md 第 10 节五段结构)

- [ ] **Step 1: 全量验证**:`npm run lint && npx tsc --noEmit && npm run build`;CI frontend job 触发确认(push 或 PR)
- [ ] **Step 2: 文档同步**:核对 spec §7 承诺逐项勾掉;design.md/architecture.md 与实现一致处更新
- [ ] **Step 3: study 文档两篇(真实踩坑记录,不编造)**
- [ ] **Step 4: Commit**

```bash
git add docs README.md
git commit -m "docs(frontend): 前端重构文档同步与学习文档"
```

---

## 里程碑对照

| Task | 交付物 | 验证 |
|---|---|---|
| 1 | token 双主题基建 | 三命令 + 主题切换生效 |
| 2 | shadcn 组件集 | 三命令 + Toast 冒烟 |
| 3 | 路由 + AppShell | 运行时走查路由矩阵 |
| 4 | Landing 宣传页 | 双主题动效走查 |
| 5 | 认证页 | 演示账号填充走查 |
| 6 | 主题列表 | 创建两步流程走查 |
| 7 | 主题详情 | 三分区 + 徽章配色走查 |
| 8 | 对话页 | 流式 + 引用 + 停止走查 |
| 9 | 分享页 + 收尾 | 全局双主题清单 |
| 10 | 文档与验收 | CI + 文档一致性 |

---

## 实施记录(2026-09-06,feat/frontend-redesign 分支)

- Task 1-9 全部交付,每 Task 一提交(lint/tsc/build 全绿后提交);Task 10 为文档同步与学习文档(17/18 两篇)。
- 偏差:shadcn CLI 在 Windows 下未解析 `@/` 别名,错误安装了 `cn`/`next-themes` 包并生成错误 import——手动修复为 `@/lib/utils` 并卸载垃圾依赖;`sonner.tsx` 包装改为读取本项目 `useTheme`(替代 next-themes)。
- 偏差:lucide-react 新版无 `Github`/`Boat` 图标——GitHub 来源用 `GitBranch`,顶栏品牌用 `Sailboat`,页脚链接改纯文字。
- 偏差:`ChatListPage` 拆为独立文件(计划写的是同文件内两导出);旧页面相对 import 未做无谓的别名 churn,随各 Task 重写时统一为 `@/`。
- 新增共享组件:`ScoreBadge`(三档配色)、`SourceIcon`、`EmptyState`、`LoadingScreen`、`PageTransition`、`useAutoScroll`(用户上滚时不强制拉回)。
- 会话页新增"停止生成"按钮(AbortController,spec 未明确但属流式体验标配)。
