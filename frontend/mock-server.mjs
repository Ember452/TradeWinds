// 本地演示用 mock API:零依赖,占用 8000 端口,配合 Vite 的 /api 代理使用。
// 仅用于无后端环境预览前端界面,数据为内存 fixture,重启即还原。不属于生产代码。
import { createServer } from "node:http";

const json = (res, status, body) => {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
};

const now = () => new Date().toISOString();
let nextId = 100;

const plan = {
  keywords: ["LLM Agent", "tool use", "evaluation", "RAG"],
  sources: ["arxiv", "hackernews", "github"],
  window_days: 7,
  relevance_criteria: ["提出新的 Agent 编排或评测方法", "开源项目有真实可用性", "近 7 天发布"],
};

const topics = [
  {
    id: 1,
    name: "AI Agent 动态",
    description: "近一周 LLM Agent 领域的新技术与开源项目",
    cadence: "daily",
    status: "active",
    plan,
  },
  {
    id: 2,
    name: "RAG 与检索增强",
    description: "检索增强生成的进展:嵌入、重排、评测",
    cadence: "weekly",
    status: "active",
    plan: { ...plan, keywords: ["RAG", "retrieval", "embedding", "rerank"] },
  },
];

const feeds = [
  { id: 1, title: "Hugging Face Blog", url: "https://huggingface.co/blog/feed.xml", status: "healthy", last_checked_at: now() },
];

const makeItem = (id, score, title, source, summary, reason) => ({
  id,
  source,
  url: `https://example.com/item/${id}`,
  title,
  summary,
  reason,
  score,
  published_at: now(),
});

const items = [
  makeItem(11, 9.2, "LangGraph 1.0 发布:图结构编排成为 Agent 框架默认形态", "github", "LangGraph 1.0 把状态机式编排带进主流,支持持久化检查点与人机协同中断。", "与主题直接相关,社区活跃度高"),
  makeItem(12, 8.7, "Tool use 评测基准 ToolBench-2:覆盖多步工具链", "arxiv", "新基准引入可验证的多步工具调用评测,揭示现有模型在长链条任务上的退化。", "评测方法可复用,数据集已开源"),
  makeItem(13, 8.1, "SSE 之外:WebSocket 在流式 Agent 前端中的取舍", "hackernews", "讨论流式对话前端的传输层选择,对比断线重连与代理兼容性。", "工程实践参考价值高"),
  makeItem(14, 7.4, "pgvector 0.8:迭代索引扫描与混合检索", "github", "新版本支持迭代索引扫描,混合检索场景下召回率明显提升。", "与 RAG 主题相关"),
  makeItem(15, 7.0, "Context Caching 实战:把长系统提示的成本降一个量级", "hackernews", "利用前缀缓存优化多轮对话成本,附真实账单对比。", "成本治理实践"),
  makeItem(16, 6.4, "小型开源项目:把 arXiv 摘要转成每日邮件的脚本", "github", "百行左右的 Python 脚本,抓取 arXiv 新论文并汇总发信。", "思路相近,可借鉴"),
  makeItem(17, 6.0, "Anthropic 发布 Claude for Excel 集成", "hackernews", "表格场景的 Agent 化操作,支持跨单元格引用与公式生成。", "产品动态,关注度一般"),
  makeItem(18, 8.9, "Deep Research 类产品的失败模式分析", "arxiv", "系统梳理自动研究 Agent 的五类失败模式:检索漂移、过度自信、引用断裂等。", "直接命中主题,分析框架完整"),
  makeItem(19, 5.5, "某大厂发布通用世界模型预告", "hackernews", "预告性质公告,细节少,社区争议大。", "相关但信息量不足"),
  makeItem(20, 8.4, "OpenAI Function Calling 支持严格 JSON Schema 校验", "github", "structured outputs 特性更新,校验失败自动重试的策略与本文管道一致。", "与结构化输出设计直接相关"),
  makeItem(21, 7.8, "Embedding 模型选型指南 2026 版", "arxiv", "按检索延迟、召回、多语言三个维度横评主流嵌入模型。", "RAG 主题核心参考"),
  makeItem(22, 6.8, "MCP 生态一年:工具协议的采用与碎片化", "hackernews", "回顾 MCP 协议一年来的生态变化,工具互操作性仍是痛点。", "协议层动态"),
];

const reports = [
  { id: 1, period_type: "weekly", period_start: "2026-08-31T00:00:00Z", period_end: "2026-09-06T00:00:00Z", item_count: 8, content: "本周共采纳 8 条内容。核心动态:1) LangGraph 1.0 发布,图编排成为默认形态;2) ToolBench-2 补齐多步工具链评测空白;3) pgvector 0.8 改善混合检索召回。建议关注:Deep Research 失败模式分析对自研管道的降级设计有直接借鉴意义。" },
];

const conversations = [
  {
    id: 1,
    title: "Agent 评测框架调研",
    created_at: now(),
    messages: [
      { id: 1, role: "user", content: "近期值得关注的 Agent 评测框架?", citations: null, tool_trace: null },
      {
        id: 2,
        role: "assistant",
        content: "近期值得关注的有两个方向:\n\n1. ToolBench-2 把评测从单步调用扩展到多步工具链,能暴露长链条任务的能力退化[1]。\n2. Deep Research 失败模式分析给出了检索漂移、引用断裂等五类失败 taxonomy,可直接用于回归评测集设计[2]。\n\n建议先搭多步工具链基准,再按失败 taxonomy 补充负样本。",
        citations: [
          { index: 1, url: "https://arxiv.org/abs/2608.12345" },
          { index: 2, url: "https://arxiv.org/abs/2608.67890" },
        ],
        tool_trace: [{ tool: "search_arxiv" }, { tool: "search_github" }],
      },
    ],
  },
];

const clickSet = new Set();

async function handler(req, res) {
  const url = new URL(req.url, "http://localhost");
  const path = url.pathname;
  const method = req.method ?? "GET";

  // 认证:任意凭据都放行
  if (path === "/api/v1/auth/login" && method === "POST")
    return json(res, 200, { access_token: "mock-token", token_type: "bearer" });
  if (path === "/api/v1/auth/register" && method === "POST") return json(res, 201, {});
  if (path === "/api/v1/users/me") return json(res, 200, { id: 1, email: "demo@tradewinds.local" });

  if (path === "/api/v1/topics" && method === "GET") return json(res, 200, topics);
  if (path === "/api/v1/topics" && method === "POST") {
    let body = "";
    for await (const chunk of req) body += chunk;
    const input = JSON.parse(body || "{}");
    const topic = {
      id: nextId++,
      name: input.name ?? "未命名主题",
      description: input.description ?? "",
      cadence: input.cadence ?? "daily",
      status: "active",
      plan,
    };
    topics.unshift(topic);
    return json(res, 201, { topic, plan });
  }

  let match = path.match(/^\/api\/v1\/topics\/(\d+)$/);
  if (match) {
    const topic = topics.find((t) => t.id === Number(match[1]));
    if (!topic) return json(res, 404, { code: "not_found", message: "主题不存在" });
    if (method === "GET") return json(res, 200, topic);
    if (method === "PATCH") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const input = JSON.parse(body || "{}");
      Object.assign(topic, input);
      return json(res, 200, topic);
    }
  }

  match = path.match(/^\/api\/v1\/topics\/(\d+)\/run$/);
  if (match && method === "POST")
    return json(res, 200, { collected: 14, new_items: 3, accepted: 2, rejected: 1 });

  match = path.match(/^\/api\/v1\/topics\/(\d+)\/mute$/);
  if (match && method === "POST") {
    const topic = topics.find((t) => t.id === Number(match[1]));
    if (!topic) return json(res, 404, { code: "not_found", message: "主题不存在" });
    topic.status = topic.status === "active" ? "muted" : "active";
    return json(res, 200, topic);
  }

  match = path.match(/^\/api\/v1\/topics\/(\d+)\/feeds$/);
  if (match) {
    if (method === "GET") return json(res, 200, feeds);
    if (method === "POST") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const input = JSON.parse(body || "{}");
      feeds.push({ id: nextId++, title: input.url.split("/").pop() ?? input.url, url: input.url, status: "healthy", last_checked_at: now() });
      return json(res, 201, {});
    }
  }

  match = path.match(/^\/api\/v1\/topics\/(\d+)\/feeds\/(\d+)$/);
  if (match && method === "DELETE") {
    const idx = feeds.findIndex((f) => f.id === Number(match[2]));
    if (idx !== -1) feeds.splice(idx, 1);
    return json(res, 204, undefined);
  }

  match = path.match(/^\/api\/v1\/topics\/(\d+)\/items$/);
  if (match && method === "GET") {
    const cursor = url.searchParams.get("cursor");
    const minScore = Number(url.searchParams.get("min_score") ?? 0);
    const start = cursor === null ? 0 : items.findIndex((i) => i.id === Number(cursor));
    const filtered = items.slice(start < 0 ? 0 : start).filter((i) => (i.score ?? 0) >= minScore);
    const page = filtered.slice(0, 10);
    const next = filtered.length > 10 ? filtered[10].id : null;
    return json(res, 200, { items: page, next_cursor: next });
  }

  match = path.match(/^\/api\/v1\/items\/(\d+)\/click$/);
  if (match && method === "POST") {
    clickSet.add(Number(match[1]));
    return json(res, 204, undefined);
  }

  match = path.match(/^\/api\/v1\/topics\/(\d+)\/reports$/);
  if (match && method === "GET") return json(res, 200, Number(match[1]) === 1 ? reports : []);

  match = path.match(/^\/api\/v1\/reports\/(\d+)\/share$/);
  if (match && method === "POST") return json(res, 200, { share_path: "/share/reports/mock-share-token" });

  match = path.match(/^\/api\/v1\/share\/reports\/(.+)$/);
  if (match && method === "GET")
    return json(res, 200, {
      title: "AI Agent 动态",
      period_type: "weekly",
      period_start: "2026-08-31T00:00:00Z",
      period_end: "2026-09-06T00:00:00Z",
      item_count: 8,
      content: reports[0].content,
    });

  // 对话
  if (path === "/api/v1/conversations" && method === "GET")
    return json(res, 200, conversations.map(({ id, title, created_at }) => ({ id, title, created_at })));
  if (path === "/api/v1/conversations" && method === "POST") {
    let body = "";
    for await (const chunk of req) body += chunk;
    const input = JSON.parse(body || "{}");
    const conversation = { id: nextId++, title: input.title || "新对话", created_at: now(), messages: [] };
    conversations.unshift(conversation);
    return json(res, 201, { id: conversation.id, title: conversation.title, created_at: conversation.created_at });
  }

  match = path.match(/^\/api\/v1\/conversations\/(\d+)$/);
  if (match && method === "GET") {
    const conversation = conversations.find((c) => c.id === Number(match[1]));
    if (!conversation) return json(res, 404, { code: "not_found", message: "会话不存在" });
    return json(res, 200, { title: conversation.title, messages: conversation.messages });
  }

  // SSE 回答:citations → delta* → done
  match = path.match(/^\/api\/v1\/conversations\/(\d+)\/messages$/);
  if (match && method === "POST") {
    let body = "";
    for await (const chunk of req) body += chunk;
    const input = JSON.parse(body || "{}");
    const conversation = conversations.find((c) => c.id === Number(match[1]));
    const citations = [
      { index: 1, url: "https://arxiv.org/abs/2608.12345" },
      { index: 2, url: "https://github.com/example/agent-repo" },
    ];
    const answer = `关于「${input.content ?? ""}」,mock 回答要点如下:\n\n1. 多步工具链评测是当前主线,ToolBench-2 覆盖了可验证的多步调用[1]。\n2. 开源编排框架的检查点与中断恢复机制日趋成熟,值得在自研管道中借鉴[2]。\n\n这是演示环境的固定回答,真实回答需要配置 LLM key 启动后端。`;
    conversation.messages.push({ id: nextId++, role: "user", content: input.content ?? "", citations: null, tool_trace: null });
    conversation.messages.push({ id: nextId++, role: "assistant", content: answer, citations, tool_trace: [{ tool: "search_arxiv" }] });

    res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
    const send = (type, data) => res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`);
    send("citations", { citations });
    for (const chunk of answer.match(/[\s\S]{1,24}/g) ?? []) {
      send("delta", { text: chunk });
      await new Promise((r) => setTimeout(r, 40));
    }
    send("done", {});
    return res.end();
  }

  return json(res, 404, { code: "not_found", message: `mock 未实现: ${method} ${path}` });
}

createServer((req, res) => handler(req, res).catch(() => json(res, 500, { code: "internal", message: "mock 内部错误" }))).listen(8000, () => {
  console.log("mock API listening on http://localhost:8000 (login accepts any credentials)");
});
