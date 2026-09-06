import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="layout">
      <header className="topbar">
        <span className="brand">⛵ TradeWinds</span>
        <nav>
          <NavLink to="/" end>主题</NavLink>
          <NavLink to="/chat">对话研究</NavLink>
        </nav>
        <span className="user">
          {user && (
            <>
              <span>{user.email}</span>
              <button
                type="button"
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
              >
                登出
              </button>
            </>
          )}
        </span>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
