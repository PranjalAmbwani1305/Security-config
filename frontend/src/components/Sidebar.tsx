import {
  LayoutDashboard,
  BriefcaseBusiness,
  ClipboardCheck,
  ListChecks,
  FolderOpen,
  AlertTriangle,
  ShieldAlert,
  FileText,
  Shield,
  Activity,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const navigation = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/engagements", label: "Engagements", icon: BriefcaseBusiness },
  { to: "/checklists", label: "Checklists", icon: ListChecks },
  { to: "/assessments", label: "Assessments", icon: ClipboardCheck },
  { to: "/evidence", label: "Evidence", icon: FolderOpen },
  { to: "/findings", label: "Findings", icon: AlertTriangle },
  { to: "/risks", label: "Risks", icon: ShieldAlert },
  { to: "/reports", label: "Reports", icon: FileText },
];

function Sidebar() {
  return (
    <aside className="sg-sidebar">
      <div className="sg-brand">
        <div className="sg-brand-mark">
          <Shield size={20} />
        </div>

        <div>
          <div className="sg-brand-name">Sentinel GRC</div>
          <div className="sg-brand-subtitle">
            Security Governance Platform
          </div>
        </div>
      </div>

      <div className="sg-sidebar-section-label">
        Workspace
      </div>

      <nav className="sg-nav">
        {navigation.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `sg-nav-item ${isActive ? "active" : ""}`
              }
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="sg-sidebar-footer">
        <div className="sg-system-status">
          <div className="sg-system-status-row">
            <span className="sg-status-dot" />
            <span>System Operational</span>
          </div>

          <div className="sg-system-meta">
            <Activity size={13} />
            Sentinel GRC v1.0
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;