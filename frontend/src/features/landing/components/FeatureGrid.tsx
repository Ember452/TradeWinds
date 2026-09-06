import { motion, useReducedMotion } from "framer-motion";
import { Rss, Gauge, Mail, MessageCircle, Search, Brain } from "lucide-react";

const FEATURES = [
  { icon: Rss, title: "多源聚合", text: "arXiv、Hacker News、GitHub 一网打尽,还支持自定义 RSS 源。" },
  { icon: Gauge, title: "AI 评分与聚类", text: "每条内容 0-10 分并自动聚类,高分精华浮出水面,低分噪音沉底。" },
  { icon: Mail, title: "周期报告", text: "日报周报自动聚合,一键生成公开分享链接,可推送进邮箱。" },
  { icon: MessageCircle, title: "对话研究", text: "像和研究员聊天一样追问,回答带编号引用,可回溯原文。" },
  { icon: Search, title: "已读检索", text: "看过的内容自动生成向量索引,随时用自然语言找回。" },
  { icon: Brain, title: "偏好记忆", text: "你的点击会沉淀为偏好画像,让后续推荐越来越懂你。" },
];

export function FeatureGrid() {
  const reduce = useReducedMotion();

  return (
    <section className="bg-surface-strong py-24">
      <div className="mx-auto max-w-5xl px-4">
        <h2 className="text-center text-3xl font-extrabold">为长期追踪而生</h2>
        <p className="mt-3 text-center text-muted-foreground">不只是搜索一次,而是一个持续运转的情报体系</p>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              className="rounded-2xl border border-border-soft bg-surface p-6 shadow-sm transition-shadow hover:shadow-md"
              initial={reduce ? false : { opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.45, delay: (i % 3) * 0.1, ease: "easeOut" }}
            >
              <div className="flex size-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
                <feature.icon className="size-5" />
              </div>
              <h3 className="mt-4 font-bold">{feature.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{feature.text}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
