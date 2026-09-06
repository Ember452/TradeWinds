import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronLeft, SendHorizontal, Square } from "lucide-react";
import { api, ApiError, streamSSE } from "@/shared/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ChatMessage } from "./components/ChatMessage";
import { useAutoScroll } from "./components/useAutoScroll";

interface Citation {
  index: number;
  url: string;
}

interface Message {
  id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  citations: Citation[] | null;
  tool_trace: { tool: string }[] | null;
}

export function ChatPage() {
  const { conversationId } = useParams();
  const id = Number(conversationId);
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; citations: Citation[] | null }[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [interrupted, setInterrupted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const { containerRef } = useAutoScroll([messages]);

  const load = useCallback(() => {
    api<{ title: string; messages: Message[] }>(`/api/v1/conversations/${id}`)
      .then((detail) => {
        setTitle(detail.title);
        setMessages(
          detail.messages
            .filter((m) => m.role !== "tool")
            .map((m) => ({ role: m.role as "user" | "assistant", content: m.content, citations: m.citations })),
        );
      })
      .catch((err: ApiError) => setError(err.message));
  }, [id]);
  useEffect(load, [load]);

  const send = useCallback(
    async (content: string) => {
      setStreaming(true);
      setInterrupted(false);
      setError(null);
      setLastQuestion(content);
      setMessages((prev) => [...prev, { role: "user", content, citations: null }]);
      setMessages((prev) => [...prev, { role: "assistant", content: "", citations: null }]);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamSSE(
          `/api/v1/conversations/${id}/messages`,
          { content },
          (type, data) => {
            if (type === "delta") {
              const text = String(data.text ?? "");
              setMessages((prev) => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                copy[copy.length - 1] = { ...last, content: last.content + text };
                return copy;
              });
            } else if (type === "citations") {
              const citations = data.citations as Citation[];
              setMessages((prev) => {
                const copy = [...prev];
                const last = copy[copy.length - 1];
                copy[copy.length - 1] = { ...last, citations };
                return copy;
              });
            } else if (type === "error") {
              setError(String(data.message ?? "生成失败"));
            }
          },
          controller.signal,
        );
      } catch (err) {
        // 流式中断:显示可重试状态,已生成内容保留
        setInterrupted(true);
        setError(err instanceof ApiError ? err.message : "连接中断,回答可能不完整");
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [id],
  );

  async function handleSubmit() {
    const content = input.trim();
    if (!content || streaming) return;
    setInput("");
    await send(content);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  return (
    <div className="flex h-[calc(100vh-8.5rem)] flex-col">
      <p className="mb-2">
        <Link
          to="/chat"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" /> 全部对话
        </Link>
      </p>
      <h1 className="mb-3 truncate text-xl font-extrabold">{title}</h1>

      <div ref={containerRef} className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.map((m, i) => (
          <ChatMessage
            key={i}
            role={m.role}
            content={m.content}
            citations={m.citations}
            streaming={streaming && i === messages.length - 1 && m.role === "assistant"}
          />
        ))}
      </div>

      {interrupted && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => lastQuestion && send(lastQuestion)}>
            重新提问
          </Button>
        </div>
      )}
      {error && !interrupted && <p className="mt-3 text-sm text-danger">{error}</p>}

      <div className="sticky bottom-0 mt-3 flex items-end gap-2 bg-background/80 py-2 backdrop-blur">
        <Textarea
          placeholder={streaming ? "回答生成中…" : "问一个研究问题,如:近期值得关注的 Agent 评测框架?"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={streaming}
          rows={1}
          className="max-h-32 min-h-9 flex-1 resize-none"
        />
        {streaming ? (
          <Button variant="outline" size="icon" className="shrink-0" onClick={() => abortRef.current?.abort()} aria-label="停止生成">
            <Square className="size-4" />
          </Button>
        ) : (
          <Button size="icon" className="shrink-0" onClick={() => void handleSubmit()} disabled={!input.trim()} aria-label="发送">
            <SendHorizontal className="size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
