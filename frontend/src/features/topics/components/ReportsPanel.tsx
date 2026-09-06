import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, Eye, FileBarChart, Share2 } from "lucide-react";
import { api, ApiError } from "@/shared/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/shared/EmptyState";

interface Report {
  id: number;
  period_type: "daily" | "weekly";
  period_start: string;
  period_end: string;
  item_count: number;
  content: string;
}

export function ReportsPanel({ topicId }: { topicId: number }) {
  const [reports, setReports] = useState<Report[] | null>(null);
  const [viewing, setViewing] = useState<Report | null>(null);
  const [shareLinks, setShareLinks] = useState<Record<number, string>>({});

  const load = useCallback(() => {
    api<Report[]>(`/api/v1/topics/${topicId}/reports`).then(setReports).catch(() => setReports([]));
  }, [topicId]);
  useEffect(load, [load]);

  async function handleShare(reportId: number) {
    try {
      const result = await api<{ share_path: string }>(`/api/v1/reports/${reportId}/share`, { method: "POST" });
      const link = `${window.location.origin}${result.share_path}`;
      setShareLinks((prev) => ({ ...prev, [reportId]: link }));
      toast.success("分享链接已生成");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "生成失败");
    }
  }

  if (reports === null) return null;

  return (
    <div>
      <h2 className="mb-4 font-bold">周期报告</h2>
      {reports.length === 0 ? (
        <EmptyState
          icon={<FileBarChart className="size-6" />}
          title="还没有报告"
          description="执行主题后自动按频率聚合生成日报/周报。"
        />
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <div
              key={report.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-soft bg-surface px-4 py-3"
            >
              <div>
                <div className="flex items-center gap-2 font-semibold">
                  <Badge variant={report.period_type === "weekly" ? "default" : "secondary"}>
                    {report.period_type === "weekly" ? "周报" : "日报"}
                  </Badge>
                  {report.period_start.slice(0, 10)} ~ {report.period_end.slice(0, 10)}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{report.item_count} 条精选</p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setViewing(report)}>
                  <Eye className="size-4" /> 查看
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleShare(report.id)}>
                  <Share2 className="size-4" /> 分享
                </Button>
              </div>
            </div>
          ))}
          {Object.entries(shareLinks).map(([reportId, link]) => (
            <p key={reportId} className="flex items-center gap-2 rounded-lg bg-primary/5 px-3 py-2 text-sm">
              <a href={link} target="_blank" rel="noreferrer" className="truncate text-primary hover:underline">
                {link}
              </a>
              <button
                type="button"
                className="shrink-0 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  navigator.clipboard.writeText(link);
                  toast.success("链接已复制");
                }}
                aria-label="复制链接"
              >
                <Copy className="size-4" />
              </button>
            </p>
          ))}
        </div>
      )}

      <Dialog open={viewing !== null} onOpenChange={(open) => !open && setViewing(null)}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-2xl">
          {viewing && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {viewing.period_type === "weekly" ? "周报" : "日报"} · {viewing.period_start.slice(0, 10)}
                </DialogTitle>
              </DialogHeader>
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7">{viewing.content}</pre>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
