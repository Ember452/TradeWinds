import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MessagesSquare, Plus } from "lucide-react";
import { api } from "@/shared/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/shared/EmptyState";

interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

export function ChatListPage() {
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [title, setTitle] = useState("");
  const navigate = useNavigate();

  const load = useCallback(() => {
    api<Conversation[]>("/api/v1/conversations").then(setConversations).catch(() => setConversations([]));
  }, []);
  useEffect(load, [load]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const conversation = await api<Conversation>("/api/v1/conversations", {
      method: "POST",
      body: { title: title || "新对话" },
    });
    setTitle("");
    navigate(`/chat/${conversation.id}`);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold">对话研究</h1>
        <p className="mt-1 text-sm text-muted-foreground">像和研究员聊天一样追问,回答带编号引用</p>
      </div>

      <form onSubmit={handleSubmit} className="mb-6 flex gap-2">
        <Input
          placeholder="新对话标题(可选)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
        />
        <Button type="submit" className="shrink-0">
          <Plus className="size-4" /> 开始新对话
        </Button>
      </form>

      {conversations === null ? (
        <div className="space-y-3">
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-20 rounded-2xl" />
        </div>
      ) : conversations.length === 0 ? (
        <EmptyState
          icon={<MessagesSquare className="size-6" />}
          title="还没有对话"
          description="开始一个新对话,研究问题会由 Agent 检索多源信息后作答。"
        />
      ) : (
        <div className="space-y-3">
          {conversations.map((c) => (
            <Card key={c.id} className="transition-all hover:-translate-y-0.5 hover:shadow-md">
              <CardContent className="p-4">
                <Link to={`/chat/${c.id}`} className="font-semibold hover:text-primary">
                  {c.title}
                </Link>
                <p className="mt-1 text-xs text-muted-foreground">{new Date(c.created_at).toLocaleString()}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
