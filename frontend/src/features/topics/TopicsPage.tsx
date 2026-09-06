import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../shared/api";

interface Topic {
  id: number;
  name: string;
  description: string;
  cadence: "daily" | "weekly";
  status: "active" | "muted";
  plan: Record<string, unknown> | null;
}

interface TopicCreated {
  topic: Topic;
  plan: Record<string, unknown>;
}

export function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cadence, setCadence] = useState<"daily" | "weekly">("daily");
  const [created, setCreated] = useState<TopicCreated | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(() => {
    api<Topic[]>("/api/v1/topics")
      .then(setTopics)
      .catch((err: ApiError) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await api<TopicCreated>("/api/v1/topics", {
        method: "POST",
        body: { name, description, cadence },
      });
      setCreated(result);
      setName("");
      setDescription("");
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "网络错误");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>我的主题</h1>

      <section className="card">
        <h2>新建主题</h2>
        <form onSubmit={handleSubmit} className="topic-form">
          <input
            placeholder="主题名称,如:AI Agent 动态"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
          />
          <textarea
            placeholder="想长期关注什么?如:近一周 LLM Agent 领域的新技术与开源项目"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            maxLength={2000}
            rows={3}
          />
          <select value={cadence} onChange={(e) => setCadence(e.target.value as "daily" | "weekly")}>
            <option value="daily">每天</option>
            <option value="weekly">每周</option>
          </select>
          <button type="submit" disabled={submitting}>
            {submitting ? "编译检索计划中…" : "创建"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
        {created && <PlanPreview plan={created.plan} />}
      </section>

      {topics.length === 0 ? (
        <p className="empty">还没有主题,创建第一个吧。</p>
      ) : (
        <ul className="topic-list">
          {topics.map((topic) => (
            <li key={topic.id} className="card">
              <Link to={`/topics/${topic.id}`} className="topic-link">
                <strong>{topic.name}</strong>
                <span className="meta">
                  {topic.cadence === "daily" ? "每天" : "每周"} ·{" "}
                  {topic.status === "active" ? "订阅中" : "已退订"}
                </span>
                <p>{topic.description}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PlanPreview({ plan }: { plan: Record<string, unknown> | null }) {
  if (!plan) return null;
  const keywords = (plan.keywords as string[]) ?? [];
  const sources = (plan.sources as string[]) ?? [];
  return (
    <div className="plan-preview">
      <h3>检索计划预览</h3>
      <p>
        关键词:{keywords.join("、")}
      </p>
      <p>信息源:{sources.join("、")}</p>
      <p>时间窗:{String(plan.window_days)} 天</p>
      <p>
        判定标准:{" "}
        {((plan.relevance_criteria as string[]) ?? []).join(";")}
      </p>
      <p className="hint">
        想调整?编辑主题描述或频率会触发 Planner 重新编译。
      </p>
    </div>
  );
}
