import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { ArrowLeft, Loader2 } from "lucide-react";
import { api, ApiError } from "@/shared/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PlanPreview } from "./PlanPreview";

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

interface CreateTopicDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

// 两步创建:填写 → 计划预览确认
export function CreateTopicDialog({ open, onOpenChange, onCreated }: CreateTopicDialogProps) {
  const [step, setStep] = useState<"form" | "confirm">("form");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cadence, setCadence] = useState<"daily" | "weekly">("daily");
  const [created, setCreated] = useState<TopicCreated | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setStep("form");
    setName("");
    setDescription("");
    setCadence("daily");
    setCreated(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const result = await api<TopicCreated>("/api/v1/topics", {
        method: "POST",
        body: { name, description, cadence },
      });
      setCreated(result);
      setStep("confirm");
      onCreated();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "创建失败,请稍后再试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {step === "form" ? (
          <>
            <DialogHeader>
              <DialogTitle>新建主题</DialogTitle>
              <DialogDescription>用一句话描述想长期关注什么,Planner 会编译出检索计划。</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="topic-name">主题名称</Label>
                <Input
                  id="topic-name"
                  placeholder="如:AI Agent 动态"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={200}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="topic-desc">关注什么?</Label>
                <Textarea
                  id="topic-desc"
                  placeholder="如:近一周 LLM Agent 领域的新技术与开源项目"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                  maxLength={2000}
                  rows={3}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="topic-cadence">更新频率</Label>
                <select
                  id="topic-cadence"
                  value={cadence}
                  onChange={(e) => setCadence(e.target.value as "daily" | "weekly")}
                  className="h-9 rounded-lg border border-input bg-surface px-3 text-sm"
                >
                  <option value="daily">每天</option>
                  <option value="weekly">每周</option>
                </select>
              </div>
              <DialogFooter>
                <Button type="submit" disabled={submitting}>
                  {submitting && <Loader2 className="size-4 animate-spin" />}
                  {submitting ? "编译检索计划中…" : "编译检索计划"}
                </Button>
              </DialogFooter>
            </form>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>确认检索计划</DialogTitle>
              <DialogDescription>这是 Planner 根据你的描述编译的计划,确认后主题开始生效。</DialogDescription>
            </DialogHeader>
            <PlanPreview plan={created?.plan ?? null} />
            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  reset();
                  setStep("form");
                }}
              >
                <ArrowLeft className="size-4" /> 返回修改
              </Button>
              <Button
                type="button"
                onClick={() => {
                  toast.success("主题已创建");
                  reset();
                  onOpenChange(false);
                }}
              >
                确认创建
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
