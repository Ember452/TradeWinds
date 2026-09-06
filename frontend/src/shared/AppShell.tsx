import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut, Moon, Sailboat, Sun } from "lucide-react";
import { useAuth } from "@/shared/auth";
import { useTheme } from "@/shared/theme";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageTransition } from "@/shared/PageTransition";

// 应用外壳:玻璃拟态 sticky 顶栏(品牌/导航/主题切换/用户菜单)+ 居中内容区
export function AppShell() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm transition-colors ${
      isActive ? "bg-primary/10 font-semibold text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"
    }`;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-border-soft bg-surface/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <NavLink to="/topics" className="flex items-center gap-2 font-bold text-foreground">
            <Sailboat className="size-5 text-primary" />
            <span>TradeWinds</span>
          </NavLink>
          <nav className="flex flex-1 items-center gap-1">
            <NavLink to="/topics" end className={navClass}>
              主题
            </NavLink>
            <NavLink to="/chat" className={navClass}>
              对话研究
            </NavLink>
          </nav>
          <Button variant="ghost" size="icon" onClick={toggle} aria-label="切换主题" title={theme === "dark" ? "切换到浅色" : "切换到深色"}>
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="max-w-44 truncate font-normal">
                  {user.email}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => {
                    logout();
                    navigate("/login");
                  }}
                >
                  <LogOut className="size-4" />
                  登出
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8">
        <PageTransition>
          <Outlet />
        </PageTransition>
      </main>
    </div>
  );
}
