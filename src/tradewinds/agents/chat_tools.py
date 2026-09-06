"""对话工具集:把信息源客户端与网页抓取适配为 ToolLoop 可调用的工具。"""

from collections.abc import Awaitable, Callable, Sequence

from tradewinds.agents.orchestrator.loop import ToolRegistry
from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan, SourceName
from tradewinds.core.text import truncate_text
from tradewinds.tools.base import SourceClient
from tradewinds.tools.fetcher import Fetcher

_SEARCH_SNIPPET_MAX = 300
_FETCH_TEXT_MAX = 1500


def _plan_for(query: str, source: SourceName) -> RetrievalPlan:
    keywords = query.split()[:6]
    if len(keywords) < 2:
        keywords = [query, query]
    return RetrievalPlan(
        keywords=keywords,
        sources=[source],
        arxiv_categories=["cs.AI", "cs.CL"] if source is SourceName.arxiv else [],
        github=None,
        window_days=30,
        relevance_criteria=["与用户问题直接相关"],
    )


def build_chat_registry(
    clients: Sequence[SourceClient],
    fetcher: Fetcher,
    *,
    history_searcher: Callable[[str], Awaitable[str]] | None = None,
) -> ToolRegistry:
    """把源客户端适配为 chat 工具:search_<source> 与 fetch_page。"""
    by_name = {client.name: client for client in clients}
    registry = ToolRegistry()

    def make_search(source: str) -> Callable[[dict[str, str]], Awaitable[str]]:
        async def execute(arguments: dict[str, str]) -> str:
            query = str(arguments["query"]).strip()
            if not query:
                return "错误:query 不能为空"
            plan = _plan_for(query, SourceName(source))
            items = await by_name[source].search(plan, topic_id=0, seen_hashes=set())
            if not items:
                return "无结果"
            snippet_max = _SEARCH_SNIPPET_MAX
            lines = [
                f"- {item.title}\n  {item.url}\n  {truncate_text(item.raw_content, snippet_max)}"
                for item in items
            ]
            return "\n".join(lines)

        return execute

    for source in by_name:
        registry.register(
            name=f"search_{source}",
            description=f'在 {source} 检索,参数 {{"query": "..."}}',
            execute=make_search(source),
        )

    async def fetch_page(arguments: dict[str, str]) -> str:
        url = str(arguments["url"]).strip()
        if not url:
            return "错误:url 不能为空"
        extracted = await fetcher.fetch(url)
        return f"{extracted.title}\n{truncate_text(extracted.text, _FETCH_TEXT_MAX)}"

    registry.register(
        name="fetch_page",
        description='抓取网页原文,参数 {"url": "https://..."}',
        execute=fetch_page,
    )
    return registry
