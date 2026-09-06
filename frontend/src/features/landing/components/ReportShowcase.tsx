import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Sailboat } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";

export function ReportShowcase() {
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto max-w-5xl px-4 py-24">
      <div className="grid items-center gap-12 md:grid-cols-2">
        <motion.div
          initial={reduce ? false : { opacity: 0, x: -24 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <h2 className="text-3xl font-extrabold leading-snug">每周一封信,<br />把一周噪音压成一页精华</h2>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            周期报告按主题自动聚合:统计区间、采纳条数、核心动态、值得关注的趋势。
            支持生成公开分享链接——下面就是一份真实结构的示例。
          </p>
          <Link
            to="/share/reports/mock-share-token"
            className="mt-6 inline-flex items-center gap-1.5 font-semibold text-primary hover:underline"
          >
            阅读公开示例 <ArrowRight className="size-4" />
          </Link>
        </motion.div>

        <motion.div
          className="rounded-2xl border border-border-soft bg-surface p-6 shadow-xl"
          initial={reduce ? false : { opacity: 0, x: 24, rotate: 1 }}
          whileInView={{ opacity: 1, x: 0, rotate: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.55, ease: "easeOut" }}
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 font-bold">
              <Sailboat className="size-4 text-primary" /> AI Agent 动态
            </span>
            <Badge>周报</Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">2026-08-31 ~ 2026-09-06 · 8 条</p>
          <div className="mt-4 space-y-3 border-t border-border-soft pt-4 text-sm leading-relaxed">
            <p><span className="font-semibold text-primary">核心动态:</span>LangGraph 1.0 发布,图编排成为默认形态;</p>
            <p><span className="font-semibold text-primary">评测进展:</span>ToolBench-2 补齐多步工具链评测空白;</p>
            <p><span className="font-semibold text-primary">建议关注:</span>Deep Research 失败模式分析对降级设计有直接借鉴意义。</p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
