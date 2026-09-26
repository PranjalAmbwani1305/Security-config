import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  Clock3,
  FileWarning,
  Layers3,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
  XCircle,
} from "lucide-react";

import "./Dashboard.css";

type Engagement = {
  id: string;
  client: string;
  technology: string;
  progress: number;
  status: "In Progress" | "Completed" | "At Risk";
  reviewer: string;
  updated: string;
};

type AssessmentResult = { item_id?: string; status?: string; notes?: string };
type Finding = { finding_id?: string; status?: string; severity?: string; title?: string };
type Risk = { risk_id?: string; risk_score?: number; risk_level?: string; status?: string; title?: string };

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const activities = [
  { icon: ShieldAlert, title: "Critical risk identified", description: "Privileged SSH access requires remediation", time: "12 min ago", tone: "danger" },
  { icon: ClipboardCheck, title: "Assessment completed", description: "Windows baseline review completed", time: "34 min ago", tone: "success" },
  { icon: FileWarning, title: "New finding created", description: "Password policy control failed", time: "1 hr ago", tone: "warning" },
  { icon: ShieldCheck, title: "Engagement approved", description: "Nova Infrastructure review approved", time: "2 hrs ago", tone: "success" },
];

function asList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[];
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    for (const key of ["items", "results", "engagements", "assessments", "findings", "risks", "data"]) {
      if (Array.isArray(record[key])) return record[key] as T[];
    }
  }
  return [];
}

function isActive(status?: string) {
  return !status || !["closed", "resolved", "accepted", "inactive"].includes(status.toLowerCase());
}

function calculateCompliance(results: AssessmentResult[]) {
  const assessed = results.filter((r) => ["compliant", "non-compliant", "compensating control"].includes((r.status || "").toLowerCase()));
  if (!assessed.length) return 0;
  const compliant = assessed.filter((r) => ["compliant", "compensating control"].includes((r.status || "").toLowerCase())).length;
  return Math.round((compliant / assessed.length) * 100);
}

function Dashboard() {
  const navigate = useNavigate();

  const [search] = useState("");
  const [lastUpdated, setLastUpdated] = useState("Just now");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [assessmentResults, setAssessmentResults] = useState<AssessmentResult[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [riskRecords, setRiskRecords] = useState<Risk[]>([]);

  const loadDashboard = useCallback(async () => {
    setError("");
    try {
      const response = await fetch(`${API_URL}/engagements`);
      if (!response.ok) throw new Error(`Unable to load engagements (${response.status})`);
      const payload = await response.json();
      const raw = asList<Record<string, unknown>>(payload);
      const base: Engagement[] = raw.map((item, index) => ({
        id: String(item.engagement_id ?? item.id ?? `ENG-${String(index + 1).padStart(3, "0")}`),
        client: String(item.client_name ?? item.client ?? "Unknown Client"),
        technology: String(item.technology ?? "Unknown"),
        progress: 0,
        status: "In Progress",
        reviewer: String(item.reviewer ?? "Security Team"),
        updated: "Recently updated",
      }));
      const details = await Promise.all(base.map(async (engagement) => {
        const [a, f, r] = await Promise.all([
          fetch(`${API_URL}/assessments/${engagement.id}`),
          fetch(`${API_URL}/findings/${engagement.id}`),
          fetch(`${API_URL}/risks/${engagement.id}`),
        ]);
        const [ap, fp, rp] = await Promise.all([
          a.ok ? a.json() : [], f.ok ? f.json() : [], r.ok ? r.json() : [],
        ]);
        const results = asList<AssessmentResult>(ap);
        const findingList = asList<Finding>(fp);
        const riskList = asList<Risk>(rp);
        const reviewed = results.filter((x) => ["compliant", "non-compliant", "compensating control", "not applicable"].includes((x.status || "").toLowerCase())).length;
        const progress = results.length ? Math.round((reviewed / results.length) * 100) : 0;
        return { engagement: { ...engagement, progress, status: progress >= 100 ? "Completed" : "In Progress" } as Engagement, results, findingList, riskList };
      }));
      setEngagements(details.map((x) => x.engagement));
      setAssessmentResults(details.flatMap((x) => x.results));
      setFindings(details.flatMap((x) => x.findingList));
      setRiskRecords(details.flatMap((x) => x.riskList));
      setLastUpdated("Just now");
    } catch (err) {
      console.error("Dashboard load failed:", err);
      setError("Unable to load live dashboard data. Make sure the FastAPI backend is running.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  const handleRefresh = () => { setRefreshing(true); void loadDashboard(); };


  const filteredEngagements = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return engagements;
    return engagements.filter((e) => e.client.toLowerCase().includes(query) || e.technology.toLowerCase().includes(query) || e.reviewer.toLowerCase().includes(query));
  }, [engagements, search]);

  const compliance = useMemo(() => calculateCompliance(assessmentResults), [assessmentResults]);
  const activeFindings = useMemo(() => findings.filter((x) => isActive(x.status)), [findings]);
  const activeRisks = useMemo(() => riskRecords.filter((x) => isActive(x.status)), [riskRecords]);
  const criticalRisks = useMemo(() => activeRisks.filter((x) => (x.risk_level || '').toLowerCase() === 'critical').length, [activeRisks]);
  const totalRiskExposure = useMemo(() => activeRisks.reduce((sum, x) => sum + Number(x.risk_score || 0), 0), [activeRisks]);
  const riskCounts = useMemo(() => [
    { label: 'Critical', value: activeRisks.filter((x) => (x.risk_level || '').toLowerCase() === 'critical').length, description: 'Immediate attention', className: 'critical' },
    { label: 'High', value: activeRisks.filter((x) => (x.risk_level || '').toLowerCase() === 'high').length, description: 'Requires treatment', className: 'high' },
    { label: 'Medium', value: activeRisks.filter((x) => (x.risk_level || '').toLowerCase() === 'medium').length, description: 'Monitor & review', className: 'medium' },
    { label: 'Low', value: activeRisks.filter((x) => (x.risk_level || '').toLowerCase() === 'low').length, description: 'Within tolerance', className: 'low' },
  ], [activeRisks]);
  const technologyCoverage = useMemo(() => {
    const counts = new Map<string, number>();
    engagements.forEach((e) => counts.set(e.technology, (counts.get(e.technology) || 0) + 1));
    return Array.from(counts.entries()).map(([technology, count]) => ({ technology, count, percentage: engagements.length ? Math.round((count / engagements.length) * 100) : 0 }));
  }, [engagements]);

  return (
    <div className="dashboard-page">
      <div className="dashboard-background dashboard-glow-one" />
      <div className="dashboard-background dashboard-glow-two" />

      <main className="dashboard-content">
        {error && <div className="panel" style={{ marginBottom: "18px", padding: "14px 18px", borderColor: "rgba(248, 113, 113, 0.35)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <AlertTriangle size={17} /><span>{error}</span>
            <button className="text-button" onClick={handleRefresh} style={{ marginLeft: "auto" }}>Retry</button>
          </div>
        </div>}
        {loading && <div className="panel" style={{ marginBottom: "18px", padding: "14px 18px", display: "flex", alignItems: "center", gap: "10px" }}>
          <RefreshCw size={16} className="spin" /><span>Loading live security posture...</span>
        </div>}
        {/* =====================================================
            PAGE HEADER
        ===================================================== */}

        <section className="dashboard-header">
          <div className="dashboard-heading">
            <div className="dashboard-breadcrumb">
              <Shield size={15} />
              <span>Command Center</span>
              <ChevronRight size={13} />
              <span>Overview</span>
            </div>

            <div className="heading-title-row">
              <h1>Security Posture</h1>

              <span className="live-indicator">
                <span />
                Live
              </span>
            </div>

            <p>
              Monitor your security configuration, compliance posture,
              findings and risk exposure from one workspace.
            </p>
          </div>

          <div className="dashboard-actions">
            <div className="platform-status">
              <span className="status-dot" />
              <span>Platform Operational</span>
            </div>

            <button
              className="icon-button"
              title="Refresh dashboard"
              onClick={handleRefresh}
            >
              <RefreshCw size={17} className={refreshing ? "spin" : ""} />
            </button>

            <button
              className="primary-button"
              onClick={() => navigate("/engagements")}
            >
              New Engagement
              <ArrowUpRight size={17} />
            </button>
          </div>
        </section>

        {/* =====================================================
            KPI CARDS
        ===================================================== */}

        <section className="stats-grid">
          <article
            className="stat-card clickable-card"
            onClick={() => navigate("/engagements")}
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                navigate("/engagements");
              }
            }}
          >
            <div className="stat-card-top">
              <div className="stat-icon blue">
                <Users size={19} />
              </div>

              <ArrowUpRight className="stat-arrow" size={17} />
            </div>

            <div className="stat-content">
              <span>Active Engagements</span>
              <strong>{String(engagements.length).padStart(2, "0")}</strong>

              <div className="stat-meta positive">
                <Activity size={13} />
                <span>{engagements.filter((e) => e.status === "In Progress").length} in progress</span>
              </div>
            </div>
          </article>

          <article
            className="stat-card clickable-card"
            onClick={() => navigate("/assessments")}
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                navigate("/assessments");
              }
            }}
          >
            <div className="stat-card-top">
              <div className="stat-icon violet">
                <ClipboardCheck size={19} />
              </div>

              <ArrowUpRight className="stat-arrow" size={17} />
            </div>

            <div className="stat-content">
              <span>Assessments</span>
              <strong>{String(assessmentResults.length).padStart(2, "0")}</strong>

              <div className="stat-meta">
                <span>Across all engagements</span>
              </div>
            </div>
          </article>

          <article
            className="stat-card clickable-card"
            onClick={() => navigate("/findings")}
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                navigate("/findings");
              }
            }}
          >
            <div className="stat-card-top">
              <div className="stat-icon orange">
                <FileWarning size={19} />
              </div>

              <ArrowUpRight className="stat-arrow" size={17} />
            </div>

            <div className="stat-content">
              <span>Open Findings</span>
              <strong>{String(activeFindings.length).padStart(2, "0")}</strong>

              <div className="stat-meta warning">
                <AlertTriangle size={13} />
                <span>{activeFindings.length} require action</span>
              </div>
            </div>
          </article>

          <article
            className="stat-card clickable-card"
            onClick={() => navigate("/risks")}
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                navigate("/risks");
              }
            }}
          >
            <div className="stat-card-top">
              <div className="stat-icon red">
                <CircleAlert size={19} />
              </div>

              <ArrowUpRight className="stat-arrow" size={17} />
            </div>

            <div className="stat-content">
              <span>Active Risks</span>
              <strong>{String(activeRisks.length).padStart(2, "0")}</strong>

              <div className="stat-meta danger">
                <ShieldAlert size={13} />
                <span>{criticalRisks} critical</span>
              </div>
            </div>
          </article>
        </section>

        {/* =====================================================
            SECURITY POSTURE + RISK
        ===================================================== */}

        <section className="dashboard-grid">
          <article className="panel posture-panel">
            <div className="panel-header">
              <div>
                <span className="panel-kicker">COMPLIANCE</span>
                <h2>Security Posture</h2>
                <p>
                  Overall control compliance across active engagements.
                </p>
              </div>

              <button
                className="panel-icon-button"
                title="View assessments"
                onClick={() => navigate("/assessments")}
              >
                <BarChart3 size={19} />
              </button>
            </div>

            <div className="posture-content">
              <div className="compliance-visual">
                <div className="compliance-ring">
                  <div className="compliance-ring-inner">
                    <strong>{compliance}%</strong>
                    <span>Compliant</span>
                  </div>
                </div>

                <div className="compliance-caption">
                  <CheckCircle2 size={14} />
                  <span>Live from assessment data</span>
                </div>
              </div>

              <div className="posture-list">
                <div className="posture-row">
                  <span>
                    <i className="legend-dot compliant" />
                    Compliant
                  </span>

                  <div className="posture-value">
                    <strong>{compliance}%</strong>

                    <div className="mini-progress">
                      <span style={{ width: `${compliance}%` }} />
                    </div>
                  </div>
                </div>

                <div className="posture-row">
                  <span>
                    <i className="legend-dot non-compliant" />
                    Non-Compliant
                  </span>

                  <div className="posture-value">
                    <strong>{Math.max(0, 100 - compliance)}%</strong>

                    <div className="mini-progress">
                      <span style={{ width: `${Math.max(0, 100 - compliance)}%` }} />
                    </div>
                  </div>
                </div>

                <div className="posture-row">
                  <span>
                    <i className="legend-dot reviewed" />
                    Not Reviewed
                  </span>

                  <div className="posture-value">
                    <strong>0%</strong>

                    <div className="mini-progress">
                      <span style={{ width: "0%" }} />
                    </div>
                  </div>
                </div>

                <button
                  className="inline-action"
                  onClick={() => navigate("/assessments")}
                >
                  View assessment details
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </article>

          <article
            className="panel risk-panel clickable-panel"
            onClick={() => navigate("/risks")}
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                navigate("/risks");
              }
            }}
          >
            <div className="panel-header">
              <div>
                <span className="panel-kicker">RISK REGISTER</span>
                <h2>Risk Overview</h2>
                <p>Current exposure by risk severity.</p>
              </div>

              <div className="risk-score">
                <span>Exposure</span>
                <strong>{totalRiskExposure}</strong>
              </div>
            </div>

            <div className="risk-list">
              {riskCounts.map((risk) => (
                <div className="risk-row" key={risk.label}>
                  <div className="risk-label">
                    <span
                      className={`risk-indicator ${risk.className}`}
                    />

                    <div>
                      <strong>{risk.label}</strong>
                      <span>{risk.description}</span>
                    </div>
                  </div>

                  <div className="risk-bar">
                    <span
                      className={`risk-fill ${risk.className}`}
                      style={{
                        width: `${Math.max(risk.value * 20, 10)}%`,
                      }}
                    />
                  </div>

                  <strong className="risk-count">
                    {risk.value}
                  </strong>
                </div>
              ))}
            </div>

            <div className="risk-footer">
              <span>
                <ShieldAlert size={14} />
                {activeRisks.length} total active risks
              </span>

              <button
                className="text-button"
                onClick={(event) => {
                  event.stopPropagation();
                  navigate("/risks");
                }}
              >
                Open risk register
                <ArrowRight size={14} />
              </button>
            </div>
          </article>
        </section>

        {/* =====================================================
            ACTIVE ENGAGEMENTS
        ===================================================== */}

        <section className="panel engagements-panel">
          <div className="panel-header">
            <div>
              <span className="panel-kicker">WORKSPACE</span>
              <h2>Active Engagements</h2>
              <p>
                Security assessments currently being reviewed by your team.
              </p>
            </div>

            <button
              className="text-button"
              onClick={() => navigate("/engagements")}
            >
              View all
              <ArrowRight size={15} />
            </button>
          </div>

          <div className="engagement-table">
            <div className="table-row table-head">
              <span>CLIENT</span>
              <span>TECHNOLOGY</span>
              <span>PROGRESS</span>
              <span>REVIEWER</span>
              <span>STATUS</span>
              <span>UPDATED</span>
              <span />
            </div>

            {filteredEngagements.length > 0 ? (
              filteredEngagements.map((engagement) => (
                <div
                  className="table-row clickable-row"
                  key={engagement.id}
                  onClick={() =>
                    navigate(`/engagements?id=${engagement.id}`)
                  }
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      navigate(`/engagements?id=${engagement.id}`);
                    }
                  }}
                >
                  <div className="client-cell">
                    <div className="client-avatar">
                      {engagement.client.charAt(0)}
                    </div>

                    <div className="client-info">
                      <strong>{engagement.client}</strong>
                      <span>{engagement.id}</span>
                    </div>
                  </div>

                  <span className="technology-badge">
                    <Layers3 size={13} />
                    {engagement.technology}
                  </span>

                  <div className="progress-cell">
                    <div className="progress-track">
                      <span
                        style={{
                          width: `${engagement.progress}%`,
                        }}
                      />
                    </div>

                    <small>{engagement.progress}%</small>
                  </div>

                  <span className="reviewer">
                    {engagement.reviewer}
                  </span>

                  <span
                    className={`engagement-status ${
                      engagement.status === "Completed"
                        ? "completed"
                        : engagement.status === "At Risk"
                          ? "at-risk"
                          : "in-progress"
                    }`}
                  >
                    {engagement.status === "Completed" ? (
                      <CheckCircle2 size={13} />
                    ) : engagement.status === "At Risk" ? (
                      <XCircle size={13} />
                    ) : (
                      <Activity size={13} />
                    )}

                    {engagement.status}
                  </span>

                  <span className="updated-time">
                    <Clock3 size={13} />
                    {engagement.updated}
                  </span>

                  <ChevronRight
                    className="row-arrow"
                    size={17}
                  />
                </div>
              ))
            ) : (
              <div className="empty-state">
                <Search size={22} />
                <strong>No engagements found</strong>
                <span>Try another search term.</span>
              </div>
            )}
          </div>
        </section>

        {/* =====================================================
            BOTTOM SECTION
        ===================================================== */}

        <section className="bottom-grid">
          {/* TECHNOLOGY COVERAGE */}

          <article className="panel technology-panel">
            <div className="panel-header">
              <div>
                <span className="panel-kicker">INFRASTRUCTURE</span>
                <h2>Technology Coverage</h2>
                <p>
                  Technologies currently covered by your security program.
                </p>
              </div>

              <button
                className="panel-icon-button"
                onClick={() => navigate("/checklists")}
              >
                <Layers3 size={18} />
              </button>
            </div>

            <div className="technology-cards">
              {technologyCoverage.length > 0 ? technologyCoverage.map((item) => (
                <button className="technology-card" key={item.technology} onClick={() => navigate("/checklists")}>
                  <div className={`technology-logo ${item.technology.toLowerCase().includes("windows") ? "windows" : "linux"}`}>
                    {item.technology.charAt(0).toUpperCase()}
                  </div>
                  <div className="technology-info">
                    <strong>{item.technology}</strong>
                    <span>{item.count} engagement{item.count === 1 ? "" : "s"}</span>
                  </div>
                  <div className="technology-score">
                    <strong>{item.percentage}%</strong>
                    <span>coverage</span>
                  </div>
                  <ChevronRight size={17} />
                </button>
              )) : (
                <div className="empty-state">
                  <Layers3 size={22} />
                  <strong>No technology data</strong>
                  <span>Create an engagement to begin.</span>
                </div>
              )}
            </div>

            <button
              className="coverage-action"
              onClick={() => navigate("/checklists")}
            >
              Manage technology checklists
              <ArrowRight size={14} />
            </button>
          </article>

          {/* RECENT ACTIVITY */}

          <article className="panel activity-panel">
            <div className="panel-header">
              <div>
                <span className="panel-kicker">ACTIVITY</span>
                <h2>Recent Activity</h2>
                <p>Latest security operations in your workspace.</p>
              </div>

              <Activity size={19} />
            </div>

            <div className="activity-list">
              {activities.map((activity) => {
                const Icon = activity.icon;

                return (
                  <div className="activity-item" key={activity.title}>
                    <div className={`activity-icon ${activity.tone}`}>
                      <Icon size={15} />
                    </div>

                    <div className="activity-content">
                      <strong>{activity.title}</strong>
                      <span>{activity.description}</span>
                    </div>

                    <time>{activity.time}</time>
                  </div>
                );
              })}
            </div>

            <button
              className="coverage-action"
              onClick={() => navigate("/findings")}
            >
              View security activity
              <ArrowRight size={14} />
            </button>
          </article>

          {/* AI */}

          <article className="automation-card">
            <div className="automation-top">
              <div className="automation-icon">
                <Sparkles size={23} />
              </div>

              <span className="ai-badge">
                <Sparkles size={12} />
                AI ASSISTED
              </span>
            </div>

            <span className="panel-kicker">
              INTELLIGENT SECURITY
            </span>

            <h2>Agentic Automation</h2>

            <p>
              Generate security checklists, analyze findings and
              accelerate risk workflows with AI-assisted security
              operations.
            </p>

            <div className="automation-features">
              <span>
                <CheckCircle2 size={13} />
                Checklist generation
              </span>

              <span>
                <CheckCircle2 size={13} />
                Finding analysis
              </span>

              <span>
                <CheckCircle2 size={13} />
                Risk assistance
              </span>
            </div>

            <button
              className="automation-button"
              onClick={() => navigate("/checklists")}
            >
              Explore AI Features
              <ArrowUpRight size={16} />
            </button>
          </article>
        </section>

        {/* =====================================================
            FOOTER
        ===================================================== */}

        <style>{`@keyframes sentinel-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } } .spin { animation: sentinel-spin .9s linear infinite; }`}</style>

        <footer className="dashboard-footer">
          <div>
            <Shield size={14} />
            <span>Sentinel GRC</span>
            <span className="footer-version">v1.0</span>
          </div>

          <div>
            <span>
              Security Configuration &amp; Compliance Platform
            </span>

            <span className="footer-separator">•</span>

            <span>Updated {lastUpdated}</span>
          </div>
        </footer>
      </main>
    </div>
  );
}

export default Dashboard;