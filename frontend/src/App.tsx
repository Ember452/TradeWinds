import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/shared/auth";
import { ThemeProvider } from "@/shared/theme";
import { RequireAuth } from "@/shared/RequireAuth";
import { AppShell } from "@/shared/AppShell";
import { AuthForm } from "@/features/auth/AuthForm";
import { SharedReportPage } from "@/features/reports/SharedReportPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { TopicsPage } from "@/features/topics/TopicsPage";
import { TopicDetailPage } from "@/features/topics/TopicDetailPage";
import { ChatListPage } from "@/features/chat/ChatListPage";
import { ChatPage } from "@/features/chat/ChatPage";

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingGate />} />
            <Route path="/login" element={<AuthForm mode="login" />} />
            <Route path="/register" element={<AuthForm mode="register" />} />
            <Route path="/share/reports/:token" element={<SharedReportPage />} />
            <Route element={<RequireAuth />}>
              <Route element={<AppShell />}>
                <Route path="/topics" element={<TopicsPage />} />
                <Route path="/topics/:topicId" element={<TopicDetailPage />} />
                <Route path="/chat" element={<ChatListPage />} />
                <Route path="/chat/:conversationId" element={<ChatPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      {/* Toaster 需在 ThemeProvider 内读取主题,置于路由之外保证任意页面可用 */}
      <Toaster richColors position="top-center" />
    </ThemeProvider>
  );
}

// 已登录用户访问 / 直接进应用,未登录看宣传页
function LandingGate() {
  const { user, loading } = useAuth();
  if (loading) return <p className="p-8 text-center text-muted-foreground">加载中…</p>;
  if (user) return <Navigate to="/topics" replace />;
  return <LandingPage />;
}
