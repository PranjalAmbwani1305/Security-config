import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import { AuthProvider } from "./auth/AuthContext";
import RequireAuth from "./auth/RequireAuth";
import ErrorBoundary from "./components/ErrorBoundary";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Engagements = lazy(() => import("./pages/Engagements"));
const Checklists = lazy(() => import("./pages/Checklists"));
const Assessments = lazy(() => import("./pages/Assessments"));
const Evidence = lazy(() => import("./pages/Evidence"));
const Findings = lazy(() => import("./pages/Findings"));
const Risks = lazy(() => import("./pages/Risks"));
const Reports = lazy(() => import("./pages/Reports"));
const Auth = lazy(() => import("./pages/Auth"));
const Webhooks = lazy(() => import("./pages/Webhooks"));
const AIAssistant = lazy(() => import("./pages/AIAssistant"));

function App() {
  return (
    <ErrorBoundary>
    <BrowserRouter>
      <AuthProvider>
      <Suspense fallback={<div style={{ padding: 32, color: "#8aa0bd" }}>Loading...</div>}>
      <Routes>
        <Route path="/login" element={<Auth />} />

        <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/engagements" element={<Engagements />} />
          <Route path="/checklists" element={<Checklists />} />
          <Route path="/assessments" element={<Assessments />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/findings" element={<Findings />} />
          <Route path="/risks" element={<Risks />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/webhooks" element={<Webhooks />} />
          <Route path="/ai-assistant" element={<AIAssistant />} />
        </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
      </AuthProvider>
    </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;