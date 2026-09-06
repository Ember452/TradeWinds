import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./auth";
import { getToken } from "./api";
import { LoadingScreen } from "./LoadingScreen";

export function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  // 用户状态未就绪但本地有 token 时暂放行,由 /users/me 请求结果决定
  if (!user && getToken() === null) return <Navigate to="/login" replace />;
  return <Outlet />;
}
