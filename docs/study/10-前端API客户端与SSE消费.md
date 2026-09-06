# 前端 API 客户端与 SSE 消费

## 这个知识点是什么

前端要消费后端的 REST + SSE 两种接口。REST 侧的核心是**统一的 API 客户端**:所有请求收口到一个函数,统一注入 JWT、统一解析 `{code, message}` 错误体、统一处理 401(token 过期清凭证回登录页)。SSE 侧的核心是**用 fetch 流式读取实现事件消费**——`EventSource` 只支持 GET,无法携带 POST body 和 Authorization 头,所以对话流必须手动解析 SSE 帧。

类比:统一 API 客户端像公司的收发室,所有快递(请求)都从这里进出,安检(401/错误解析)只做一次;手动 SSE 解析像自己拆快递——快递员(EventSource)不收你要寄的包裹(POST body),只好自己开车去取。

## TradeWinds 为什么需要它

对话 Agent 的回答是流式的,且要携带 JWT 发 POST——这两个条件一叠加,`EventSource` 直接出局。同时前端有主题/Feed/会话多个模块,如果各处自行 fetch,token 过期处理和错误提示会各写一套、必然漂移。

## 本项目怎么实现的

- **统一客户端**([shared/api.ts](../../frontend/src/shared/api.ts)):`api<T>()` 泛型函数收口全部 REST 调用;401 时清 token 并跳转 `/login`;非 2xx 解析后端统一错误体抛 `ApiError(status, code, message)`,组件层按 `code`(如 `chat_busy`、`quota_exceeded`)分支提示;
- **SSE 消费**:`streamSSE(path, body, onEvent, signal)` 用 fetch 的 `ReadableStream` reader 逐块解码,按空行分帧、解析 `event:`/`data:`,回调给调用方;`AbortSignal` 支持中断;
- **事件驱动渲染**([features/chat/ChatPage.tsx](../../frontend/src/features/chat/ChatPage.tsx)):`citations` 事件先更新引用列表,`delta` 事件逐段追加正文(天然打字机效果),`done` 收尾;流抛错时保留已生成内容并显示"重新提问";
- **无限滚动**([features/topics/TopicDetailPage.tsx](../../frontend/src/features/topics/TopicDetailPage.tsx)):Feed 用后端 keyset 游标 + `IntersectionObserver` 哨兵元素触底加载,配合 `min_score` 参数。

## 踩过的坑

1. **`verbatimModuleSyntax` 下的类型导入**:React 组件 props 里的 `ReactNode` 必须用 `import type`,普通导入在 tsc --noEmit 下报错;
2. **SSE 帧边界**:TCP 分块不保证对齐事件帧,必须维护缓冲区按 `\n\n` 切分,且最后一个不完整帧要留在 buffer 里(`decode(value, {stream: true})`);
3. **路由守卫与 401 的循环**:登录页不需要 token,守卫不能在"token 过期跳登录"后再拦截一次跳转;处理方式是 401 只在非 `/login` 路径时跳转。

## 延伸阅读

- [Vite Guide](https://vite.dev/guide/)——dev 代理与构建
- [TypeScript-eslint flat config](https://typescript-eslint.io/getting-started)——本项目 ESLint 配置方式
- [Streams API](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API)——ReadableStream 逐块读取与 TextDecoder 的 stream 模式
