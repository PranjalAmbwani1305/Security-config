import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  Plus,
  RefreshCw,
  ShieldAlert,
  Target,
  X,
} from "lucide-react";
import "./Risks.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Engagement = {
  engagement_id: string;
  client_name: string;
  technology: string;
  reviewer: string;
};

type Finding = {
  finding_id: string;
  engagement_id: string;
  item_id: string;
  title: string;
  description: string;
  severity: string;
  recommendation: string;
  status: string;
};

type Risk = {
  risk_id: string;
  engagement_id: string;
  finding_id: string;
  title: string;
  likelihood: number;
  impact: number;
  risk_score: number;
  risk_level: string;
  treatment: string;
  owner: string;
  status: string;
};

const treatmentOptions = ["Mitigate", "Accept", "Transfer", "Avoid"];
const statusOptions = ["Open", "Monitoring", "Closed"];

function Risks() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedEngagement, setSelectedEngagement] = useState("");
  const [findings, setFindings] = useState<Finding[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createMessage, setCreateMessage] = useState("");

  const [search, setSearch] = useState("");
  const [levelFilter, setLevelFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");

  const [form, setForm] = useState({
    finding_id: "",
    title: "",
    likelihood: 3,
    impact: 3,
    treatment: "Mitigate",
    owner: "",
    status: "Open",
  });

  async function loadEngagements() {
    const response = await fetch(`${API_URL}/engagements`);

    if (!response.ok) {
      throw new Error("Unable to load engagements.");
    }

    const data = await response.json();
    const list = data.engagements || [];

    setEngagements(list);

    if (!selectedEngagement && list.length > 0) {
      setSelectedEngagement(list[0].engagement_id);
    }
  }

  async function loadRiskData(engagementId: string) {
    if (!engagementId) {
      setFindings([]);
      setRisks([]);
      return;
    }

    const [findingsResponse, risksResponse] = await Promise.all([
      fetch(`${API_URL}/findings/${engagementId}`),
      fetch(`${API_URL}/risks/${engagementId}`),
    ]);

    if (!findingsResponse.ok) {
      throw new Error("Unable to load findings.");
    }

    if (!risksResponse.ok) {
      throw new Error("Unable to load risks.");
    }

    const findingsData = await findingsResponse.json();
    const risksData = await risksResponse.json();

    setFindings(findingsData.findings || []);
    setRisks(risksData.risks || []);
  }

  async function loadAll() {
    try {
      setError("");

      if (engagements.length === 0) {
        await loadEngagements();
      }

      const engagementId =
        selectedEngagement ||
        engagements[0]?.engagement_id ||
        "";

      if (engagementId) {
        await loadRiskData(engagementId);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while loading risk data."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (!selectedEngagement) return;

    loadRiskData(selectedEngagement).catch((err) => {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load risk data."
      );
    });
  }, [selectedEngagement]);

  async function refresh() {
    try {
      setRefreshing(true);
      setError("");
      await loadRiskData(selectedEngagement);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to refresh risk data."
      );
    } finally {
      setRefreshing(false);
    }
  }

  function openCreateModal() {
    setCreateMessage("");

    setForm({
      finding_id: findings[0]?.finding_id || "",
      title: "",
      likelihood: 3,
      impact: 3,
      treatment: "Mitigate",
      owner: "",
      status: "Open",
    });

    setShowModal(true);
  }

  async function createRisk(event: React.FormEvent) {
    event.preventDefault();

    if (!selectedEngagement) {
      setCreateMessage("Select an engagement first.");
      return;
    }

    if (!form.finding_id) {
      setCreateMessage("Select a related finding.");
      return;
    }

    if (!form.title.trim()) {
      setCreateMessage("Enter a risk title.");
      return;
    }

    if (!form.owner.trim()) {
      setCreateMessage("Enter a risk owner.");
      return;
    }

    try {
      setCreating(true);
      setCreateMessage("");

      const riskId = `RSK-${crypto.randomUUID()
        .replace(/-/g, "")
        .slice(0, 6)
        .toUpperCase()}`;

      const response = await fetch(`${API_URL}/risks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          risk_id: riskId,
          engagement_id: selectedEngagement,
          finding_id: form.finding_id,
          title: form.title.trim(),
          likelihood: Number(form.likelihood),
          impact: Number(form.impact),
          treatment: form.treatment,
          owner: form.owner.trim(),
          status: form.status,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.message || "Unable to create risk."
        );
      }

      setShowModal(false);
      await loadRiskData(selectedEngagement);
    } catch (err) {
      setCreateMessage(
        err instanceof Error
          ? err.message
          : "Unable to create risk."
      );
    } finally {
      setCreating(false);
    }
  }

  const selectedEngagementDetails = engagements.find(
    (engagement) =>
      engagement.engagement_id === selectedEngagement
  );

  const filteredRisks = useMemo(() => {
    const normalizedSearch = search.toLowerCase().trim();

    return risks.filter((risk) => {
      const matchesSearch =
        !normalizedSearch ||
        risk.title.toLowerCase().includes(normalizedSearch) ||
        risk.risk_id.toLowerCase().includes(normalizedSearch) ||
        risk.owner.toLowerCase().includes(normalizedSearch) ||
        risk.finding_id.toLowerCase().includes(normalizedSearch);

      const matchesLevel =
        levelFilter === "All" ||
        risk.risk_level.toLowerCase() === levelFilter.toLowerCase();

      const matchesStatus =
        statusFilter === "All" ||
        risk.status.toLowerCase() === statusFilter.toLowerCase();

      return matchesSearch && matchesLevel && matchesStatus;
    });
  }, [risks, search, levelFilter, statusFilter]);

  const stats = useMemo(() => {
    return {
      total: risks.length,
      critical: risks.filter(
        (risk) => risk.risk_level === "Critical"
      ).length,
      high: risks.filter(
        (risk) => risk.risk_level === "High"
      ).length,
      medium: risks.filter(
        (risk) => risk.risk_level === "Medium"
      ).length,
      low: risks.filter(
        (risk) => risk.risk_level === "Low"
      ).length,
      open: risks.filter(
        (risk) => risk.status === "Open"
      ).length,
    };
  }, [risks]);

  const totalExposure = useMemo(
    () =>
      risks.reduce(
        (total, risk) => total + Number(risk.risk_score || 0),
        0
      ),
    [risks]
  );

  function levelClass(level: string) {
    return `risk-level risk-level-${level.toLowerCase()}`;
  }

  function statusClass(status: string) {
    return `risk-status risk-status-${status.toLowerCase().replace(" ", "-")}`;
  }

  if (loading) {
    return (
      <main className="risks-page">
        <div className="risks-loading">
          <RefreshCw size={20} className="spin" />
          Loading risk register...
        </div>
      </main>
    );
  }

  return (
    <main className="risks-page">
      <section className="risks-header">
        <div>
          <div className="risks-kicker">
            <ShieldAlert size={14} />
            RISK MANAGEMENT
          </div>

          <h1>Risk Register</h1>

          <p>
            Identify, assess, treat, and monitor security risks
            across active engagements.
          </p>
        </div>

        <div className="risks-header-actions">
          <button
            className="secondary-button"
            onClick={refresh}
            disabled={refreshing}
          >
            <RefreshCw
              size={16}
              className={refreshing ? "spin" : ""}
            />
            Refresh
          </button>

          <button
            className="primary-button"
            onClick={openCreateModal}
            disabled={findings.length === 0}
          >
            <Plus size={17} />
            Create Risk
          </button>
        </div>
      </section>

      {error && (
        <div className="risk-alert">
          <AlertTriangle size={17} />
          {error}
        </div>
      )}

      <section className="risk-context">
        <div className="context-field">
          <label>ENGAGEMENT</label>

          <div className="select-wrapper">
            <select
              value={selectedEngagement}
              onChange={(event) =>
                setSelectedEngagement(event.target.value)
              }
            >
              {engagements.length === 0 && (
                <option value="">No engagements available</option>
              )}

              {engagements.map((engagement) => (
                <option
                  key={engagement.engagement_id}
                  value={engagement.engagement_id}
                >
                  {engagement.client_name} ·{" "}
                  {engagement.engagement_id}
                </option>
              ))}
            </select>

            <ChevronDown size={16} />
          </div>
        </div>

        {selectedEngagementDetails && (
          <div className="context-meta">
            <span>
              {selectedEngagementDetails.technology}
            </span>
            <span className="context-divider" />
            <span>
              Reviewer: {selectedEngagementDetails.reviewer}
            </span>
          </div>
        )}
      </section>

      <section className="risk-stats">
        <div className="risk-stat-card">
          <div className="stat-icon neutral">
            <ShieldAlert size={18} />
          </div>

          <div>
            <span>Total Risks</span>
            <strong>{stats.total}</strong>
          </div>
        </div>

        <div className="risk-stat-card critical-card">
          <div className="stat-icon critical">
            <AlertTriangle size={18} />
          </div>

          <div>
            <span>Critical</span>
            <strong>{stats.critical}</strong>
          </div>
        </div>

        <div className="risk-stat-card high-card">
          <div className="stat-icon high">
            <Target size={18} />
          </div>

          <div>
            <span>High</span>
            <strong>{stats.high}</strong>
          </div>
        </div>

        <div className="risk-stat-card">
          <div className="stat-icon neutral">
            <ShieldAlert size={18} />
          </div>

          <div>
            <span>Open</span>
            <strong>{stats.open}</strong>
          </div>
        </div>

        <div className="risk-stat-card exposure-card">
          <div className="stat-icon exposure">
            <Target size={18} />
          </div>

          <div>
            <span>Exposure Score</span>
            <strong>{totalExposure}</strong>
          </div>
        </div>
      </section>

      <section className="risk-overview-grid">
        <article className="risk-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">SEVERITY DISTRIBUTION</span>
              <h2>Risk Exposure</h2>
            </div>

            <span className="panel-caption">
              {risks.length} recorded
            </span>
          </div>

          <div className="severity-bars">
            {[
              {
                label: "Critical",
                count: stats.critical,
                className: "critical",
              },
              {
                label: "High",
                count: stats.high,
                className: "high",
              },
              {
                label: "Medium",
                count: stats.medium,
                className: "medium",
              },
              {
                label: "Low",
                count: stats.low,
                className: "low",
              },
            ].map((item) => (
              <div className="severity-row" key={item.label}>
                <div className="severity-label">
                  <span
                    className={`severity-dot ${item.className}`}
                  />
                  <span>{item.label}</span>
                </div>

                <div className="severity-track">
                  <span
                    className={`severity-fill ${item.className}`}
                    style={{
                      width: `${
                        stats.total
                          ? Math.max(
                              (item.count / stats.total) * 100,
                              item.count ? 8 : 0
                            )
                          : 0
                      }%`,
                    }}
                  />
                </div>

                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="risk-panel score-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-kicker">RISK MODEL</span>
              <h2>Likelihood × Impact</h2>
            </div>
          </div>

          <div className="score-content">
            <div className="score-orb">
              <span>EXPOSURE</span>
              <strong>{totalExposure}</strong>
            </div>

            <div className="score-description">
              <p>
                Risk score is calculated by the backend from
                likelihood multiplied by impact.
              </p>

              <div className="score-scale">
                <span>1</span>
                <div className="scale-track">
                  <span />
                </div>
                <span>25</span>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section className="risk-register-panel">
        <div className="register-header">
          <div>
            <span className="panel-kicker">RISK REGISTER</span>
            <h2>Security Risks</h2>
            <p>
              Review current exposure and treatment status.
            </p>
          </div>

          <div className="register-filters">
            <input
              type="text"
              placeholder="Search risks..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />

            <select
              value={levelFilter}
              onChange={(event) =>
                setLevelFilter(event.target.value)
              }
            >
              <option value="All">All levels</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>

            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value)
              }
            >
              <option value="All">All statuses</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>
        </div>

        {findings.length === 0 && (
          <div className="empty-state">
            <ShieldAlert size={28} />
            <h3>No findings available</h3>
            <p>
              Create at least one finding before creating a
              risk.
            </p>
          </div>
        )}

        {findings.length > 0 && risks.length === 0 && (
          <div className="empty-state">
            <ShieldAlert size={28} />
            <h3>No risks recorded</h3>
            <p>
              Use <strong>Create Risk</strong> to add the first
              risk to this engagement.
            </p>
          </div>
        )}

        {filteredRisks.length > 0 && (
          <div className="risk-table-wrapper">
            <table className="risk-table">
              <thead>
                <tr>
                  <th>RISK</th>
                  <th>RELATED FINDING</th>
                  <th>LEVEL</th>
                  <th>SCORE</th>
                  <th>TREATMENT</th>
                  <th>OWNER</th>
                  <th>STATUS</th>
                </tr>
              </thead>

              <tbody>
                {filteredRisks.map((risk) => (
                  <tr key={risk.risk_id}>
                    <td>
                      <div className="risk-title-cell">
                        <strong>{risk.title}</strong>
                        <span>{risk.risk_id}</span>
                      </div>
                    </td>

                    <td>
                      <span className="finding-id">
                        {risk.finding_id}
                      </span>
                    </td>

                    <td>
                      <span className={levelClass(risk.risk_level)}>
                        {risk.risk_level}
                      </span>
                    </td>

                    <td>
                      <div className="score-cell">
                        <strong>{risk.risk_score}</strong>
                        <span>
                          {risk.likelihood} × {risk.impact}
                        </span>
                      </div>
                    </td>

                    <td>{risk.treatment}</td>

                    <td>
                      <span className="owner-cell">
                        {risk.owner}
                      </span>
                    </td>

                    <td>
                      <span className={statusClass(risk.status)}>
                        {risk.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {risks.length > 0 && filteredRisks.length === 0 && (
          <div className="empty-state compact">
            <h3>No matching risks</h3>
            <p>
              Try changing the search or filter values.
            </p>
          </div>
        )}
      </section>

      {showModal && (
        <div
          className="modal-backdrop"
          onMouseDown={() => setShowModal(false)}
        >
          <div
            className="risk-modal"
            onMouseDown={(event) =>
              event.stopPropagation()
            }
          >
            <div className="modal-header">
              <div>
                <span className="panel-kicker">
                  RISK MANAGEMENT
                </span>
                <h2>Create Risk</h2>
                <p>
                  Register a new security risk against an
                  existing finding.
                </p>
              </div>

              <button
                className="modal-close"
                onClick={() => setShowModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={createRisk}>
              <div className="form-field">
                <label>Related Finding</label>

                <select
                  value={form.finding_id}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      finding_id: event.target.value,
                    })
                  }
                >
                  <option value="">
                    Select a finding
                  </option>

                  {findings.map((finding) => (
                    <option
                      key={finding.finding_id}
                      value={finding.finding_id}
                    >
                      {finding.finding_id} · {finding.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-field">
                <label>Risk Title</label>

                <input
                  type="text"
                  placeholder="e.g. Insecure SSH configuration"
                  value={form.title}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      title: event.target.value,
                    })
                  }
                />
              </div>

              <div className="form-grid">
                <div className="form-field">
                  <label>Likelihood</label>

                  <select
                    value={form.likelihood}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        likelihood: Number(
                          event.target.value
                        ),
                      })
                    }
                  >
                    <option value={1}>1 — Rare</option>
                    <option value={2}>2 — Unlikely</option>
                    <option value={3}>3 — Possible</option>
                    <option value={4}>4 — Likely</option>
                    <option value={5}>5 — Almost Certain</option>
                  </select>
                </div>

                <div className="form-field">
                  <label>Impact</label>

                  <select
                    value={form.impact}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        impact: Number(event.target.value),
                      })
                    }
                  >
                    <option value={1}>1 — Minimal</option>
                    <option value={2}>2 — Minor</option>
                    <option value={3}>3 — Moderate</option>
                    <option value={4}>4 — Major</option>
                    <option value={5}>5 — Severe</option>
                  </select>
                </div>
              </div>

              <div className="risk-preview">
                <div>
                  <span>Calculated score</span>
                  <strong>
                    {form.likelihood * form.impact}
                  </strong>
                </div>

                <div>
                  <span>Risk level</span>
                  <strong
                    className={levelClass(
                      form.likelihood * form.impact <= 4
                        ? "Low"
                        : form.likelihood * form.impact <= 9
                        ? "Medium"
                        : form.likelihood * form.impact <= 16
                        ? "High"
                        : "Critical"
                    )}
                  >
                    {form.likelihood * form.impact <= 4
                      ? "Low"
                      : form.likelihood * form.impact <= 9
                      ? "Medium"
                      : form.likelihood * form.impact <= 16
                      ? "High"
                      : "Critical"}
                  </strong>
                </div>
              </div>

              <div className="form-grid">
                <div className="form-field">
                  <label>Treatment</label>

                  <select
                    value={form.treatment}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        treatment: event.target.value,
                      })
                    }
                  >
                    {treatmentOptions.map((option) => (
                      <option
                        key={option}
                        value={option}
                      >
                        {option}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-field">
                  <label>Status</label>

                  <select
                    value={form.status}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        status: event.target.value,
                      })
                    }
                  >
                    {statusOptions.map((option) => (
                      <option
                        key={option}
                        value={option}
                      >
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-field">
                <label>Risk Owner</label>

                <input
                  type="text"
                  placeholder="e.g. Infrastructure Team"
                  value={form.owner}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      owner: event.target.value,
                    })
                  }
                />
              </div>

              {createMessage && (
                <div className="form-error">
                  <AlertTriangle size={15} />
                  {createMessage}
                </div>
              )}

              <div className="modal-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="primary-button"
                  disabled={creating}
                >
                  {creating ? (
                    <>
                      <RefreshCw size={16} className="spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Plus size={16} />
                      Create Risk
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

export default Risks;