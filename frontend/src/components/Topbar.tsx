import { useEffect, useMemo, useRef, useState } from "react";
import { Bell, Search, Command, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";

type EngagementHit = { engagement_id: string; client_name: string; technology: string };
type AuditEntry = { id: string; action: string; object_type: string; object_id: string; created_at: string };

const PAGES = [
  { label: "Dashboard", to: "/" },
  { label: "Engagements", to: "/engagements" },
  { label: "Checklists", to: "/checklists" },
  { label: "Assessments", to: "/assessments" },
  { label: "Evidence", to: "/evidence" },
  { label: "Findings", to: "/findings" },
  { label: "Risks", to: "/risks" },
  { label: "Reports", to: "/reports" },
  { label: "Webhooks", to: "/webhooks" },
  { label: "AI Assistant", to: "/ai-assistant" },
];

const LAST_SEEN_KEY = "sentinel.notifications_seen";

function describe(a: AuditEntry) {
  return `${a.action.replace(/[._]/g, " ")} · ${a.object_type} ${a.object_id.slice(0, 8)}`;
}

const ROLE_LABEL: Record<string, string> = {
  org_admin: "Organization Admin",
  grc_manager: "GRC Manager",
  grc_auditor: "GRC Auditor",
  reviewer: "Reviewer",
  read_only: "Read Only",
};

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

function Topbar() {
  const { user, organization, role, logout, can } = useAuth();
  const navigate = useNavigate();

  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [engagements, setEngagements] = useState<EngagementHit[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<AuditEntry[]>([]);
  const [seenAt, setSeenAt] = useState(() => localStorage.getItem(LAST_SEEN_KEY) || "");
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const canAudit = can("audit.view");

  // Cmd/Ctrl+K focuses the search box.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close dropdowns on outside click.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
        setNotifOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  // Engagements for search (loaded once, lazily on first focus).
  const loadEngagements = async () => {
    if (engagements.length) return;
    try {
      const res = await apiFetch("/engagements");
      if (res.ok) setEngagements((await res.json()).engagements || []);
    } catch { /* search still works for pages */ }
  };

  // Notifications = recent audit-log entries (only for roles allowed to view them).
  useEffect(() => {
    if (!canAudit) return;
    let alive = true;
    const load = async () => {
      try {
        const res = await apiFetch("/audit-logs?limit=15");
        if (res.ok && alive) setNotifications(await res.json());
      } catch { /* ignore */ }
    };
    load();
    const t = setInterval(load, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, [canAudit]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const pages = PAGES.filter((p) => p.label.toLowerCase().includes(q))
      .map((p) => ({ key: p.to, title: p.label, sub: "Page", to: p.to }));
    const eng = engagements
      .filter((e) => `${e.engagement_id} ${e.client_name} ${e.technology}`.toLowerCase().includes(q))
      .slice(0, 6)
      .map((e) => ({ key: e.engagement_id, title: `${e.engagement_id} · ${e.client_name}`, sub: e.technology, to: "/engagements" }));
    return [...eng, ...pages].slice(0, 8);
  }, [query, engagements]);

  const unread = notifications.filter((n) => !seenAt || n.created_at > seenAt).length;

  const toggleNotifications = () => {
    const next = !notifOpen;
    setNotifOpen(next);
    setSearchOpen(false);
    if (next && notifications[0]) {
      setSeenAt(notifications[0].created_at);
      localStorage.setItem(LAST_SEEN_KEY, notifications[0].created_at);
    }
  };

  const go = (to: string) => {
    setSearchOpen(false);
    setQuery("");
    navigate(to);
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sg-header">
      <div className="sg-header-search" ref={boxRef} style={{ position: "relative" }}>
        <Search size={17} />

        <input
          ref={inputRef}
          type="text"
          value={query}
          placeholder="Search engagements and pages..."
          aria-label="Search"
          onFocus={() => { setSearchOpen(true); loadEngagements(); }}
          onChange={(e) => { setQuery(e.target.value); setSearchOpen(true); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && results[0]) go(results[0].to);
            if (e.key === "Escape") { setSearchOpen(false); inputRef.current?.blur(); }
          }}
        />

        <div className="sg-search-shortcut">
          <Command size={11} />
          K
        </div>

        {searchOpen && query.trim() && (
          <div className="sg-dropdown" role="listbox">
            {results.length === 0 ? (
              <div className="sg-dropdown-empty">No matches</div>
            ) : (
              results.map((r) => (
                <button key={r.key} type="button" className="sg-dropdown-item" onClick={() => go(r.to)}>
                  <strong>{r.title}</strong>
                  <span>{r.sub}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>

      <div className="sg-header-actions">
        {canAudit && (
          <div style={{ position: "relative" }}>
            <button
              type="button"
              className="sg-icon-button"
              title="Notifications"
              aria-label={`Notifications${unread ? ` (${unread} new)` : ""}`}
              onClick={toggleNotifications}
            >
              <Bell size={18} />
              {unread > 0 && <span className="sg-notification-dot" />}
            </button>

            {notifOpen && (
              <div className="sg-dropdown sg-dropdown-right" role="menu">
                <div className="sg-dropdown-title">Recent activity</div>
                {notifications.length === 0 ? (
                  <div className="sg-dropdown-empty">Nothing yet</div>
                ) : (
                  notifications.slice(0, 8).map((n) => (
                    <div key={n.id} className="sg-dropdown-item static">
                      <strong>{describe(n)}</strong>
                      <span>{new Date(n.created_at).toLocaleString()}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}

        <div className="sg-user-menu">
          <div className="sg-user-avatar">{user ? initials(user.full_name) : ""}</div>

          <div className="sg-user-info">
            <strong>{user?.full_name}</strong>
            <span>
              {role ? ROLE_LABEL[role] : "Platform Administrator"}
              {organization ? ` · ${organization.name}` : ""}
            </span>
          </div>

          <button type="button" className="sg-icon-button" title="Sign out" aria-label="Sign out" onClick={handleLogout}>
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </header>
  );
}

export default Topbar;
