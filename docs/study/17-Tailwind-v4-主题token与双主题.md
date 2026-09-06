# 17 · Tailwind v4 主题 token 与双主题

## 这个知识点是什么

设计 token 是把"颜色、间距、圆角"这些视觉决策抽象成**有语义名字的变量**(如 `--c-surface` 而不是 `#ffffff`),界面代码只引用语义名。Tailwind v4 把这件事前移进了 CSS:不再需要 `tailwind.config.js`,在 CSS 里用 `@theme` 声明 token,构建时自动生成对应的工具类(`bg-surface`、`text-muted-foreground`)。"双主题"则是同一组语义名配两套取值:浅色主题的变量写在 `:root`,深色主题的覆盖值写在 `.dark` 选择器下,切换主题只是切换 class,所有引用语义名的组件自动换装。

类比:token 像舞台剧本里的角色名("主角"),双主题是同一角色由两个演员出演(白天场/夜间场),剧本一字不改。

## TradeWinds 为什么需要它

重构前 330 行扁平 CSS 只有两三个写死的颜色,所有卡片一个样,且只支持浅色。产品化重构需要:① 多页面视觉一致(颜色/间距不能各写各的);② 晴空/星夜双主题(spec 确定的需求);③ 评分徽章等状态色需要"按语义分档"而不是散落的 hex。没有 token 体系,这三件事每一条都会变成重复劳动和漂移源。

## 本项目怎么实现的

核心在 `frontend/src/index.css`,分三层:

1. **桥接层**(`@theme inline`):把 CSS 变量映射为 Tailwind 工具类名。`inline` 修饰符让 Tailwind 直接内联变量引用而非复制值——这是双主题的关键,工具类生成的是 `background-color: var(--c-surface)`,值随 `.dark` 动态变化:

```css
@custom-variant dark (&:where(.dark, .dark *));

@theme inline {
  --color-surface: var(--c-surface);
  --color-primary: var(--c-primary);
  /* shadcn/ui 组件内部引用的语义名,桥接到同一套变量 */
  --color-popover: var(--c-surface);
  --color-destructive: var(--c-danger);
}
```

2. **取值层**:`:root { --c-surface: #ffffff; ... }`(晴空)与 `.dark { --c-surface: #131b38; ... }`(星夜),各约 17 个语义变量。

3. **切换层**(`frontend/src/shared/theme.tsx`):`ThemeProvider` 初始化时读 localStorage,缺省跟随 `prefers-color-scheme`,切换时对 `document.documentElement` 增删 `.dark` class。`useTheme()` 供组件(顶栏切换按钮、Toaster)读取当前主题。

约束:业务组件只允许使用语义工具类(`bg-surface`、`text-accent`),禁止写 hex——违反即主题切换失效。

## 踩过的坑

- **shadcn CLI 的别名解析失败**:在 Windows/Git Bash 下 `npx shadcn add` 没有正确解析 tsconfig 的 `paths` 别名,把 `cn` 当成了 npm 包名(import 写成 `import { cn } from "cn"`)并真的安装了一个叫 `cn` 的垃圾包,`clsx`/`tailwind-merge` 反而没装。修复:批量 sed 改回 `@/lib/utils`,卸载垃圾包,手动补装正确依赖。教训:CLI 生成代码后必须跑一次 `tsc --noEmit` 并抽查 import。
- **双套语义名并存**:shadcn 组件内部用 `bg-popover`、`text-destructive`、`ring-ring` 等它自己的语义类,与本项目 token 名不同。解法不是改十几份生成的组件,而是在 `@theme inline` 里把这些名字也桥接到同一批 CSS 变量——token 名单从生成的组件里 grep 得出,确保映射完备。
- **`@custom-variant dark` 必须声明**:Tailwind v4 默认 `dark:` 前缀跟随系统媒体查询,而本项目需要 class 驱动(手动切换),不声明这条,所有 `dark:` 工具类都不会响应 `.dark` class。

## 延伸阅读

- Tailwind CSS v4 官方文档:theme variables(https://tailwindcss.com/docs/theme)
- Tailwind v4 升级指南:`@custom-variant` 与 dark mode class 策略(https://tailwindcss.com/docs/dark-mode)
- shadcn/ui theming:CSS variables 约定(https://ui.shadcn.com/docs/theming)
