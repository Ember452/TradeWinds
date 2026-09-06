import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Sailboat } from "lucide-react";
import { api } from "@/shared/api";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

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

  return (
    <div className="min-h-screen">
      {/* 顶部晴空条 */}
      <div
        className="flex items-center justify-between px-6 py-5"
        style={{ background: "linear-gradient(120deg, var(--c-sky-1) 0%, var(--c-sky-2) 100%)" }}
      >
        <Link to="/" className="flex items-center gap-2 font-bold text-white">
          <Sailboat className="size-5" /> TradeWinds
        </Link>
        <Badge className="border-white/40 bg-white/15 text-white hover:bg-white/15">
          公开分享
        </Badge>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-10">
        {error ? (
          <p className="rounded-2xl border border-dashed border-border-soft bg-surface-strong px-6 py-14 text-center text-muted-foreground">
            {error}
          </p>
        ) : !report ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-2/3 rounded-xl" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
        ) : (
          <article className="rounded-2xl border border-border-soft bg-surface p-8 shadow-xl">
            <h1 className="text-2xl font-extrabold">
              {report.title} {report.period_type === "weekly" ? "周报" : "日报"}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {report.period_start.slice(0, 10)} ~ {report.period_end.slice(0, 10)}(UTC) · {report.item_count} 条
            </p>
            <pre className="mt-6 whitespace-pre-wrap break-words font-sans text-sm leading-7">{report.content}</pre>
          </article>
        )}

        <p className="mt-8 text-center text-sm text-muted-foreground">
          由{" "}
          <Link to="/" className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
            <Sailboat className="size-3.5" /> TradeWinds
          </Link>{" "}
          生成 — AI 驱动的技术情报管道
        </p>
      </div>
    </div>
  );
}
