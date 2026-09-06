import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}

// 通用空状态:圆底图标 + 标题 + 描述 + 可选行动按钮
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-soft bg-surface-strong px-6 py-14 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">{icon}</div>
      <h3 className="mt-4 font-bold text-foreground">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
