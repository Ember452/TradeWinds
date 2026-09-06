// 检索计划预览:Planner 编译产物的人类可读摘要
export function PlanPreview({ plan }: { plan: Record<string, unknown> | null }) {
  if (!plan) return null;
  const keywords = (plan.keywords as string[]) ?? [];
  const sources = (plan.sources as string[]) ?? [];
  const criteria = ((plan.relevance_criteria as string[]) ?? []).join(";");

  return (
    <div className="rounded-xl border border-dashed border-primary/30 bg-primary/5 p-4 text-sm">
      <h4 className="mb-2 font-bold text-primary">检索计划预览</h4>
      <p className="text-foreground/90">
        <span className="text-muted-foreground">关键词:</span>
        {keywords.map((k) => (
          <span key={k} className="mx-0.5 inline-block rounded-md bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
            {k}
          </span>
        ))}
      </p>
      <p className="mt-1.5 text-foreground/90">
        <span className="text-muted-foreground">信息源:</span>
        {sources.join("、")}
      </p>
      <p className="mt-1.5 text-foreground/90">
        <span className="text-muted-foreground">时间窗:</span>
        {String(plan.window_days)} 天
      </p>
      <p className="mt-1.5 leading-relaxed text-foreground/90">
        <span className="text-muted-foreground">判定标准:</span>
        {criteria}
      </p>
      <p className="mt-2 text-xs text-muted-foreground">想调整?编辑主题描述或频率会触发 Planner 重新编译。</p>
    </div>
  );
}
