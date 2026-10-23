// ルーティングと、ログイン・権限による画面の出し分け
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useNavigate } from "react-router";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { NAV_ITEMS, homePath } from "./auth/routes";
import Sidebar from "./components/Sidebar";
import LoginPage from "./pages/LoginPage";
import PlaceholderPage from "./pages/PlaceholderPage";

// ログイン必須の画面の枠(左にサイドバー)
function Layout() {
  const { me, loading, logout } = useAuth();
  const navigate = useNavigate();
  if (loading) {
    return <p style={{ padding: 16 }}>読み込み中…</p>;
  }
  if (!me) {
    return <Navigate to="/login" replace />;
  }
  return (
    <div style={{ display: "flex" }}>
      <Sidebar
        me={me}
        onLogout={async () => {
          await logout();
          navigate("/login", { replace: true });
        }}
      />
      <main style={{ flex: 1, padding: 24 }}>
        <Outlet />
      </main>
    </div>
  );
}

// 店長専用の画面に担当者が来たら、所属部門の既定の画面へ戻す
function ManagerOnly({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  if (me && me.role !== "manager") {
    return <Navigate to={homePath(me)} replace />;
  }
  return <>{children}</>;
}

function Home() {
  const { me } = useAuth();
  return <Navigate to={me ? homePath(me) : "/login"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            {NAV_ITEMS.map((item) => (
              <Route
                key={item.path}
                path={item.path}
                element={
                  item.managerOnly ? (
                    <ManagerOnly>
                      <PlaceholderPage title={item.label} />
                    </ManagerOnly>
                  ) : (
                    <PlaceholderPage title={item.label} />
                  )
                }
              />
            ))}
            <Route path="*" element={<Home />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
