# TradeWinds 前端产品化重构 — 设计文档

日期:2026-09-06 · 状态:已与需求方逐节确认

## 1. 背景与目标

项目定位为面试可演示的作品集项目(design.md v0.3),现有前端为 MVP 级:无设计体系、无宣传页、交互反馈缺失。本次将其重构为成熟产品级前端:

- 新增华丽首页宣传页(未登录首页),动漫"新海诚晴空"视觉方向,纸飞机动效作为品牌记忆点
- 应用内六个界面全部重构,交互反馈闭环(Toast/确认/骨架屏/空状态)
- 亮暗双主题(浅色"晴空" / 深色"星夜"),跟随系统 + 手动切换
- **后端 API 契约零改动**;FastAPI 静态托管的 SPA 部署模型不变

非目标:不引入 SSR/元框架;不新增前端单测框架;不做移动端原生适配优化之外的响应式重构。

## 2. 技术栈与依赖

保留:Vite + React 19 + TypeScript + react-router 7;`src/shared/api.ts`(JWT 注入、401 统一处理、SSE 帧解析)与 `src/shared/auth.tsx` 的认证状态逻辑不动。

新增依赖(理由按 AGENTS.md 第 7 节):

| 依赖 | 用途 | 理由 |
|---|---|---|
| `tailwindcss@^4` + `@tailwindcss/vite` | 设计 token 与样式载体 | 构建期工具,无运行时体积;原子类保证多页面视觉一致性 |
| shadcn/ui(CLI 生成组件源码入 `src/components/ui/`) | 弹窗/Tab/Toast/确认框等 | 组件源码进仓库可定制;底层 radix-ui 无头原语交互与无障碍达标 |
| `framer-motion` | hero 动效、滚动叙事、页面过渡 | 宣传页 scroll-driven 动画的核心依赖 |
| `lucide-react` | 图标 | tree-shaking,按需打包 |

## 3. 双主题体系

- CSS 变量定义语义 token(背景/表面/主色/强调/成功/警告/危险/文字层级),`.dark` class 切换,Tailwind v4 `@theme` 映射
- 浅色 = **新海诚晴空**:高饱和天蓝渐变、暖光斑、通透白表面
- 深色 = **星夜巡航**:深夜蓝紫底、星光/辉光点缀、渐变发光纸飞机
- 默认跟随 `prefers-color-scheme`,顶栏手动切换并记忆于 localStorage(`tradewinds_theme`)
- 评分徽章、来源标识、空状态插画、骨架屏均定义双主题配色

## 4. 路由结构

| 路径 | 守卫 | 页面 |
|---|---|---|
| `/` | 未登录 → Landing;已登录 → 重定向 `/topics` | 宣传页(新) |
| `/login`、`/register` | 公开 | 认证页(重构) |
| `/share/reports/:token` | 公开 | 公开分享页(重构) |
| `/topics`、`/topics/:id` | RequireAuth + AppShell | 主题列表/详情(重构) |
| `/chat`、`/chat/:id` | RequireAuth + AppShell | 对话列表/详情(重构) |

## 5. 宣传页(Landing)

单页滚动叙事,全部动效经 framer-motion 实现,`prefers-reduced-motion` 下降级为静态:

1. **Hero**:天空渐变 + 体积光斑;纸飞机(SVG)沿虚线轨道绕 ⛵ 情报核心盘旋,带发光尾迹;流云视差漂移;主标题 + 副标题 + 双 CTA(免费开始 → /register;查看示例报告 → 公开分享页)
2. **工作原理**:订阅 → 多源检索与 AI 评分 → 简报送达,三步管道随滚动依次浮现(scroll-linked)
3. **功能特性**:特性卡片网格(多源聚合/评分聚类/周期报告/对话研究/RAG 检索/偏好记忆)
4. **样例报告**:展示真实结构的内容卡片,引导至公开分享页
5. **页脚**:项目说明与 GitHub 链接位

## 6. 应用内界面

- **AppShell**:sticky 玻璃拟态顶栏(品牌/导航:主题、对话研究/主题切换按钮/用户邮箱与登出菜单);内容区最大宽度容器
- **主题列表**:卡片网格(名称/频率/状态徽章/描述);创建改为 Dialog 两步流程(填写 → Planner 计划预览确认);空状态插画引导
- **主题详情**:头部(元信息 + 立即执行/退订/编辑)与 Tabs 分区:
  - 信息流:骨架屏、来源图标(arxiv/hn/github/rss)、发布时间、评分分段配色徽章(≥8 强调 / ≥6 中性 / 其余弱化)、卡片 hover 反馈、无限滚动保留
  - 周期报告:列表 + 应用内 Dialog 查看正文 + 生成分享链接(Toast 反馈)
  - 订阅源:健康状态标识,删除经 AlertDialog 确认
- **对话**:会话列表卡片;详情页 textarea 输入(Enter 发送/Shift+Enter 换行)、自动滚动到底、流式 typing 指示动画、引用上标 Popover 悬浮预览、断线重试条保留
- **登录/注册**:动漫天空背景 + 演示账号一键填充(demo@tradewinds.local / demo12345)
- **全局**:写操作(执行/退订/添加源/创建)统一 Toast 反馈;页面切换过渡;双主题骨架屏与空状态组件

## 7. 验证与文档

- 验收门:`npm run lint`、`tsc --noEmit`、`vite build` 全绿;CI frontend job 通过
- 视觉验收:双主题逐页走查(visual companion 或截图对比)
- 后端契约零改动,现有集成测试不受影响
- 交付后按 AGENTS.md 第 9/10 节:同步 design.md / architecture.md 前端相关章节,新增 docs/study/ 学习文档(Tailwind 主题 token 与双主题、shadcn/ui 组件模式等,按实际拆分)

## 8. 实施约束

- `api.ts` / `auth.tsx` 对外行为不变;后端不得有任何改动
- 组件按 AGENTS.md 第 6 节拆分:设计系统(`src/components/ui/`)、业务组件(`src/features/<域>/components/`)、页面组装三层
- 演示数据依赖 `make seed` 的既有 fixture,前端不硬编码演示内容(宣传页静态叙事内容除外)
