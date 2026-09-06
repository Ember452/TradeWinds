import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { CalendarClock, Loader2, Pencil, Play, X } from "lucide-react";
import { api, ApiError } from "@/shared/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { PlanPreview } from "./PlanPreview";

interface Topic {
  id: number;
  name: string;
  description: string;
  cadence: "daily" | "weekly";
  status: "active" | "muted";
  plan: Record<string, unknown> | null;
}

interface RunResult {
  collected: number;
  new_items: number;
  accepted: number;
  rejected: number;
}

interface TopicHeaderProps {
  topic: Topic;
  onTopicChange: (topic: Topic) => void;
}

// 详情页头部:元信息、执行/退订/编辑操作、计划预览
export function TopicHeader({ topic, onTopicChange }: TopicHeaderProps) {
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [editing, setEditing] = useState(false);
  const [description, setDescription] = useState(topic.description);
  const [cadence, setCadence] = useState<"daily" | "weekly">(topic.cadence);

  async function handleRun() {
    setRunning(true);
    try {
      setRunResult(await api<RunResult>(`/api/v1/topics/${topic.id}/run`, { method: "POST" }));
      toast.success("执行完成");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "执行失败");
    } finally {
      setRunning(false);
    }
  }

  async function handleMute() {
    try {
      const updated = await api<Topic>(`/api/v1/topics/${topic.id}/mute`, { method: "POST" });
      onTopicChange(updated);
      toast.success(updated.status === "muted" ? "已退订,不再自动执行" : "已重新订阅");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "操作失败");
    }
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    try {
      const updated = await api<Topic>(`/api/v1/topics/${topic.id}`, {
        method: "PATCH",
        body: { description, cadence },
      });
      onTopicChange(updated);
      setEditing(false);
      toast.success("已保存,计划已重新编译");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "保存失败");
    }
  }

  return (
    <div className="mb-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">{topic.name}</h1>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <CalendarClock className="size-4" />
            {topic.cadence === "daily" ? "每天执行" : "每周执行"} ·
            {topic.status === "active" ? " 订阅中" : " 已退订"}
            {topic.status === "active" && <Badge className="bg-success/15 text-success hover:bg-success/15">运行中</Badge>}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleRun} disabled={running}>
            {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
            {running ? "执行中…" : "立即执行一次"}
          </Button>
          {topic.status === "active" && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline">退订</Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>确认退订「{topic.name}」?</AlertDialogTitle>
                  <AlertDialogDescription>
                    退订后不再自动执行与推送;条目数据保留,可随时重新订阅。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={handleMute}>确认退订</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
          <Button variant="ghost" onClick={() => setEditing(!editing)}>
            {editing ? <X className="size-4" /> : <Pencil className="size-4" />}
            {editing ? "取消编辑" : "编辑描述/频率"}
          </Button>
        </div>
      </div>

      {runResult && (
        <p className="mt-3 rounded-lg bg-primary/5 px-3 py-2 text-sm text-muted-foreground">
          执行完成:检索 {runResult.collected} 条,新增 {runResult.new_items} 条,采纳 {runResult.accepted} 条,
          拒绝 {runResult.rejected} 条。
        </p>
      )}

      {editing && (
        <Card className="mt-4">
          <CardContent className="p-4">
            <form onSubmit={handleSave} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="edit-desc">主题描述</Label>
                <Textarea
                  id="edit-desc"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  required
                  maxLength={2000}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="edit-cadence">更新频率</Label>
                <select
                  id="edit-cadence"
                  value={cadence}
                  onChange={(e) => setCadence(e.target.value as "daily" | "weekly")}
                  className="h-9 rounded-lg border border-input bg-surface px-3 text-sm"
                >
                  <option value="daily">每天</option>
                  <option value="weekly">每周</option>
                </select>
              </div>
              <Button type="submit" className="self-start">
                保存并重新编译计划
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="mt-4">
        <PlanPreview plan={topic.plan} />
      </div>
    </div>
  );
}
