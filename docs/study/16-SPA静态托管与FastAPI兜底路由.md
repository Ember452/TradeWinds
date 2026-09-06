# SPA 静态托管:FastAPI 兜底路由与容器内前端构建

## 这个知识点是什么

React 这类 SPA(单页应用)只有一个 `index.html`,页面路由(如 `/topics`)由前端 JavaScript 在浏览器里完成。这意味着把构建产物交给 Web 服务托管时,服务器必须理解一条特殊规则:**任何"不是文件、也不是 API"的路径,都返回同一个 `index.html`**(通常叫兜底路由 / fallback),否则用户在 `/topics` 上按 F5 刷新就会得到 404。配套问题是怎么让前端产物进入部署单元——常见做法是把 `npm run build` 也做成 Docker 构建的一个阶段(multi-stage build),让"一条命令起全栈"不依赖宿主机装 Node。

类比:API 路由像医院的挂号窗口,各窗口各管各的;SPA 兜底路由则是大堂咨询台——凡是没挂科室牌子的来访者,一律递上同一份就诊指南(index.html),由指南带他去真正的地方。但 `api/` 开头的"内部通道"不走咨询台,走错了就该 404。

## TradeWinds 为什么需要它

定位调整为面试可演示项目(design.md v0.3)后,演示形态是"`make demo` 一条命令起全栈"。此前前端只有两种跑法:vite dev server(需要宿主机 Node + 第二个终端)或不托管——面试现场"两条命令、两个终端、还得等 npm"是演示事故的高发区。目标改为:前端构建产物打进 api 镜像,api 容器自己托管 SPA,浏览器访问 `http://localhost` 一步直达,且 `static_dir` 不配置时行为与旧版完全一致(本地开发照旧走 vite 代理,零侵入)。

## 本项目怎么实现的

核心在 [src/tradewinds/api/app.py](../../src/tradewinds/api/app.py) 的 `mount_spa(app, static_dir)`:

```python
def mount_spa(app: FastAPI, static_dir: str) -> None:
    if not static_dir:
        return
    dist = Path(static_dir)
    if not (dist / "index.html").is_file():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="spa_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)   # /api 未知路径不兜底
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
```

设计取舍:

- **挂载时机在 lifespan 而非 `create_app()`**:`create_app()` 在部分单测里被"不启动服务"地调用(如 healthz 冒烟测试),而 `get_settings()` 是 lru_cache 的必填校验配置单例——在工厂里读配置会让这些测试在 CI(无环境变量)下炸掉。lifespan 里 `get_settings()` 本来就会被调用,SPA 挂载顺路完成,还保证"路由注册先于第一个请求"。
- **路由优先级靠注册顺序**:FastAPI 按注册顺序匹配,API 路由在工厂里先注册,兜底路由最后注册,所以 `/api/v1/...`、`/healthz`、`/docs` 永远优先于兜底;`Mount("/assets")` 挂在兜底之前,静态资源精确命中。
- **`/api` 前缀显式排除**:兜底路由 `/{full_path:path}` 理论上能吞掉一切 GET,若 API 调用方拼错路径,会收到 200 + HTML 而不是 404——对前端 fetch 客户端的错误处理是灾难(它会把 HTML 当 JSON 解析)。显式排除让"API 路径 404"语义保持诚实。
- **产物就绪检测**:`index.html` 不存在就不挂载,配置了但镜像里没有前端产物时优雅降级为纯 API 服务。
- **容器内构建**([Dockerfile](../../Dockerfile)):新增 `node:22-alpine` 阶段,`npm ci && npm run build`,产物 `COPY --from=frontend-builder /web/dist /app/static`;compose 给 api 注入 `TRADEWINDS_STATIC_DIR=/app/static`。配套 [.dockerignore](../../.dockerignore) 从排除整个 `frontend` 改为只排除 `frontend/node_modules` 与 `frontend/dist`(排除规则里不带斜线的 `dist` 只匹配仓库根目录,不挡子目录)。

## 踩过的坑

1. **"SPA 兜底吞掉 API 404"不是理论问题**:首版测试里 `GET /api/v1/no-such-endpoint` 若不做前缀排除,会拿到 200 和 `index.html`,单测 `assert "demo-index" not in response.text` 专门钉住这个回归;
2. **`create_app()` 不等于"应用启动"**:已有测试 `TestClient(create_app())` 不进入 `with` 就不发 lifespan,若把需要配置读取的逻辑放进工厂函数,这些测试会以"缺 TRADEWINDS_DATABASE_URL"的方式失败——工厂只做零依赖的路由拼装,一切读配置的动作留在 lifespan;
3. **Windows 本地无 Docker**:集成测试与 compose 链路本机无法验证,只能靠"单测覆盖 mount_spa 纯逻辑 + 真实 dist 冒烟脚本"逼近,compose 层的正确性要等 CI 或有 Docker 的环境确认(见实施记录)。

## 延伸阅读

- [FastAPI: Static Files](https://fastapi.tiangolo.com/tutorial/static-files/)——`StaticFiles` 挂载与 `html=True` 的局限(不做客户端路由兜底)
- [Starlette: Routing](https://www.starlette.io/routing/)——按注册顺序匹配的路由语义,`Mount` 与 path 参数路由的优先级
- [Docker: Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)——构建阶段与运行阶段分离,产物只拷贝不携带工具链
- [Vite: 构建产物结构](https://vitejs.dev/guide/build.html)——`dist/index.html` 与 `assets/` 的默认布局及 `base` 对资源路径的影响
