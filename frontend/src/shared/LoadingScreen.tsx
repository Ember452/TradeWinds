import { motion, useReducedMotion } from "framer-motion";

// 全页加载态:晴空渐变 + 纸飞机轻浮动
export function LoadingScreen() {
  const reduce = useReducedMotion();
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-6"
      style={{ background: "linear-gradient(180deg, var(--c-sky-1) 0%, var(--c-sky-2) 55%, var(--c-sky-3) 100%)" }}
    >
      <motion.svg
        viewBox="0 0 24 24"
        className="size-16 drop-shadow-lg"
        animate={reduce ? undefined : { y: [0, -10, 0], rotate: [0, -6, 0] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <path d="M2 12 L22 3 L15 21 L11 14 Z" fill="#fff" stroke="rgba(30,60,120,.85)" strokeWidth="1" strokeLinejoin="round" />
      </motion.svg>
      <p className="text-sm font-medium text-white/90 drop-shadow">加载中…</p>
    </div>
  );
}
