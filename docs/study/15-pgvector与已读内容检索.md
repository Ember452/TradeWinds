# pgvector 与已读内容检索

## 这个知识点是什么

RAG(检索增强生成)在这里的形态很具体:把用户读过的每条内容变成一个**向量**(一段文本的语义坐标),"我上周看过的那篇讲 xx 的文章"变成一次**最近邻查询**——把问题也变成向量,找距离最近的那几条。pgvector 是 PostgreSQL 的向量扩展,让"存向量 + 按距离排序"不用离开关系数据库。

类比:给每条已读内容发一张语义坐标卡;提问时把问题标到同一坐标系上,取最近的几张卡。pgvector 的意义是坐标系和书架(业务表)在同一个房间,一个 SQL 搞定,不用引进一座新仓库(独立向量库)。

## TradeWinds 为什么需要它

对话 Agent 已能检索公开信息,但回答不了"我之前看过什么"——用户没有记忆库。扩展计划明确:不引入独立向量库,pgvector 优先。这一步让"跨会话记忆"(点击偏好)之外又多了一个检索维度的记忆:语义级已读回忆。

## 本项目怎么实现的

- **迁移([0010](../../alembic/versions/0010_item_embeddings.py))**:`CREATE EXTENSION vector` + `item_embeddings`(item_id 级联主键)。**向量列不锁维度**——MVP 数据量下精确检索足够,不需要 ivfflat ANN 索引;换嵌入模型(维度变化)不用改表。规模触发 ANN 需求时,再固定维度建索引,升级路径已在 study 里写明;
- **嵌入生成**([agents/orchestrator/embeddings.py](../../src/tradewinds/agents/orchestrator/embeddings.py)):`OpenAICompatibleEmbedder` 走 OpenAI-compatible `/embeddings`,错误包装为 LLMError;管道 run 后对 accepted 条目的 `标题+摘要+正文片段` 生成嵌入 upsert;**失败记 warning 不阻塞管道**(降级原则——嵌入是增强,不是主链路);
- **检索**([services/rag_service.py](../../src/tradewinds/services/rag_service.py)):`<=>`(余弦距离)top-K,JOIN items/topics 限定**只检索当前用户自己的 accepted 条目**;REST `GET /items/search` + 对话工具 `search_history`,后者回答"我上周看过的那篇 xx";
- **总开关**:`TRADEWINDS_EMBEDDING_MODEL` 未配置时功能整体关闭(接口 404、工具不注册),不引入半可用状态。

## 踩过的坑

1. **对话工具拿不到"当前用户"**:工具在 ToolLoop 的任务里执行,不在请求依赖链上。用 `contextvars.ContextVar` 在对话期声明当前用户,任务创建时自动捕获上下文——工具内部经 `current_rag_user()` 取值;不传就明确报"无法确定当前用户",绝不放宽成全局检索;
2. **pgvector 的向量字面量**:驱动不认识 `list[float]`,要用 `'[1,2,3]'` 文本字面量 + `CAST(:v AS vector)`;写入与查询两端都要 CAST;
3. **compose 镜像**:官方 `postgres:16` 不带 pgvector,换 `pgvector/pgvector:pg16`——本地 compose 与 CI service 要同步换,否则集成测试在 CREATE EXTENSION 处炸。

## 延伸阅读

- [pgvector GitHub](https://github.com/pgvector/pgvector)——操作符(`<=>` 余弦)与索引选项
- [OpenAI: Embeddings guide](https://platform.openai.com/docs/guides/embeddings)——嵌入 API 语义
- [Supabase: pgvector 入门](https://supabase.com/docs/guides/database/extensions/pgvector)——含索引维度锁定的权衡讲解
