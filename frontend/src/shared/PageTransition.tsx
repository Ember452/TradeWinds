import { motion } from "framer-motion";
import type { ReactNode } from "react";

// 页面切换过渡:淡入上移;prefers-reduced-motion 下由全局 CSS 降级
export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
