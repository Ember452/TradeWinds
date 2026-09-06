import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, streamSSE } from "../../shared/api";

interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

interface Message {
  id: number;
  role: "user" | "assistant" | "tool";
  content: string;
  citations: { index: number; url: string }[] | null;
  tool_trace: { tool: string }[] | null;
}

export function ChatListPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [title, setTitle] = useState("");
  const navigate = useNavigate();

  const load = useCallback(() => {
    api<Conversation[]>("/api/v1/conversations").then(setConversations).catch(() => undefined);
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
      <h1>对话研究</h1>
      <form onSubmit={handleSubmit} className="topic-form">
        <input
          placeholder="新对话标题(可选)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
        />
        <button type="submit">开始新对话</button>
      </form>
      <ul className="topic-list">
        {conversations.map((c) => (
          <li key={c.id} className="card">
            <Link to={`/chat/${c.id}`}>{c.title}</Link>
            <span className="meta">{new Date(c.created_at).toLocaleString()}</span>
          </li>
        ))}
      </ul>
      {conversations.length === 0 && <p className="empty">还没有对话。</p>}
    </div>
  );
}

interface Citation {
  index: number;
  url: string;
}

export function ChatPage() {
  const { conversationId } = useParams();
  const id = Number(conversationId);
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string; citations: Citation[] | null }[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [interrupted, setInterrupted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);

  const load = useCallback(() => {
    api<{ title: string; messages: Message[] }>(`/api/v1/conversations/${id}`)
      .then((detail) => {
        setTitle(detail.title);
        setMessages(
          detail.messages
            .filter((m) => m.role !== "tool")
            .map((m) => ({ role: m.role, content: m.content, citations: m.citations })),
        );
      })
      .catch((err: ApiError) => setError(err.message));
  }, [id]);
  useEffect(load, [load]);

  async function send(content: string) {
    setStreaming(true);
    setInterrupted(false);
    setError(null);
    setLastQuestion(content);
    setMessages((prev) => [...prev, { role: "user", content, citations: null }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "", citations: null }]);

    try {
      await streamSSE(`/api/v1/conversations/${id}/messages`, { content }, (type, data) => {
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
      });
    } catch (err) {
      // 流式中断:显示可重试状态,已生成内容保留
      setInterrupted(true);
      setError(err instanceof ApiError ? err.message : "连接中断,回答可能不完整");
    } finally {
      setStreaming(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const content = input.trim();
    if (!content || streaming) return;
    setInput("");
    await send(content);
  }

  return (
    <div className="chat-page">
      <p className="breadcrumb">
        <Link to="/chat">← 全部对话</Link>
      </p>
      <h1>{title}</h1>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="bubble">
              <Markdownish text={m.content} citations={m.citations} />
            </div>
            {m.role === "assistant" && m.citations && m.citations.length > 0 && (
              <ol className="citations">
                {m.citations.map((c) => (
                  <li key={c.index}>
                    <a href={c.url} target="_blank" rel="noreferrer">
                      {c.url}
                    </a>
                  </li>
                ))}
              </ol>
            )}
          </div>
        ))}
      </div>

      {interrupted && (
        <div className="retry-hint">
          <span>{error}</span>
          <button type="button" onClick={() => lastQuestion && send(lastQuestion)}>
            重新提问
          </button>
        </div>
      )}
      {error && !interrupted && <p className="error">{error}</p>}

      <form onSubmit={handleSubmit} className="chat-input">
        <input
          placeholder={streaming ? "回答生成中…" : "问一个研究问题,如:近期值得关注的 Agent 评测框架?"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={streaming}
          maxLength={4000}
        />
        <button type="submit" disabled={streaming || !input.trim()}>
          发送
        </button>
      </form>
    </div>
  );
}

/** 轻量渲染:把 [n] 替换为悬浮显示原文链接的引用上标,其余按纯文本+换行。 */
function Markdownish({ text, citations }: { text: string; citations: Citation[] | null }) {
  const parts = text.split(/(\[\d+\])/g);
  const citationFor = (label: string) => {
    const index = Number(label.slice(1, -1));
    return citations?.find((c) => c.index === index);
  };
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[\d+\]$/);
        if (match) {
          const citation = citationFor(part);
          if (citation) {
            return (
              <a
                key={i}
                className="citation-mark"
                href={citation.url}
                target="_blank"
                rel="noreferrer"
                title={citation.url}
              >
                [{citation.index}]
              </a>
            );
          }
          return <span key={i}>{part}</span>;
        }
        return (
          <span key={i}>
            {part.split("\n").map((line, j, arr) => (
              <span key={j}>
                {line}
                {j < arr.length - 1 && <br />}
              </span>
            ))}
          </span>
        );
      })}
    </>
  );
}
