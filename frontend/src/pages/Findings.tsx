import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  FileWarning,
  Filter,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import "./Findings.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Engagement = {
  engagement_id: string;
  client_name: string;
  technology: string;
  reviewer: string;
};

type ChecklistItem = {
  item_id: string;
  category: string;
  control: string;
  reference: string;
  audit_step: string;
};

type AssessmentResult = {
  item_id: string;
  status: string;
  notes: string;
};

type Assessment = {
  engagement_id: string;
  results: AssessmentResult[];
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

const severityOptions = ["Critical", "High", "Medium", "Low"];

const statusOptions = ["Open", "In Progress", "Resolved", "Accepted"];

function Findings() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedEngagement, setSelectedEngagement] = useState("");

  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const [form, setForm] = useState({
    title: "",
    description: "",
    item_id: "",
    severity: "High",
    recommendation: "",
    status: "Open",
  });

  useEffect(() => {
    loadEngagements();
  }, []);

  useEffect(() => {
    if (selectedEngagement) {
      loadEngagementData(selectedEngagement);
    }
  }, [selectedEngagement]);

  async function loadEngagements() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_URL}/engagements`);

      if (!response.ok) {
        throw new Error("Failed to load engagements.");
      }

      const data = await response.json();
      const items = data.engagements || [];

      setEngagements(items);

      if (items.length > 0) {
        setSelectedEngagement(items[0].engagement_id);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load engagements."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadEngagementData(engagementId: string) {
    try {
      setLoadingData(true);
      setError("");

      const engagement = engagements.find(
        (item) => item.engagement_id === engagementId
      );

      if (!engagement) {
        return;
      }

      const [checklistResponse, assessmentResponse, findingsResponse] =
        await Promise.all([
          fetch(`${API_URL}/checklists/${engagement.technology}`),
          fetch(`${API_URL}/assessments/${engagementId}`),
          fetch(`${API_URL}/findings/${engagementId}`),
        ]);

      if (!checklistResponse.ok) {
        throw new Error("Failed to load checklist.");
      }

      if (!assessmentResponse.ok) {
        throw new Error("Failed to load assessments.");
      }

      if (!findingsResponse.ok) {
        throw new Error("Failed to load findings.");
      }

      const checklistData = await checklistResponse.json();
      const assessmentData = await assessmentResponse.json();
      const findingsData = await findingsResponse.json();

      setChecklist(checklistData.checklist || []);
      setAssessments(assessmentData.assessments || []);
      setFindings(findingsData.findings || []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load finding data."
      );
    } finally {
      setLoadingData(false);
    }
  }

  async function refresh() {
    if (selectedEngagement) {
      await loadEngagementData(selectedEngagement);
    } else {
      await loadEngagements();
    }
  }

  const selectedEngagementDetails = engagements.find(
    (item) => item.engagement_id === selectedEngagement
  );

  const assessedItemIds = useMemo(() => {
    const ids = new Set<string>();

    assessments.forEach((assessment) => {
      assessment.results?.forEach((result) => {
        if (
          result.status &&
          !["not reviewed", "not applicable"].includes(
            result.status.toLowerCase()
          )
        ) {
          ids.add(result.item_id);
        }
      });
    });

    return ids;
  }, [assessments]);

  const assessedControls = useMemo(
    () => checklist.filter((item) => assessedItemIds.has(item.item_id)),
    [checklist, assessedItemIds]
  );

  const filteredFindings = useMemo(() => {
    const query = search.trim().toLowerCase();

    return findings.filter((finding) => {
      const matchesSearch =
        !query ||
        finding.finding_id.toLowerCase().includes(query) ||
        finding.title.toLowerCase().includes(query) ||
        finding.item_id.toLowerCase().includes(query) ||
        finding.description.toLowerCase().includes(query);

      const matchesSeverity =
        severityFilter === "All" ||
        finding.severity.toLowerCase() === severityFilter.toLowerCase();

      const matchesStatus =
        statusFilter === "All" ||
        finding.status.toLowerCase() === statusFilter.toLowerCase();

      return matchesSearch && matchesSeverity && matchesStatus;
    });
  }, [findings, search, severityFilter, statusFilter]);

  const criticalCount = findings.filter(
    (item) => item.severity.toLowerCase() === "critical"
  ).length;

  const highCount = findings.filter(
    (item) => item.severity.toLowerCase() === "high"
  ).length;

  const openCount = findings.filter(
    (item) => item.status.toLowerCase() === "open"
  ).length;

  async function createFinding() {
    if (!selectedEngagement) {
      setError("Select an engagement first.");
      return;
    }

    if (!form.title.trim()) {
      setError("Finding title is required.");
      return;
    }

    if (!form.item_id) {
      setError("Select an assessed control.");
      return;
    }

    try {
      setCreating(true);
      setError("");
      setSuccessMessage("");

      const findingId = `FND-${Date.now().toString().slice(-6)}`;

      const response = await fetch(`${API_URL}/findings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          finding_id: findingId,
          engagement_id: selectedEngagement,
          item_id: form.item_id,
          title: form.title.trim(),
          description: form.description.trim(),
          severity: form.severity,
          recommendation: form.recommendation.trim(),
          status: form.status,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to create finding.");
      }

      if (!data.finding) {
        throw new Error(data.message || "Finding could not be created.");
      }

      setSuccessMessage("Finding created successfully.");

      setForm({
        title: "",
        description: "",
        item_id: "",
        severity: "High",
        recommendation: "",
        status: "Open",
      });

      setShowCreate(false);

      await loadEngagementData(selectedEngagement);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create finding."
      );
    } finally {
      setCreating(false);
    }
  }

  function severityClass(severity: string) {
    switch (severity.toLowerCase()) {
      case "critical":
        return "finding-severity critical";
      case "high":
        return "finding-severity high";
      case "medium":
        return "finding-severity medium";
      default:
        return "finding-severity low";
    }
  }

  function statusClass(status: string) {
    switch (status.toLowerCase()) {
      case "resolved":
        return "finding-status resolved";
      case "in progress":
        return "finding-status progress";
      case "accepted":
        return "finding-status accepted";
      default:
        return "finding-status open";
    }
  }

  if (loading) {
    return (
      <main className="findings-page">
        <div className="findings-loading">
          <RefreshCw size={22} className="spin" />
          <span>Loading findings workspace...</span>
        </div>
      </main>
    );
  }

  return (
    <main className="findings-page">
      <div className="findings-orb findings-orb-one" />
      <div className="findings-orb findings-orb-two" />

      <section className="findings-shell">
        <header className="findings-header">
          <div>
            <div className="findings-eyebrow">
              <ShieldAlert size={15} />
              Security Findings
            </div>

            <h1>Findings</h1>

            <p>
              Review, document and track security findings identified during
              configuration assessments.
            </p>
          </div>

          <div className="findings-header-actions">
            <button
              className="findings-secondary-button"
              onClick={refresh}
              disabled={loadingData}
            >
              <RefreshCw
                size={16}
                className={loadingData ? "spin" : ""}
              />
              Refresh
            </button>

            <button
              className="findings-primary-button"
              onClick={() => {
                setError("");
                setSuccessMessage("");
                setShowCreate(true);
              }}
              disabled={!selectedEngagement}
            >
              <Plus size={17} />
              New Finding
            </button>
          </div>
        </header>

        {error && (
          <div className="findings-alert error">
            <AlertCircle size={17} />
            <span>{error}</span>
            <button onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="findings-alert success">
            <CheckCircle2 size={17} />
            <span>{successMessage}</span>
            <button onClick={() => setSuccessMessage("")}>
              <X size={16} />
            </button>
          </div>
        )}

        <section className="finding-context-card">
          <div>
            <span className="context-label">Assessment Engagement</span>
            <div className="engagement-select-wrapper">
              <select
                value={selectedEngagement}
                onChange={(event) => {
                  setSelectedEngagement(event.target.value);
                  setSuccessMessage("");
                  setError("");
                }}
              >
                {engagements.map((engagement) => (
                  <option
                    key={engagement.engagement_id}
                    value={engagement.engagement_id}
                  >
                    {engagement.engagement_id} — {engagement.client_name}
                  </option>
                ))}
              </select>
              <ChevronDown size={17} />
            </div>
          </div>

          {selectedEngagementDetails && (
            <div className="engagement-meta">
              <span>
                Technology{" "}
                <strong>{selectedEngagementDetails.technology}</strong>
              </span>
              <span>
                Reviewer{" "}
                <strong>{selectedEngagementDetails.reviewer}</strong>
              </span>
            </div>
          )}
        </section>

        <section className="finding-kpis">
          <div className="finding-kpi-card">
            <div className="finding-kpi-icon total">
              <FileWarning size={19} />
            </div>
            <div>
              <span>Total Findings</span>
              <strong>{findings.length}</strong>
            </div>
          </div>

          <div className="finding-kpi-card">
            <div className="finding-kpi-icon critical">
              <ShieldAlert size={19} />
            </div>
            <div>
              <span>Critical</span>
              <strong>{criticalCount}</strong>
            </div>
          </div>

          <div className="finding-kpi-card">
            <div className="finding-kpi-icon high">
              <AlertCircle size={19} />
            </div>
            <div>
              <span>High Severity</span>
              <strong>{highCount}</strong>
            </div>
          </div>

          <div className="finding-kpi-card">
            <div className="finding-kpi-icon open">
              <FileWarning size={19} />
            </div>
            <div>
              <span>Open</span>
              <strong>{openCount}</strong>
            </div>
          </div>
        </section>

        <section className="findings-panel">
          <div className="panel-header">
            <div>
              <h2>Finding Register</h2>
              <p>
                Findings recorded against assessed security controls.
              </p>
            </div>

            <div className="panel-count">
              {filteredFindings.length}{" "}
              {filteredFindings.length === 1 ? "finding" : "findings"}
            </div>
          </div>

          <div className="findings-toolbar">
            <div className="finding-search">
              <Search size={17} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search findings..."
              />
            </div>

            <div className="finding-filter">
              <Filter size={15} />
              <select
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value)}
              >
                <option value="All">All severity</option>
                {severityOptions.map((severity) => (
                  <option key={severity} value={severity}>
                    {severity}
                  </option>
                ))}
              </select>
            </div>

            <div className="finding-filter">
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                <option value="All">All status</option>
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {loadingData ? (
            <div className="findings-empty">
              <RefreshCw size={22} className="spin" />
              <span>Loading engagement findings...</span>
            </div>
          ) : filteredFindings.length === 0 ? (
            <div className="findings-empty">
              <div className="empty-icon">
                <FileWarning size={22} />
              </div>
              <h3>No findings found</h3>
              <p>
                {findings.length === 0
                  ? "No findings have been recorded for this engagement yet."
                  : "Try changing your search or filters."}
              </p>
            </div>
          ) : (
            <div className="findings-table-wrapper">
              <table className="findings-table">
                <thead>
                  <tr>
                    <th>Finding</th>
                    <th>Control</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Recommendation</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredFindings.map((finding) => (
                    <tr key={finding.finding_id}>
                      <td>
                        <div className="finding-title-cell">
                          <span className="finding-id">
                            {finding.finding_id}
                          </span>
                          <strong>{finding.title}</strong>
                          <span className="finding-description">
                            {finding.description || "No description provided."}
                          </span>
                        </div>
                      </td>

                      <td>
                        <span className="control-chip">
                          {finding.item_id}
                        </span>
                      </td>

                      <td>
                        <span className={severityClass(finding.severity)}>
                          {finding.severity}
                        </span>
                      </td>

                      <td>
                        <span className={statusClass(finding.status)}>
                          {finding.status}
                        </span>
                      </td>

                      <td>
                        <span className="recommendation-cell">
                          {finding.recommendation ||
                            "No recommendation provided."}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>

      {showCreate && (
        <div
          className="finding-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setShowCreate(false);
            }
          }}
        >
          <div className="finding-modal">
            <div className="modal-header">
              <div>
                <span className="findings-eyebrow">
                  <Plus size={14} />
                  Finding Management
                </span>
                <h2>Create Finding</h2>
                <p>
                  Record a finding against an assessed security control.
                </p>
              </div>

              <button
                className="modal-close"
                onClick={() => setShowCreate(false)}
              >
                <X size={19} />
              </button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>Assessed Control *</label>

                <select
                  value={form.item_id}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      item_id: event.target.value,
                    })
                  }
                >
                  <option value="">
                    Select an assessed control
                  </option>

                  {assessedControls.map((item) => (
                    <option key={item.item_id} value={item.item_id}>
                      {item.item_id} — {item.control}
                    </option>
                  ))}
                </select>

                {assessedControls.length === 0 && (
                  <small className="form-help warning-text">
                    No assessed controls are available. Complete an
                    assessment first.
                  </small>
                )}
              </div>

              <div className="form-group">
                <label>Finding Title *</label>
                <input
                  value={form.title}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      title: event.target.value,
                    })
                  }
                  placeholder="e.g. Root login is enabled"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Severity</label>
                  <select
                    value={form.severity}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        severity: event.target.value,
                      })
                    }
                  >
                    {severityOptions.map((severity) => (
                      <option key={severity} value={severity}>
                        {severity}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
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
                    {statusOptions.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={form.description}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      description: event.target.value,
                    })
                  }
                  placeholder="Describe the security issue and observed condition..."
                  rows={4}
                />
              </div>

              <div className="form-group">
                <label>Recommendation</label>
                <textarea
                  value={form.recommendation}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      recommendation: event.target.value,
                    })
                  }
                  placeholder="Describe the recommended remediation..."
                  rows={4}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="findings-secondary-button"
                onClick={() => setShowCreate(false)}
                disabled={creating}
              >
                Cancel
              </button>

              <button
                className="findings-primary-button"
                onClick={createFinding}
                disabled={
                  creating ||
                  !form.title.trim() ||
                  !form.item_id ||
                  assessedControls.length === 0
                }
              >
                {creating ? (
                  <>
                    <RefreshCw size={16} className="spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus size={17} />
                    Create Finding
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

export default Findings;