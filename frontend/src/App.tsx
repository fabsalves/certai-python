import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RoleRoute } from "./components/RoleRoute";
import { AuthProvider } from "./lib/auth";
import { CohortEditor } from "./pages/CohortEditor";
import { Cohorts } from "./pages/Cohorts";
import { Dashboard } from "./pages/Dashboard";
import { Learn } from "./pages/Learn";
import { Login } from "./pages/Login";
import { Playground } from "./pages/Playground";
import { Professors } from "./pages/Professors";
import { TrackEditor } from "./pages/TrackEditor";
import { Tracks } from "./pages/Tracks";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />

            <Route path="tracks" element={<RoleRoute area="tracks"><Tracks /></RoleRoute>} />
            <Route path="tracks/new" element={<RoleRoute area="tracks"><TrackEditor /></RoleRoute>} />
            <Route path="tracks/:trackId" element={<RoleRoute area="tracks"><TrackEditor /></RoleRoute>} />

            <Route path="cohorts" element={<RoleRoute area="cohorts"><Cohorts /></RoleRoute>} />
            <Route path="cohorts/new" element={<RoleRoute area="cohorts"><CohortEditor /></RoleRoute>} />
            <Route path="cohorts/:cohortId" element={<RoleRoute area="cohorts"><CohortEditor /></RoleRoute>} />
            <Route path="professors" element={<RoleRoute area="professors"><Professors /></RoleRoute>} />
            <Route path="learn" element={<RoleRoute area="learn"><Learn /></RoleRoute>} />
            <Route path="admin/playground" element={<RoleRoute area="playground"><Playground /></RoleRoute>} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
