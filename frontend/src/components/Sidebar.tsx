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
  Webhook,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { API_URL } from "../lib/api";

const navigation = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/engagements", label: "Engagements", icon: BriefcaseBusiness },
  { to: "/checklists", label: "Checklists", icon: ListChecks },
  { to: "/assessments", label: "Assessments", icon: ClipboardCheck },
  { to: "/evidence", label: "Evidence", icon: FolderOpen },
  { to: "/findings", label: "Findings", icon: AlertTriangle },
  { to: "/risks", label: "Risks", icon: ShieldAlert },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/ai-assistant", label: "AI Assistant", icon: Sparkles },
  { to: "/webhooks", label: "Webhooks", icon: Webhook, permission: "webhook.manage" },
] as { to: string; label: string; icon: typeof Shield; permission?: string }[];

type Health = "checking" | "up" | "down";

/** Real API health (GET /ready checks the database), polled every 60s. */
function useApiHealth(): Health {
  const [health, setHealth] = useState<Health>("checking");
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/ready`, { cache: "no-store" });
        if (alive) setHealth(res.ok ? "up" : "down");
      } catch {
        if (alive) setHealth("down");
      }
    };
    check();
    const t = setInterval(check, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return health;
}

const HEALTH_LABEL: Record<Health, string> = {
  checking: "Checking status...",
  up: "System Operational",
  down: "API Unreachable",
};

function Sidebar() {
  const { can } = useAuth();
  const health = useApiHealth();
  const items = navigation.filter((i) => !i.permission || can(i.permission));

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
        {items.map((item) => {
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
            <span
              className="sg-status-dot"
              style={health === "down" ? { background: "#f87171" } : health === "checking" ? { background: "#fbbf24" } : undefined}
            />
            <span>{HEALTH_LABEL[health]}</span>
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