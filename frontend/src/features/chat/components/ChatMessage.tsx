import { motion, useReducedMotion } from "framer-motion";
import { CitationText } from "./CitationText";

interface Citation {
  index: number;
  url: string;
}

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  streaming?: boolean;
}

// 单条消息气泡;streaming 为真时尾部显示三点打字指示
export function ChatMessage({ role, content, citations, streaming = false }: ChatMessageProps) {
  const reduce = useReducedMotion();
  const isUser = role === "user";

  return (
    <motion.div
      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div
        className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser ? "rounded-br-sm bg-primary text-primary-foreground" : "rounded-bl-sm border border-border-soft bg-surface"
        }`}
      >
        {isUser ? content : <CitationText text={content} citations={citations} />}
        {streaming && (
          <span className="ml-1 inline-flex translate-y-0.5 items-center gap-0.5">
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="inline-block size-1 rounded-full bg-muted-foreground"
                animate={{ opacity: [0.2, 1, 0.2] }}
                transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </span>
        )}
      </div>
      {!isUser && citations && citations.length > 0 && (
        <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-xs text-muted-foreground">
          {citations.map((c) => (
            <li key={c.index}>
              <a href={c.url} target="_blank" rel="noreferrer" className="break-all hover:text-primary hover:underline">
                {c.url}
              </a>
            </li>
          ))}
        </ol>
      )}
    </motion.div>
  );
}
