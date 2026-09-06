# 自研 Agent 工具循环

## 这个知识点是什么

"工具循环"(agentic loop)是让 LLM 从"一次问答"升级为"多步做事"的核心机制:模型先看问题和可用工具清单,要么直接回答,要么请求调用某个工具;程序执行工具、把结果喂回对话历史,再让模型继续,直到它给出最终答案。一个循环 = LLM 决策 + 程序执行 + 结果回注,反复迭代。

类比:普通调用像问一位闭门造车的专家;工具循环像给专家配了一部电话——他可以随时查资料、让助手跑腿(工具),拿到结果再继续思考,直到给出结论。

## TradeWinds 为什么需要它

TradeWinds 的对话研究 Agent 要"边查边答":用户问一个研究问题,Agent 需要调用 arXiv/HN/GitHub 搜索和网页抓取,再综合作答。设计文档明确不引入 LangGraph/PydanticAI 等编排框架——四角色管道是固定流程,用框架反而引入不可控的黑盒;自研循环只需要:Provider 抽象、工具注册表、护栏(截断/超时/迭代上限)。

## 本项目怎么实现的

核心在 [agents/orchestrator/loop.py](../../src/tradewinds/agents/orchestrator/loop.py),约 200 行:

- **决策载体用结构化输出**:`AssistantTurn(content, tool_calls)` 是 Pydantic 模型,每轮通过 `provider.complete(response_model=AssistantTurn)` 拿到校验过的决策——模型要么给 `content`,要么给 `tool_calls`。这是与"SDK 原生 tool_calls"的关键取舍:不绑定供应商的函数调用协议,换模型、做流式都不动循环层;
- **工具注册表**:`ToolRegistry.register(name, description, execute)`,执行时 `KeyError`(未知工具)和任意异常都由循环层捕获,转成 `ToolTrace(error=...)` 以 `role=tool` 消息回注,循环继续——工具故障是"模型可见的信息",不是"程序错误"(design.md 4.1 的原则);
- **三条护栏**:`truncate_messages` 超长时保留系统指令+最近消息;`asyncio.timeout` 控制总时长;`max_iterations` 控制轮数,三者都以 `LoopResult.stopped_reason` 显式上报,上层可以"声明局限作答"而不是拿到半个崩溃状态。

## 踩过的坑

1. **`asyncio.timeout` 抛的是 `TimeoutError`**(3.11+ 内建),不是 `asyncio.TimeoutError` 的旧别名包装,捕获时写错类型会静默漏接;
2. **测试里构造"非法输出"不能用 Pydantic 模型**:`StrictAnswer(number=-1)` 在构造时就抛 ValidationError,轮不到循环层处理——要用 dict 模拟 LLM 的原始输出;
3. **截断预算要把系统指令算进去**:`budget = max_chars - len(system)`,否则系统指令特别长时"最近消息"会被全部丢掉。

## 延伸阅读

- [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)——"workflow vs agent"的边界划分,与本项目"管道用 workflow、对话用 loop"一致
- [OpenAI Cookbook: Function calling](https://cookbook.openai.com/examples/function_calling)——理解原生 tool_calls 协议,便于对比本实现的取舍
