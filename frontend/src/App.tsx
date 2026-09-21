import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./store/auth";
import Login from "./pages/Login";
import Home from "./pages/Home";
import SsoCallback from "./pages/SsoCallback";

export default function App() {
  const { user, loading, init } = useAuth();

  useEffect(() => {
    init();
  }, [init]);

  if (loading) return <div className="empty">Chargement…</div>;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
      <Route path="/auth/callback" element={<SsoCallback />} />
      <Route path="/*" element={user ? <Home /> : <Navigate to="/login" />} />
    </Routes>
  );
}
