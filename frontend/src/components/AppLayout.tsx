import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

function AppLayout() {
  return (
    <div className="sg-app">
      <Sidebar />

      <main className="sg-main">
        <Topbar />

        <div className="sg-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default AppLayout;