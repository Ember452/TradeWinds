import { cn } from "@/lib/utils";

// 评分徽章三档:≥8 强调(琥珀)、≥6 中性(蓝)、其余弱化(灰)
export function ScoreBadge({ score, className }: { score: number | null; className?: string }) {
  if (score === null) return null;
  const tier =
    score >= 8
      ? "border-accent/40 bg-accent/15 text-accent"
      : score >= 6
        ? "border-primary/30 bg-primary/10 text-primary"
        : "border-border-soft bg-muted text-muted-foreground";
  return (
    <span
      className={cn("inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 text-xs font-bold tabular-nums", tier, className)}
    >
      {score.toFixed(1)}
    </span>
  );
}
