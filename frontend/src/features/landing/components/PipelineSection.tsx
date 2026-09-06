import { motion, useReducedMotion } from "framer-motion";
import { Mail, Rss, Gauge } from "lucide-react";

const STEPS = [
  { icon: Rss, title: "1 · 订阅主题", text: "用一句话描述你想长期追踪的领域,AI 编译成检索计划:关键词、信息源、时间窗、判定标准。" },
  { icon: Gauge, title: "2 · 检索与评分", text: "管道定时横扫 arXiv、Hacker News、GitHub 与你的 RSS,逐条打分、聚类、写摘要与推荐理由。" },
  { icon: Mail, title: "3 · 简报送达", text: "高分条目即时推送,每日/每周聚合成一份简报邮件——把一周噪音压缩成一页精华。" },
];

export function PipelineSection() {
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto max-w-5xl px-4 py-24">
      <h2 className="text-center text-3xl font-extrabold">它如何工作</h2>
      <p className="mt-3 text-center text-muted-foreground">一条全自动的情报管道,你只需要描述关心什么</p>
      <div className="mt-14 grid gap-6 md:grid-cols-3">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            className="relative rounded-2xl border border-border-soft bg-surface p-6 shadow-sm"
            initial={reduce ? false : { opacity: 0, y: 32 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5, delay: i * 0.15, ease: "easeOut" }}
          >
            <div className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <step.icon className="size-5" />
            </div>
            <h3 className="mt-4 text-lg font-bold">{step.title}</h3>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.text}</p>
            {i < STEPS.length - 1 && (
              <div className="absolute -right-3 top-1/2 hidden h-px w-6 border-t-2 border-dashed border-primary/40 md:block" />
            )}
          </motion.div>
        ))}
      </div>
    </section>
  );
}
