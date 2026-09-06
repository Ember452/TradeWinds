# 工程骨架:pyproject 统一配置

## 这个知识点是什么

`pyproject.toml` 是 Python 官方(PEP 518/621)定义的项目描述文件,如今已经能承载一个项目的**全部工具配置**:依赖与构建方式、ruff 的 lint 规则、mypy 的严格度、pytest 的运行参数。所谓"统一配置"就是让 `pyproject.toml` 成为这些工具配置的**唯一来源**——任何人 clone 仓库后,运行同一条命令得到完全相同的行为,不存在"README 里说用旧参数"或"CI 和本机行为不一致"的问题。

类比:它像餐厅的"总菜单"——后厨(ruff)、品控(mypy)、试吃员(pytest)都按同一份菜单工作,而不是各记各的小抄。

## TradeWinds 为什么需要它

本项目按 AGENTS.md 的规范执行"每个 Task 必过 lint + mypy + 测试三道闸"。如果工具配置散落在 `setup.cfg`、`tox.ini`、`ruff.toml`、零散命令行参数里,就会出现:

- 本机能过、CI 挂掉(参数不同步);
- 新增依赖忘记声明,别人拉代码跑不起来;
- 每次都要凭记忆敲长命令,违反 architecture.md "禁止凭记忆敲长命令"的规定。

## 本项目怎么实现的

配置全部在 [pyproject.toml](../../pyproject.toml),要点:

- **src layout**(`src/tradewinds/`)+ hatchling 构建:测试与运行时导入的都是"安装后的包",避免"本地能跑因为 cwd 恰好对"的假象;
- **依赖分组**:运行时依赖在 `[project].dependencies`,开发工具在 `[dependency-groups].dev`,用 `uv sync` 一键安装;
- **ruff**:选定规则集(`E/W/F/I/N/UP/B/C4/SIM/ASYNC/RUF`),`api/` 目录对 B008(FastAPI 的 `Depends()` 惯用法)豁免;
- **mypy strict + pydantic 插件**:全量类型标注,插件让 mypy 理解 Pydantic 模型的运行时行为;
- **pytest**:`asyncio_mode = "auto"`(协程测试不用逐个加装饰器);`integration` 标记区分需要真实 PG/Redis 的集成测试,默认命令排除它们,CI 的集成 job 才跑;
- **统一入口 [Makefile](../../Makefile)**:`make lint / type / test / up` 等目标包装 `uv run ...` 命令;[pre-commit](../../.pre-commit-config.yaml) 用 `language: system` 的本地钩子直接调用 `uv run`,与 Makefile、CI 共用同一套配置。

## 踩过的坑

1. **ruff format 把 markdown 里的 Python 代码块也格式化了**(ruff 0.16),导致改代码时文档被顺带改动。解决:`extend-exclude = ["*.md"]`,文档变更必须可追溯到文档任务本身。
2. **mypy strict 报 `Settings()` 缺少必填参数**:字段明明由 pydantic-settings 从环境变量读取,但 mypy 按 `__init__` 签名检查。解决:启用 `plugins = ["pydantic.mypy"]`,让 mypy 理解 Pydantic 的声明式模型。
3. **ruff B008 与 FastAPI 冲突**:B008 禁止"参数默认值里调用函数",而 FastAPI 依赖注入正是这么写的。解决:`per-file-ignores` 只对 `src/tradewinds/api/**` 豁免。
4. **starlette TestClient 不进 `with` 就不触发 lifespan**:单元冒烟测试直接 `client.get()`,不会执行 lifespan 里的 DB/Redis 连接,这让"无环境变量也能跑冒烟测试"成立——但要求依赖里不能假设 `app.state` 一定存在。

## 延伸阅读

- [pyproject.toml 规范(PEP 621)](https://packaging.python.org/en/latest/specifications/pyproject-toml/)
- [uv 官方文档](https://docs.astral.sh/uv/)
- [ruff 配置文档](https://docs.astral.sh/ruff/configuration/)
- [mypy pydantic 插件](https://docs.pydantic.dev/latest/integrations/mypy/)
