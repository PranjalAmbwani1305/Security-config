import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileCheck2,
  FolderKanban,
  LayoutDashboard,
  ListChecks,
  MonitorCheck,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import "./Engagements.css";

const API_URL = import.meta.env.VITE_API_URL;

type Engagement = {
  engagement_id: string;
  client_name: string;
  technology: string;
  reviewer: string;
  results: unknown[];
};

function Engagements() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [clientName, setClientName] = useState("");
  const [technology, setTechnology] = useState("Linux");
  const [reviewer, setReviewer] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    loadEngagements();
  }, []);

  async function loadEngagements(showRefresh = false) {
    if (showRefresh) setRefreshing(true);

    try {
      const response = await fetch(`${API_URL}/engagements`);

      if (!response.ok) {
        throw new Error("Failed to load engagements");
      }

      const data = await response.json();
      setEngagements(data.engagements || []);
      setMessage("");
    } catch (error) {
      console.error("Failed to load engagements:", error);
      setMessage("Unable to load engagements. Check that the backend is running.");
    } finally {
      setRefreshing(false);
    }
  }

  async function createEngagement() {
    setMessage("");

    if (!clientName.trim()) {
      setMessage("Please enter a client name.");
      return;
    }

    if (!reviewer.trim()) {
      setMessage("Please enter a reviewer name.");
      return;
    }

    setLoading(true);

    const engagementId = `ENG-${Date.now()}`;

    try {
      const response = await fetch(`${API_URL}/engagements`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          engagement_id: engagementId,
          client_name: clientName.trim(),
          technology,
          reviewer: reviewer.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to create engagement");
      }

      setClientName("");
      setReviewer("");
      setTechnology("Linux");
      setShowForm(false);
      setMessage("Engagement created successfully.");
      await loadEngagements();
    } catch (error) {
      console.error("Create engagement error:", error);
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to create engagement.",
      );
    } finally {
      setLoading(false);
    }
  }

  const filteredEngagements = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) return engagements;

    return engagements.filter((item) =>
      [
        item.engagement_id,
        item.client_name,
        item.technology,
        item.reviewer,
      ].some((value) => value.toLowerCase().includes(query)),
    );
  }, [engagements, search]);

  const linuxCount = engagements.filter(
    (item) => item.technology.toLowerCase() === "linux",
  ).length;

  const windowsCount = engagements.filter(
    (item) => item.technology.toLowerCase() === "windows",
  ).length;

  return (
    <div className="engagement-page">
      <aside className="engagement-sidebar">
        <Link to="/" className="engagement-brand">
          <div className="brand-mark">
            <ShieldCheck size={22} />
          </div>
          <div>
            <div className="brand-name">Sentinel GRC</div>
            <div className="brand-subtitle">Security Governance Platform</div>
          </div>
        </Link>

        <div className="sidebar-section-label">Workspace</div>

        <nav className="engagement-nav">
          <NavItem to="/" label="Dashboard" icon={<LayoutDashboard size={18} />} />
          <NavItem
            to="/engagements"
            label="Engagements"
            icon={<FolderKanban size={18} />}
            active
          />
          <NavItem to="/checklists" label="Checklists" icon={<ListChecks size={18} />} />
          <NavItem
            to="/assessments"
            label="Assessments"
            icon={<ClipboardCheck size={18} />}
          />
          <NavItem to="/evidence" label="Evidence" icon={<FileCheck2 size={18} />} />
          <NavItem to="/findings" label="Findings" icon={<AlertCircle size={18} />} />
          <NavItem to="/risks" label="Risks" icon={<Activity size={18} />} />
          <NavItem to="/reports" label="Reports" icon={<MonitorCheck size={18} />} />
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status-dot" />
          <div>
            <div className="sidebar-status-title">Platform Operational</div>
            <div className="sidebar-status-text">FastAPI connected</div>
          </div>
        </div>
      </aside>

      <main className="engagement-main">
        <header className="engagement-topbar">
          <div className="topbar-search">
            <Search size={17} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search engagements, clients, reviewers..."
            />
            <span className="search-key">⌘ K</span>
          </div>

          <div className="topbar-profile">
            <div className="profile-avatar">GR</div>
            <div className="profile-copy">
              <span>GRC Reviewer</span>
              <small>Security Operations</small>
            </div>
          </div>
        </header>

        <section className="engagement-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-line" />
                GOVERNANCE WORKSPACE
              </div>
              <h1>Engagements</h1>
              <p>
                Create and manage security configuration and compliance
                assessment engagements.
              </p>
            </div>

            <button
              className="primary-button"
              onClick={() => {
                setMessage("");
                setShowForm(true);
              }}
            >
              <Plus size={18} />
              New Engagement
            </button>
          </div>

          {message && (
            <div
              className={`feedback-banner ${
                message.toLowerCase().includes("success")
                  ? "feedback-success"
                  : "feedback-error"
              }`}
            >
              {message.toLowerCase().includes("success") ? (
                <CheckCircle2 size={18} />
              ) : (
                <AlertCircle size={18} />
              )}
              <span>{message}</span>
              <button onClick={() => setMessage("")} aria-label="Dismiss">
                <X size={16} />
              </button>
            </div>
          )}

          <div className="stat-grid">
            <StatCard
              title="Total Engagements"
              value={engagements.length}
              description="Assessment workspaces"
              icon={<FolderKanban size={20} />}
            />
            <StatCard
              title="Linux Assessments"
              value={linuxCount}
              description="Linux technology scope"
              icon={<MonitorCheck size={20} />}
            />
            <StatCard
              title="Windows Assessments"
              value={windowsCount}
              description="Windows technology scope"
              icon={<ShieldCheck size={20} />}
            />
            <StatCard
              title="Active Reviewers"
              value={new Set(engagements.map((item) => item.reviewer)).size}
              description="Assigned reviewers"
              icon={<Users size={20} />}
            />
          </div>

          <section className="engagement-panel">
            <div className="panel-header">
              <div>
                <div className="panel-title-row">
                  <h2>Assessment Engagements</h2>
                  <span className="count-badge">{filteredEngagements.length}</span>
                </div>
                <p>Security assessment workspaces currently available in Sentinel GRC.</p>
              </div>

              <button
                className="secondary-button"
                onClick={() => loadEngagements(true)}
                disabled={refreshing}
              >
                <RefreshCw size={16} className={refreshing ? "spin" : ""} />
                Refresh
              </button>
            </div>

            {engagements.length === 0 ? (
              <EmptyState onCreate={() => setShowForm(true)} />
            ) : filteredEngagements.length === 0 ? (
              <div className="empty-filter-state">
                <Search size={28} />
                <h3>No matching engagements</h3>
                <p>Try a different client, technology, reviewer, or engagement ID.</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="engagement-table">
                  <thead>
                    <tr>
                      <th>Engagement</th>
                      <th>Client</th>
                      <th>Technology</th>
                      <th>Reviewer</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEngagements.map((engagement) => (
                      <tr key={engagement.engagement_id}>
                        <td>
                          <div className="engagement-id">
                            <span className="id-icon">
                              <FolderKanban size={15} />
                            </span>
                            <div>
                              <strong>{engagement.engagement_id}</strong>
                              <small>Security assessment</small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="client-name">{engagement.client_name}</span>
                        </td>
                        <td>
                          <span
                            className={`technology-badge ${
                              engagement.technology.toLowerCase() === "linux"
                                ? "technology-linux"
                                : "technology-windows"
                            }`}
                          >
                            <span />
                            {engagement.technology}
                          </span>
                        </td>
                        <td>
                          <div className="reviewer-cell">
                            <span className="reviewer-avatar">
                              {engagement.reviewer
                                .split(" ")
                                .map((part) => part[0])
                                .join("")
                                .slice(0, 2)
                                .toUpperCase()}
                            </span>
                            <span>{engagement.reviewer}</span>
                          </div>
                        </td>
                        <td>
                          <span className="status-badge">
                            <span />
                            Active
                          </span>
                        </td>
                        <td>
                          <Link
                            to={`/assessments?engagement=${encodeURIComponent(
                              engagement.engagement_id,
                            )}`}
                            className="row-action"
                            title="Open assessment"
                          >
                            <ArrowRight size={17} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </section>
      </main>

      {showForm && (
        <div className="modal-backdrop" onMouseDown={() => setShowForm(false)}>
          <div
            className="engagement-modal"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <div className="modal-icon">
                  <FolderKanban size={20} />
                </div>
                <h2>Create Engagement</h2>
                <p>Start a new security configuration assessment.</p>
              </div>
              <button
                className="modal-close"
                onClick={() => setShowForm(false)}
                aria-label="Close"
              >
                <X size={19} />
              </button>
            </div>

            <div className="modal-form">
              <label>
                <span>Client Name</span>
                <input
                  value={clientName}
                  onChange={(event) => setClientName(event.target.value)}
                  placeholder="e.g. Acme Corporation"
                  autoFocus
                />
              </label>

              <label>
                <span>Technology</span>
                <select
                  value={technology}
                  onChange={(event) => setTechnology(event.target.value)}
                >
                  <option value="Linux">Linux</option>
                  <option value="Windows">Windows</option>
                </select>
              </label>

              <label>
                <span>Reviewer</span>
                <input
                  value={reviewer}
                  onChange={(event) => setReviewer(event.target.value)}
                  placeholder="e.g. Security Reviewer"
                />
              </label>
            </div>

            <div className="modal-footer">
              <button
                className="secondary-button modal-cancel"
                onClick={() => setShowForm(false)}
                disabled={loading}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={createEngagement}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <RefreshCw size={17} className="spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus size={17} />
                    Create Engagement
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NavItem({
  to,
  label,
  icon,
  active = false,
}: {
  to: string;
  label: string;
  icon: React.ReactNode;
  active?: boolean;
}) {
  return (
    <Link to={to} className={`engagement-nav-item ${active ? "active" : ""}`}>
      <span className="nav-icon">{icon}</span>
      <span>{label}</span>
    </Link>
  );
}

function StatCard({
  title,
  value,
  description,
  icon,
}: {
  title: string;
  value: number;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="engagement-stat-card">
      <div className="stat-card-top">
        <span className="stat-icon">{icon}</span>
        <span className="stat-live">LIVE</span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-title">{title}</div>
      <div className="stat-description">{description}</div>
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <FolderKanban size={30} />
      </div>
      <h3>No engagements yet</h3>
      <p>Create your first engagement to begin a security assessment.</p>
      <button className="primary-button" onClick={onCreate}>
        <Plus size={17} />
        Create Engagement
      </button>
    </div>
  );
}

export default Engagements;
