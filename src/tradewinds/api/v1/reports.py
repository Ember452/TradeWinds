"""报告路由:主题报告列表、详情、分享,以及无鉴权的公开分享访问。"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.api.deps import get_current_user, get_db
from tradewinds.models.report import Report, ReportPeriodType
from tradewinds.models.user import User
from tradewinds.services.report_service import ReportService

router = APIRouter(tags=["reports"])


class ReportRead(BaseModel):
    id: int
    topic_id: int
    period_type: ReportPeriodType
    period_start: datetime
    period_end: datetime
    item_count: int
    share_token: str | None
    content: str

    model_config = {"from_attributes": True}


class SharedReportRead(BaseModel):
    title: str
    period_type: ReportPeriodType
    period_start: datetime
    period_end: datetime
    item_count: int
    content: str


class ShareResponse(BaseModel):
    share_token: str
    share_path: str
    page_path: str


def _service(session: AsyncSession = Depends(get_db)) -> ReportService:
    return ReportService(session)


def _to_read(report: Report) -> ReportRead:
    data = ReportRead.model_validate(report)
    data.item_count = len(report.item_ids or [])
    return data


@router.get("/topics/{topic_id}/reports", response_model=list[ReportRead])
async def list_reports(
    topic_id: int,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(_service),
) -> list[ReportRead]:
    return [
        _to_read(report)
        for report in await report_service.list_for_topic(current_user.id, topic_id)
    ]


@router.get("/reports/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(_service),
) -> ReportRead:
    return _to_read(await report_service.get(current_user.id, report_id))


@router.post("/reports/{report_id}/share", response_model=ShareResponse)
async def share_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    report_service: ReportService = Depends(_service),
) -> ShareResponse:
    report = await report_service.share(current_user.id, report_id)
    assert report.share_token is not None  # share() 必然生成
    token = report.share_token
    return ShareResponse(
        share_token=token,
        share_path=f"/api/v1/share/reports/{token}",
        page_path=f"/share/reports/{token}",
    )


@router.get("/share/reports/{token}", response_model=SharedReportRead)
async def get_shared_report(
    token: str,
    report_service: ReportService = Depends(_service),
) -> SharedReportRead:
    """公开分享访问:仅凭 share_token,不含任何用户信息。"""
    report = await report_service.get_by_share_token(token)
    title = await report_service.topic_title_of(report)
    return SharedReportRead(
        title=title,
        period_type=report.period_type,
        period_start=report.period_start,
        period_end=report.period_end,
        item_count=len(report.item_ids or []),
        content=report.content,
    )
