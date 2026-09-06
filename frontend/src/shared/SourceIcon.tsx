import { FileText, Flame, GitBranch, Globe, Rss } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const SOURCE_META: Record<string, { icon: LucideIcon; label: string }> = {
  arxiv: { icon: FileText, label: "arXiv" },
  hackernews: { icon: Flame, label: "Hacker News" },
  github: { icon: GitBranch, label: "GitHub" },
  rss: { icon: Rss, label: "RSS" },
};

// 来源标识:arxiv/hackernews/github/rss,未知来源用地球兜底
export function SourceIcon({ source, withLabel = false }: { source: string; withLabel?: boolean }) {
  const meta = SOURCE_META[source] ?? { icon: Globe, label: source };
  const Icon = meta.icon;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground" title={meta.label}>
      <Icon className="size-3.5" />
      {withLabel && meta.label}
    </span>
  );
}
