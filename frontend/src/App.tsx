import { BrowserRouter, Routes, Route } from "react-router-dom";

import AppLayout from "./components/AppLayout";

import Dashboard from "./pages/Dashboard";
import Engagements from "./pages/Engagements";
import Checklists from "./pages/Checklists";
import Assessments from "./pages/Assessments";
import Evidence from "./pages/Evidence";
import Findings from "./pages/Findings";
import Risks from "./pages/Risks";
import Reports from "./pages/Reports";
import Auth from "./pages/Auth";
import Webhooks from "./pages/Webhooks";
import AIAssistant from "./pages/AIAssistant";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Auth />} />

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
      </Routes>
    </BrowserRouter>
  );
}

export default App;