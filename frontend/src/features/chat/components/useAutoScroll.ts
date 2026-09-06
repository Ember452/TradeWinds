import { useCallback, useEffect, useRef } from "react";
import type { RefObject } from "react";

const STICKY_THRESHOLD = 120; // 距底超过该值视为用户主动上滚,不强制拉回

// 消息区自动滚底:内容变化时平滑滚动;用户上滚阅读历史时不打断
export function useAutoScroll(deps: unknown[]): { containerRef: RefObject<HTMLDivElement | null>; scrollToBottom: () => void } {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stickyRef = useRef(true);

  const scrollToBottom = useCallback((smooth = true) => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => {
      stickyRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICKY_THRESHOLD;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (stickyRef.current) scrollToBottom();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { containerRef, scrollToBottom: () => scrollToBottom() };
}
