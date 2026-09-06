import { Sailboat } from "lucide-react";
import { Link } from "react-router-dom";

export function SiteFooter() {
  return (
    <footer className="border-t border-border-soft bg-surface-strong py-10">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 px-4 text-center">
        <span className="flex items-center gap-2 font-bold">
          <Sailboat className="size-4 text-primary" /> TradeWinds
        </span>
        <p className="text-sm text-muted-foreground">AI 驱动的技术情报管道 · 面试演示作品集项目</p>
        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          GitHub 仓库
        </a>
        <div className="mt-2 flex gap-4 text-sm">
          <Link to="/login" className="text-muted-foreground hover:text-foreground">
            登录
          </Link>
          <Link to="/register" className="text-muted-foreground hover:text-foreground">
            注册
          </Link>
        </div>
      </div>
    </footer>
  );
}
