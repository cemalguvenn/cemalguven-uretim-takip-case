import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ImportData from "./pages/ImportData.jsx";
import Records from "./pages/Records.jsx";
import ValidationReport from "./pages/ValidationReport.jsx";
import SyncManager from "./pages/SyncManager.jsx";
import Settings from "./pages/Settings.jsx";

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/import" element={<ImportData />} />
        <Route path="/records" element={<Records />} />
        <Route path="/validation" element={<ValidationReport />} />
        <Route path="/sync" element={<SyncManager />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}
