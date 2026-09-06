import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./shared/auth";
import { RequireAuth } from "./shared/RequireAuth";
import { Layout } from "./shared/Layout";
import { AuthForm } from "./features/auth/AuthForm";
import { SharedReportPage } from "./features/reports/SharedReportPage";
import { TopicsPage } from "./features/topics/TopicsPage";
import { TopicDetailPage } from "./features/topics/TopicDetailPage";
import { ChatListPage, ChatPage } from "./features/chat/ChatPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<AuthForm mode="login" />} />
          <Route path="/register" element={<AuthForm mode="register" />} />
          <Route path="/share/reports/:token" element={<SharedReportPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route path="/" element={<TopicsPage />} />
              <Route path="/topics/:topicId" element={<TopicDetailPage />} />
              <Route path="/chat" element={<ChatListPage />} />
              <Route path="/chat/:conversationId" element={<ChatPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
