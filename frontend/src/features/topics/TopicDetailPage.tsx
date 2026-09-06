import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../../shared/api";
import { PlanPreview } from "./TopicsPage";

interface Topic {
  id: number;
  name: string;
  description: string;
  cadence: "daily" | "weekly";
  status: "active" | "muted";
  plan: Record<string, unknown> | null;
}

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

interface RunResult {
  collected: number;
  new_items: number;
  accepted: number;
  rejected: number;
}

const PAGE_SIZE = 10;

export function TopicDetailPage() {
  const { topicId } = useParams();
  const id = Number(topicId);
  const [topic, setTopic] = useState<Topic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [editing, setEditing] = useState(false);
  const [description, setDescription] = useState("");
  const [cadence, setCadence] = useState<"daily" | "weekly">("daily");
  const [minScore, setMinScore] = useState<number | null>(null);

  const load = useCallback(() => {
    api<Topic>(`/api/v1/topics/${id}`)
      .then((t) => {
        setTopic(t);
        setDescription(t.description);
        setCadence(t.cadence);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [id]);

  useEffect(load, [load]);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      setRunResult(await api<RunResult>(`/api/v1/topics/${id}/run`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "网络错误");
    } finally {
      setRunning(false);
    }
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    try {
      setTopic(
        await api<Topic>(`/api/v1/topics/${id}`, {
          method: "PATCH",
          body: { description, cadence },
        }),
      );
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "网络错误");
    }
  }

  async function handleMute() {
    const updated = await api<Topic>(`/api/v1/topics/${id}/mute`, { method: "POST" });
    setTopic(updated);
  }

  if (!topic) return <p className="loading">{error ?? "加载中…"}</p>;

  return (
    <div>
      <p className="breadcrumb">
        <Link to="/">← 全部主题</Link>
      </p>
      <h1>{topic.name}</h1>
      <p className="meta">
        {topic.cadence === "daily" ? "每天" : "每周"} ·{" "}
        {topic.status === "active" ? "订阅中" : "已退订"}
      </p>
      {error && <p className="error">{error}</p>}

      <div className="actions">
        <button type="button" onClick={handleRun} disabled={running}>
          {running ? "执行中…" : "立即执行一次"}
        </button>
        {topic.status === "active" && (
          <button type="button" onClick={handleMute} className="secondary">
            退订
          </button>
        )}
        <button type="button" onClick={() => setEditing(!editing)} className="secondary">
          {editing ? "取消编辑" : "编辑描述/频率"}
        </button>
      </div>
      {runResult && (
        <p className="hint">
          执行完成:检索 {runResult.collected} 条,新增 {runResult.new_items} 条,采纳{" "}
          {runResult.accepted} 条,拒绝 {runResult.rejected} 条。
        </p>
      )}

      {editing && (
        <form onSubmit={handleSave} className="card topic-form">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            required
            maxLength={2000}
          />
          <select value={cadence} onChange={(e) => setCadence(e.target.value as "daily" | "weekly")}>
            <option value="daily">每天</option>
            <option value="weekly">每周</option>
          </select>
          <button type="submit">保存并重新编译计划</button>
        </form>
      )}

      <PlanPreview plan={topic.plan} />

      <ReportsPanel topicId={id} />

      <Feed topicId={id} minScore={minScore} onMinScoreChange={setMinScore} />
    </div>
  );
}

interface Report {
  id: number;
  period_type: "daily" | "weekly";
  period_start: string;
  period_end: string;
  item_count: number;
  content: string;
}

function ReportsPanel({ topicId }: { topicId: number }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [shareLink, setShareLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Report[]>(`/api/v1/topics/${topicId}/reports`)
      .then(setReports)
      .catch((err: ApiError) => setError(err.message));
  }, [topicId]);
  useEffect(load, [load]);

  async function handleShare(reportId: number) {
    try {
      const result = await api<{ share_path: string }>(`/api/v1/reports/${reportId}/share`, {
        method: "POST",
      });
      setShareLink(`${window.location.origin}${result.share_path}`);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "网络错误");
    }
  }

  return (
    <section className="card">
      <h2>周期报告</h2>
      {reports.length === 0 && <p className="meta">执行主题后自动按频率聚合生成日报/周报。</p>}
      <ul className="feed-list">
        {reports.map((report) => (
          <li key={report.id} className="item-card">
            <div className="item-head">
              <strong>
                {report.period_type === "weekly" ? "周报" : "日报"} ·{" "}
                {report.period_start.slice(0, 10)}
              </strong>
              <span className="meta">{report.item_count} 条</span>
            </div>
            <div className="actions">
              <button type="button" className="secondary" onClick={() => handleShare(report.id)}>
                生成分享链接
              </button>
            </div>
          </li>
        ))}
      </ul>
      {shareLink && (
        <p className="hint">
          分享链接:<a href={shareLink} target="_blank" rel="noreferrer">{shareLink}</a>
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function Feed({
  topicId,
  minScore,
  onMinScoreChange,
}: {
  topicId: number;
  minScore: number | null;
  onMinScoreChange: (v: number | null) => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(true);
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
        setItems((prev) =>
          cursorValue === null ? page.items : [...prev, ...page.items],
        );
        setCursor(page.next_cursor);
        setHasMore(page.next_cursor !== null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "网络错误");
      } finally {
        setLoading(false);
      }
    },
    [topicId, minScore],
  );

  useEffect(() => {
    setItems([]);
    setHasMore(true);
    loadPage(null);
  }, [loadPage]);

  // 无限滚动:哨兵元素进入视口时加载下一页
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && cursor !== null) loadPage(cursor);
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, cursor, loadPage]);

  return (
    <section>
      <div className="feed-header">
        <h2>Feed</h2>
        <label className="meta">
          最低评分
          <select
            value={minScore ?? ""}
            onChange={(e) => onMinScoreChange(e.target.value === "" ? null : Number(e.target.value))}
          >
            <option value="">全部</option>
            <option value="6">6+</option>
            <option value="8">8+</option>
          </select>
        </label>
      </div>
      {items.length === 0 && !loading && <p className="empty">暂无内容,执行一次主题试试。</p>}
      <ul className="feed-list">
        {items.map((item) => (
          <li key={item.id} className="card item-card">
            <div className="item-head">
              <a href={item.url} target="_blank" rel="noreferrer">
                {item.title}
              </a>
              {item.score !== null && <span className="score">{item.score.toFixed(1)}</span>}
            </div>
            <p className="meta">来源:{item.source}</p>
            {item.summary && <p>{item.summary}</p>}
            {item.reason && <p className="reason">推荐理由:{item.reason}</p>}
          </li>
        ))}
      </ul>
      {error && <p className="error">{error}</p>}
      {loading && <p className="loading">加载中…</p>}
      <div ref={sentinelRef} />
    </section>
  );
}
