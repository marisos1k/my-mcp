import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { LoginPage } from "./pages/LoginPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { EditorPage } from "./pages/EditorPage";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { email, loading } = useAuth();
  if (loading) return <div className="center-msg">Загрузка...</div>;
  if (!email) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { email, loading } = useAuth();

  if (loading) {
    return <div className="center-msg">Загрузка...</div>;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={email ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <ProjectsPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/editor/:pipelineId"
        element={
          <PrivateRoute>
            <EditorPage />
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
