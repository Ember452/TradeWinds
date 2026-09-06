import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Inbox, Plus } from "lucide-react";
import { api } from "@/shared/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/shared/EmptyState";
import { CreateTopicDialog } from "./components/CreateTopicDialog";

interface Topic {
  id: number;
  name: string;
  description: string;
  cadence: "daily" | "weekly";
  status: "active" | "muted";
  plan: Record<string, unknown> | null;
}

export function TopicsPage() {
  const [topics, setTopics] = useState<Topic[] | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(() => {
    api<Topic[]>("/api/v1/topics").then(setTopics).catch(() => setTopics([]));
  }, []);

  useEffect(load, [load]);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold">我的主题</h1>
          <p className="mt-1 text-sm text-muted-foreground">每个主题是一条自动运转的情报管道</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> 新建主题
        </Button>
      </div>

      {topics === null ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-36 rounded-2xl" />
          <Skeleton className="h-36 rounded-2xl" />
          <Skeleton className="h-36 rounded-2xl" />
        </div>
      ) : topics.length === 0 ? (
        <EmptyState
          icon={<Inbox className="size-6" />}
          title="还没有主题"
          description="创建第一个订阅,让情报开始飞。AI 会把你的描述编译成检索计划,自动追踪相关内容。"
          action={
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" /> 新建主题
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {topics.map((topic) => (
            <Card key={topic.id} className="group transition-all hover:-translate-y-0.5 hover:shadow-md">
              <CardContent className="flex h-full flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <Link to={`/topics/${topic.id}`} className="text-lg font-bold hover:text-primary">
                    {topic.name}
                  </Link>
                  <div className="flex shrink-0 gap-1.5">
                    <Badge variant="secondary">{topic.cadence === "daily" ? "每天" : "每周"}</Badge>
                    {topic.status === "active" ? (
                      <Badge className="bg-success/15 text-success hover:bg-success/15">订阅中</Badge>
                    ) : (
                      <Badge variant="outline">已退订</Badge>
                    )}
                  </div>
                </div>
                <p className="mt-2 line-clamp-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                  {topic.description}
                </p>
                <Link
                  to={`/topics/${topic.id}`}
                  className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
                >
                  进入主题
                  <ArrowUpRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateTopicDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={load} />
    </div>
  );
}
