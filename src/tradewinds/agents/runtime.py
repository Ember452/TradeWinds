"""运行时组件组装:从 Settings 构建编排层与信息源组件。

app(lifespan)与 Celery 任务共用,保证两端行为一致;不含业务语义。
"""

from dataclasses import dataclass

import httpx

from tradewinds.agents.analyst import Analyst
from tradewinds.agents.editor import Editor
from tradewinds.agents.orchestrator.embeddings import Embedder, OpenAICompatibleEmbedder
from tradewinds.agents.orchestrator.llm import (
    LLMProvider,
    ModelTier,
    OpenAICompatibleProvider,
)
from tradewinds.agents.orchestrator.metering import UsageRecorder
from tradewinds.agents.orchestrator.structured import StructuredRunner
from tradewinds.agents.planner import Planner
from tradewinds.agents.retriever import Retriever
from tradewinds.core.config import Settings
from tradewinds.tools.arxiv import ArxivClient
from tradewinds.tools.base import RateLimiter, SourceClient
from tradewinds.tools.fetcher import Fetcher
from tradewinds.tools.github import GithubClient
from tradewinds.tools.hackernews import HackerNewsClient


@dataclass
class PipelineComponents:
    planner: Planner
    analyst: Analyst
    editor: Editor
    retriever: Retriever
    provider: LLMProvider
    source_clients: list[SourceClient]
    fetcher: Fetcher
    rate_limiter: RateLimiter
    http_client: httpx.AsyncClient
    embedder: Embedder | None


def build_pipeline_components(
    settings: Settings, *, usage_recorder: UsageRecorder | None = None
) -> PipelineComponents:
    http_client = httpx.AsyncClient(timeout=30, follow_redirects=True)
    limiter = RateLimiter(max_concurrency=5, min_interval_seconds=1.0)
    provider = OpenAICompatibleProvider(
        base_url=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model_map={
            ModelTier.low: settings.model_low,
            ModelTier.mid: settings.model_mid,
        },
    )
    runner = StructuredRunner(provider)
    source_clients: list[SourceClient] = [
        ArxivClient(limiter, http_client),
        HackerNewsClient(limiter, http_client),
        GithubClient(limiter, http_client, token=settings.github_token),
    ]
    return PipelineComponents(
        planner=Planner(runner),
        analyst=Analyst(runner, recorder=usage_recorder),
        editor=Editor(runner, recorder=usage_recorder),
        retriever=Retriever(source_clients),
        provider=provider,
        source_clients=source_clients,
        fetcher=Fetcher(limiter, http_client),
        rate_limiter=limiter,
        http_client=http_client,
        embedder=(
            OpenAICompatibleEmbedder(
                base_url=settings.llm_api_base,
                api_key=settings.llm_api_key,
                model=settings.embedding_model,
            )
            if settings.embedding_model
            else None
        ),
    )
