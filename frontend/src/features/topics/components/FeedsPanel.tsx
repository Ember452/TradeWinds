import { useCallback, useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/shared/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

interface FeedSource {
  id: number;
  title: string;
  url: string;
  status: "healthy" | "broken";
  last_checked_at: string | null;
}

export function FeedsPanel({ topicId }: { topicId: number }) {
  const [feeds, setFeeds] = useState<FeedSource[]>([]);
  const [url, setUrl] = useState("");

  const load = useCallback(() => {
    api<FeedSource[]>(`/api/v1/topics/${topicId}/feeds`).then(setFeeds).catch(() => undefined);
  }, [topicId]);
  useEffect(load, [load]);

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    try {
      await api(`/api/v1/topics/${topicId}/feeds`, { method: "POST", body: { url } });
      setUrl("");
      toast.success("订阅源已添加");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "添加失败");
    }
  }

  async function handleDelete(feedId: number) {
    await api(`/api/v1/topics/${topicId}/feeds/${feedId}`, { method: "DELETE" }).catch(() => undefined);
    toast.success("订阅源已删除");
    load();
  }

  return (
    <div>
      <h2 className="mb-4 font-bold">自定义订阅源</h2>
      <p className="mb-3 text-sm text-muted-foreground">
        提交 RSS/Atom 地址,创建时校验有效性,每日自动复检;broken 源仍会尝试抓取并标注降级。
      </p>
      <form onSubmit={handleAdd} className="mb-4 flex gap-2">
        <Input
          placeholder="https://example.com/feed.xml"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          minLength={8}
          maxLength={2048}
        />
        <Button type="submit" className="shrink-0">
          <Plus className="size-4" /> 添加
        </Button>
      </form>
      {feeds.length > 0 && (
        <ul className="space-y-2">
          {feeds.map((feed) => (
            <li
              key={feed.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-border-soft bg-surface px-4 py-3"
            >
              <div className="min-w-0">
                <a href={feed.url} target="_blank" rel="noreferrer" className="truncate font-medium hover:text-primary">
                  {feed.title}
                </a>
                <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span className={`inline-block size-1.5 rounded-full ${feed.status === "healthy" ? "bg-success" : "bg-danger"}`} />
                  {feed.status === "healthy" ? "正常" : "异常"}
                  {feed.last_checked_at && ` · 复检于 ${new Date(feed.last_checked_at).toLocaleDateString()}`}
                </p>
              </div>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="删除订阅源">
                    <Trash2 className="size-4 text-muted-foreground hover:text-danger" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>删除订阅源「{feed.title}」?</AlertDialogTitle>
                    <AlertDialogDescription>删除后该源不再参与此主题的检索。</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>取消</AlertDialogCancel>
                    <AlertDialogAction onClick={() => handleDelete(feed.id)}>确认删除</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
