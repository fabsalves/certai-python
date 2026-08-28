import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RoleRoute } from "./components/RoleRoute";
import { AuthProvider } from "./lib/auth";
import { OrgProvider } from "./lib/orgContext";
import { ConfirmProvider } from "./lib/confirm";
import { FeedbackProvider } from "./lib/feedback";
import { ThemeProvider } from "./lib/theme";
import { OrgAdminPage } from "./pages/admin/OrgAdminPage";
import { OrgDetailPage } from "./pages/admin/OrgDetailPage";
import { SuperAdminPage } from "./pages/admin/SuperAdminPage";
import { CohortCosts } from "./pages/CohortCosts";
import { CohortEditor } from "./pages/CohortEditor";
import { Costs } from "./pages/Costs";
import { Cohorts } from "./pages/Cohorts";
import { Dashboard } from "./pages/Dashboard";
import { Learn } from "./pages/Learn";
import { Login } from "./pages/Login";
import { Playground } from "./pages/Playground";
import { Professors } from "./pages/Professors";
import { StudentCosts } from "./pages/StudentCosts";
import { TrackEditor } from "./pages/TrackEditor";
import { Tracks } from "./pages/Tracks";
import { VoiceSession } from "./pages/VoiceSession";

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <OrgProvider>
        <ConfirmProvider>
          <FeedbackProvider>
          <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/voz/:handoffToken" element={<VoiceSession />} />

          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />

            <Route path="tracks" element={<RoleRoute area="tracks"><Tracks /></RoleRoute>} />
            <Route path="tracks/:trackId" element={<RoleRoute area="tracks"><TrackEditor /></RoleRoute>} />

            <Route path="cohorts" element={<RoleRoute area="cohorts"><Cohorts /></RoleRoute>} />
            <Route path="cohorts/:cohortId" element={<RoleRoute area="cohorts"><CohortEditor /></RoleRoute>} />
            <Route path="professors" element={<RoleRoute area="professors"><Professors /></RoleRoute>} />
            <Route path="learn" element={<RoleRoute area="learn"><Learn /></RoleRoute>} />
            <Route path="admin/playground" element={<RoleRoute area="playground"><Playground /></RoleRoute>} />
            <Route path="admin" element={<RoleRoute area="admin"><SuperAdminPage /></RoleRoute>} />
            <Route path="admin/orgs/:orgId" element={<RoleRoute area="admin"><OrgDetailPage /></RoleRoute>} />
            <Route path="settings" element={<RoleRoute area="settings"><OrgAdminPage /></RoleRoute>} />

            <Route path="costs" element={<RoleRoute area="costs"><Costs /></RoleRoute>} />
            <Route path="costs/:cohortId" element={<RoleRoute area="costs"><CohortCosts /></RoleRoute>} />
            <Route
              path="costs/:cohortId/alunos/:studentId"
              element={<RoleRoute area="costs"><StudentCosts /></RoleRoute>}
            />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </BrowserRouter>
        </FeedbackProvider>
      </ConfirmProvider>
        </OrgProvider>
    </AuthProvider>
    </ThemeProvider>
  );
}
