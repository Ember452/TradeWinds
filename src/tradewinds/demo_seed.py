"""演示数据 seed:一键生成可演示的预置数据,幂等(演示账号已存在即整体跳过)。

运行:python -m tradewinds.demo_seed(容器内已配 DATABASE_URL,或本地 make seed)。
纯本地数据,零网络零 LLM;报告经 ReportService 真实聚合生成,与线上逻辑同构。
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.config import get_settings
from tradewinds.core.database import create_engine, create_session_factory
from tradewinds.core.security import hash_password
from tradewinds.models.conversation import Conversation, Message, MessageRole
from tradewinds.models.engagement import ItemClick
from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.push_log import PushLog, PushStatus, PushType
from tradewinds.models.topic import Cadence, Topic, TopicStatus
from tradewinds.models.user import User
from tradewinds.services.push_service import digest_key_of
from tradewinds.services.report_service import ReportService
from tradewinds.tools.base import url_hash

DEMO_EMAIL = "demo@tradewinds.local"
DEMO_PASSWORD = "demo12345"


def _plan(
    keywords: list[str], sources: list[str], *, arxiv: list[str] | None = None
) -> dict[str, object]:
    return {
        "keywords": keywords,
        "sources": sources,
        "arxiv_categories": arxiv or [],
        "github": {"keywords": keywords[:2], "min_stars": 100},
        "window_days": 7,
        "relevance_criteria": ["与主题直接相关", "有代码或论文佐证"],
    }


def _item(
    topic_id: int,
    source: str,
    url: str,
    title: str,
    score: float,
    cluster: str,
    summary: str,
    reason: str,
) -> Item:
    accepted = score >= 6.0
    return Item(
        topic_id=topic_id,
        source=source,
        url=url,
        url_hash=url_hash(url, topic_id),
        title=title,
        raw_content=f"{title}。{summary}(演示预置内容,仅用于本地展示。)",
        published_at=datetime.now(UTC) - timedelta(days=1),
        score=score,
        cluster_key=cluster,
        summary=summary if accepted else None,
        reason=reason if accepted else None,
        status=ItemStatus.accepted if accepted else ItemStatus.rejected,
    )


_TOPIC1_ITEMS = [
    (
        "arxiv",
        "https://arxiv.org/abs/2603.04417",
        "ReAct-R2:反思式工具调用让 Agent 自纠错",
        9.2,
        "agent-frameworks",
        "提出反思-重试机制,工具调用失败后模型自行修正参数再试,基准任务成功率提升 14%。",
        "与主题高度相关:直接改进工具循环的容错方式,有论文与代码。",
    ),
    (
        "github",
        "https://github.com/browser-use/browser-use",
        "browser-use:让 LLM 操控浏览器的 Agent 库",
        8.8,
        "agent-frameworks",
        "把网页交互抽象成工具集,模型可点击、填表、导航;本周新增结构化输出模式。",
        "Star 增长快,issue 活跃,是浏览器 Agent 方向的代表性实现。",
    ),
    (
        "hackernews",
        "https://news.ycombinator.com/item?id=44912345",
        "我们用多 Agent 评审替代了代码人工初审",
        8.5,
        "multi-agent",
        "作者描述用三个角色 Agent(作者/评审/仲裁)做代码初审,误报率与人工评审相当。",
        "一线实践经验,含成本与失败案例,对多 Agent 编排有参考价值。",
    ),
    (
        "arxiv",
        "https://arxiv.org/abs/2603.01882",
        "Agent 记忆的分层压缩:摘要层级决定检索质量",
        7.8,
        "memory",
        "对比扁平记忆与分层摘要记忆,后者在长程任务中检索命中率提升明显。",
        "与 RAG 已读检索设计直接相关,值得跟踪其分层策略。",
    ),
    (
        "hackernews",
        "https://news.ycombinator.com/item?id=44909876",
        "MCP 一年后:工具生态真的标准化了吗",
        7.2,
        "tool-ecosystem",
        "梳理 MCP 协议落地一年的生态现状:客户端采纳广,服务端质量参差。",
        "工具协议方向的生态综述,与本项目工具层设计可对照。",
    ),
    (
        "github",
        "https://github.com/pydantic/pydantic-ai",
        "pydantic-ai:类型安全的 Agent 框架发布 1.0",
        6.8,
        "agent-frameworks",
        "以 Pydantic 校验为核心的结构化输出 Agent 框架正式发布 1.0。",
        "与本项目自研编排层的结构化输出同构,可对照其重试设计。",
    ),
    (
        "arxiv",
        "https://arxiv.org/abs/2602.09931",
        "通用对话系统的情感陪伴能力评测",
        4.1,
        "unrelated",
        "提出情感陪伴维度的评测基准。",
        "",
    ),
    (
        "hackernews",
        "https://news.ycombinator.com/item?id=44898765",
        "Show HN: 我做了一个 AI 简历筛选器",
        3.5,
        "unrelated",
        "面向 HR 的简历筛选 SaaS。",
        "",
    ),
]

_TOPIC2_ITEMS = [
    (
        "arxiv",
        "https://arxiv.org/abs/2603.02764",
        "GraphRAG 的检索边界:图结构何时反而拖累召回",
        8.9,
        "graphrag",
        "系统评测 GraphRAG 与向量 RAG,发现图结构在多跳问题占优、单跳召回反而更差。",
        "对检索增强的选型有直接指导意义,实验设置完整。",
    ),
    (
        "arxiv",
        "https://arxiv.org/abs/2602.08815",
        " Late-Chunking:先编码后切分的嵌入式检索",
        8.1,
        "chunking",
        "先对全文编码再切分,使块向量携带全文上下文,小模型检索质量逼近大模型。",
        "实现成本低、效果提升明确,是分块策略的实用改进。",
    ),
    (
        "github",
        "https://github.com/pgvector/pgvector",
        "pgvector 0.8:迭代式扫描与混合查询优化",
        7.4,
        "vector-store",
        "新版本改进 ANN 索引的迭代扫描,过滤查询不再漏召回。",
        "本项目向量存储正是 pgvector,版本演进值得跟进。",
    ),
    (
        "hackernews",
        "https://news.ycombinator.com/item?id=44904567",
        "RAG 已死?长上下文时代检索依然便宜得多",
        6.9,
        "rag-vs-context",
        "作者用成本模型论证:长上下文全量塞入的费用比检索高两个数量级。",
        "对「检索 vs 长上下文」的取舍给出了量化视角。",
    ),
]


async def seed_demo(session: AsyncSession) -> bool:
    """写入演示数据;返回是否执行了写入(演示账号已存在则整体跳过)。"""
    existing = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
    if existing is not None:
        return False

    user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
    session.add(user)
    await session.flush()

    far_future = datetime.now(UTC) + timedelta(days=30)
    topic_agent = Topic(
        user_id=user.id,
        name="Agent 新技术动态",
        description="跟踪 LLM Agent 框架、工具调用、多智能体协作方向的新论文、新项目与一线实践。",
        plan=_plan(
            ["LLM agent", "tool use", "multi-agent"],
            ["arxiv", "hackernews", "github"],
            arxiv=["cs.AI", "cs.CL"],
        ),
        cadence=Cadence.daily,
        status=TopicStatus.active,
        last_run_at=datetime.now(UTC) - timedelta(days=1),
        next_run_at=far_future,
    )
    topic_rag = Topic(
        user_id=user.id,
        name="RAG 与检索增强",
        description="跟踪检索增强生成(RAG)的检索策略、向量存储与分块技术进展。",
        plan=_plan(
            ["RAG", "retrieval augmented", "embedding"],
            ["arxiv", "hackernews", "github"],
            arxiv=["cs.IR"],
        ),
        cadence=Cadence.weekly,
        status=TopicStatus.active,
        last_run_at=datetime.now(UTC) - timedelta(days=2),
        next_run_at=far_future,
    )
    session.add_all([topic_agent, topic_rag])
    await session.flush()

    items_agent = [_item(topic_agent.id, *row) for row in _TOPIC1_ITEMS]
    items_rag = [_item(topic_rag.id, *row) for row in _TOPIC2_ITEMS]
    session.add_all(items_agent + items_rag)
    await session.flush()

    # 报告经真实聚合服务生成,分享 token 直接就绪
    report = await ReportService(session).upsert_period_report(topic_rag, now=datetime.now(UTC))
    if report is not None:
        await ReportService(session).share(user.id, report.id)

    session.add_all([ItemClick(user_id=user.id, item_id=item.id) for item in items_agent[:3]])

    session.add_all(
        [
            PushLog(
                topic_id=topic_agent.id,
                user_id=user.id,
                channel="email",
                digest_key=digest_key_of([item.url for item in items_agent[:3]]),
                item_ids=[item.id for item in items_agent[:3]],
                recipient=DEMO_EMAIL,
                status=PushStatus.sent,
                sent_at=datetime.now(UTC) - timedelta(hours=20),
            ),
            PushLog(
                topic_id=topic_agent.id,
                user_id=user.id,
                channel="email",
                digest_key=f"item:{items_agent[0].id}",
                item_ids=[items_agent[0].id],
                recipient=DEMO_EMAIL,
                status=PushStatus.sent,
                push_type=PushType.immediate,
                cluster_key=items_agent[0].cluster_key,
                sent_at=datetime.now(UTC) - timedelta(hours=19),
            ),
        ]
    )

    conversation = Conversation(user_id=user.id, title="Agent 框架近况")
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            Message(
                conversation_id=conversation.id,
                role=MessageRole.user,
                content="Agent 框架最近有什么值得看的新东西?",
            ),
            Message(
                conversation_id=conversation.id,
                role=MessageRole.assistant,
                content=(
                    "近两周值得关注的方向有三个:\n"
                    "1. 工具循环容错:ReAct-R2 提出反思-重试机制,工具失败后模型自行修正参数,"
                    "基准任务成功率提升约 14% [1];\n"
                    "2. 浏览器 Agent:browser-use 把网页交互抽象成工具集,"
                    "本周新增结构化输出模式 [2];\n"
                    "3. 多 Agent 实践:有团队用三角色 Agent 做代码初审,误报率已与人工相当 [3]。\n"
                    "如果只看一个,建议先读 [1],它对本项目的工具循环设计最有参考价值。"
                ),
                citations=[
                    {
                        "index": 1,
                        "url": "https://arxiv.org/abs/2603.04417",
                        "title": "ReAct-R2:反思式工具调用让 Agent 自纠错",
                        "source": "arxiv",
                    },
                    {
                        "index": 2,
                        "url": "https://github.com/browser-use/browser-use",
                        "title": "browser-use:让 LLM 操控浏览器的 Agent 库",
                        "source": "github",
                    },
                    {
                        "index": 3,
                        "url": "https://news.ycombinator.com/item?id=44912345",
                        "title": "我们用多 Agent 评审替代了代码人工初审",
                        "source": "hackernews",
                    },
                ],
                tool_trace=[
                    {
                        "tool": "search_arxiv",
                        "arguments": {"query": "agent tool use"},
                        "result": "3 条候选",
                    },
                    {
                        "tool": "search_github",
                        "arguments": {"keywords": ["llm agent"]},
                        "result": "2 条候选",
                    },
                    {
                        "tool": "fetch_page",
                        "arguments": {"url": "https://arxiv.org/abs/2603.04417"},
                        "result": "已抓取原文",
                    },
                ],
            ),
        ]
    )
    await session.commit()
    return True


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            created = await seed_demo(session)
        print("演示数据已写入" if created else "演示数据已存在,跳过")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
