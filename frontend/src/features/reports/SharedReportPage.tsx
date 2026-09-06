import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../../shared/api";

interface SharedReport {
  title: string;
  period_type: "daily" | "weekly";
  period_start: string;
  period_end: string;
  item_count: number;
  content: string;
}

/** 公开分享页:无需登录,凭 share_token 只读访问(后端不返回任何用户信息)。 */
export function SharedReportPage() {
  const { token } = useParams();
  const [report, setReport] = useState<SharedReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api<SharedReport>(`/api/v1/share/reports/${token}`)
      .then(setReport)
      .catch(() => setError("报告不存在或链接已失效"));
  }, [token]);

  if (error) return <p className="empty">{error}</p>;
  if (!report) return <p className="loading">加载中…</p>;

  const periodLabel = report.period_type === "weekly" ? "周报" : "日报";

  return (
    <div className="card share-page">
      <h1>
        {report.title} {periodLabel}
      </h1>
      <p className="meta">
        {report.period_start.slice(0, 10)} ~ {report.period_end.slice(0, 10)}(UTC) ·{" "}
        {report.item_count} 条
      </p>
      <pre className="report-content">{report.content}</pre>
      <p className="meta">
        由 <a href="/">TradeWinds</a> 生成
      </p>
    </div>
  );
}
