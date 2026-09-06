import { useCallback, useEffect, useRef, useState } from "react";
import { Plane } from "lucide-react";
import { api, ApiError } from "@/shared/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/shared/EmptyState";
import { ScoreBadge } from "@/shared/ScoreBadge";
import { SourceIcon } from "@/shared/SourceIcon";

interface Item {
  id: number;
  source: string;
  url: string;
  title: string;
  summary: string | null;
  reason: string | null;
  score: number | null;
  published_at: string | null;
}

interface FeedPage {
  items: Item[];
  next_cursor: number | null;
}

const PAGE_SIZE = 10;

interface FeedPanelProps {
  topicId: number;
  minScore: number | null;
  onMinScoreChange: (v: number | null) => void;
}

// 信息流:评分筛选 + 游标无限滚动;点击条目 fire-and-forget 上报偏好信号
export function FeedPanel({ topicId, minScore, onMinScoreChange }: FeedPanelProps) {
  const [items, setItems] = useState<Item[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const loadPage = useCallback(
    async (cursorValue: number | null) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
        if (cursorValue !== null) params.set("cursor", String(cursorValue));
        if (minScore !== null) params.set("min_score", String(minScore));
        const page = await api<FeedPage>(`/api/v1/topics/${topicId}/items?${params}`);
        setItems((prev) => (cursorValue === null ? page.items : [...prev, ...page.items]));
        setCursor(page.next_cursor);
        setHasMore(page.next_cursor !== null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "加载失败");
      } finally {
        setLoading(false);
        setInitialLoading(false);
      }
    },
    [topicId, minScore],
  );

  useEffect(() => {
    setItems([]);
    setHasMore(true);
    setInitialLoading(true);
    loadPage(null);
  }, [loadPage]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && cursor !== null) loadPage(cursor);
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, cursor, loadPage]);

  if (initialLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-bold">信息流</h2>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          最低评分
          <select
            value={minScore ?? ""}
            onChange={(e) => onMinScoreChange(e.target.value === "" ? null : Number(e.target.value))}
            className="h-8 rounded-lg border border-input bg-surface px-2 text-sm"
          >
            <option value="">全部</option>
            <option value="6">6+</option>
            <option value="8">8+</option>
          </select>
        </label>
      </div>

      {items.length === 0 && !loading ? (
        <EmptyState
          icon={<Plane className="size-6" />}
          title="暂无内容"
          description="执行一次主题,让第一批情报飞进来。"
        />
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <Card key={item.id} className="transition-all hover:-translate-y-0.5 hover:shadow-md">
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => {
                      // 点击即偏好信号:静默上报,失败不打扰用户
                      api(`/api/v1/items/${item.id}/click`, { method: "POST" }).catch(() => undefined);
                    }}
                    className="font-semibold leading-snug hover:text-primary"
                  >
                    {item.title}
                  </a>
                  <ScoreBadge score={item.score} />
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <SourceIcon source={item.source} withLabel />
                  {item.published_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(item.published_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                {item.summary && <p className="mt-3 text-sm leading-relaxed text-foreground/90">{item.summary}</p>}
                {item.reason && (
                  <p className="mt-3 border-l-2 border-accent/50 pl-3 text-sm leading-relaxed text-muted-foreground">
                    <span className="font-medium text-warning">推荐理由:</span>
                    {item.reason}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-sm text-danger">{error}</p>}
      {loading && !initialLoading && <p className="mt-3 text-center text-sm text-muted-foreground">加载中…</p>}
      <div ref={sentinelRef} />
    </div>
  );
}
