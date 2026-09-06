import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api, ApiError } from "@/shared/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TopicHeader } from "./components/TopicHeader";
import { FeedPanel } from "./components/FeedPanel";
import { ReportsPanel } from "./components/ReportsPanel";
import { FeedsPanel } from "./components/FeedsPanel";

interface Topic {
  id: number;
  name: string;
  description: string;
  cadence: "daily" | "weekly";
  status: "active" | "muted";
  plan: Record<string, unknown> | null;
}

export function TopicDetailPage() {
  const { topicId } = useParams();
  const id = Number(topicId);
  const [topic, setTopic] = useState<Topic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [minScore, setMinScore] = useState<number | null>(null);

  const load = useCallback(() => {
    api<Topic>(`/api/v1/topics/${id}`)
      .then(setTopic)
      .catch((err: ApiError) => setError(err.message));
  }, [id]);

  useEffect(load, [load]);

  if (!topic) return <p className="py-12 text-center text-muted-foreground">{error ?? "加载中…"}</p>;

  return (
    <div>
      <p className="mb-4">
        <Link
          to="/topics"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" /> 全部主题
        </Link>
      </p>

      <TopicHeader topic={topic} onTopicChange={setTopic} />

      <Tabs defaultValue="feed">
        <TabsList>
          <TabsTrigger value="feed">信息流</TabsTrigger>
          <TabsTrigger value="reports">周期报告</TabsTrigger>
          <TabsTrigger value="feeds">订阅源</TabsTrigger>
        </TabsList>
        <TabsContent value="feed" className="mt-6">
          <FeedPanel topicId={id} minScore={minScore} onMinScoreChange={setMinScore} />
        </TabsContent>
        <TabsContent value="reports" className="mt-6">
          <ReportsPanel topicId={id} />
        </TabsContent>
        <TabsContent value="feeds" className="mt-6">
          <FeedsPanel topicId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
