import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  FileCheck2,
  FileText,
  Filter,
  FolderOpen,
  Loader2,
  RefreshCw,
  Search,
  Shield,
  UploadCloud,
  XCircle,
} from "lucide-react";

import "./Evidence.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Engagement = {
  engagement_id: string;
  client_name: string;
  technology: string;
  reviewer: string;
  results: unknown[];
};

type Evidence = {
  evidence_id?: string;
  engagement_id?: string;
  file_name?: string;
  filename?: string;
  evidence_type?: string;
  type?: string;
  description?: string;
  status?: string;
  uploaded_by?: string;
  created_at?: string;
  uploaded_at?: string;
};

function Evidence() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedEngagement, setSelectedEngagement] =
    useState("");

  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("All");

  const [loadingEngagements, setLoadingEngagements] = useState(true);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadEngagements();
  }, []);

  useEffect(() => {
    if (selectedEngagement) {
      loadEvidence(selectedEngagement);
    } else {
      setEvidence([]);
    }
  }, [selectedEngagement]);

  async function loadEngagements() {
    setLoadingEngagements(true);
    setMessage("");

    try {
      const response = await fetch(`${API_URL}/engagements`);

      if (!response.ok) {
        throw new Error("Unable to load engagements.");
      }

      const data = await response.json();
      const items: Engagement[] = data.engagements || [];

      setEngagements(items);

      if (items.length > 0) {
        setSelectedEngagement(items[0].engagement_id);
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load engagements.",
      );
    } finally {
      setLoadingEngagements(false);
    }
  }

  async function loadEvidence(engagementId: string) {
    setLoadingEvidence(true);
    setMessage("");

    try {
      const response = await fetch(
        `${API_URL}/evidence/${encodeURIComponent(engagementId)}`,
      );

      if (!response.ok) {
        throw new Error("Unable to load evidence.");
      }

      const data = await response.json();

      const items =
        Array.isArray(data)
          ? data
          : data.evidence || [];

      setEvidence(items);
    } catch (error) {
      setEvidence([]);
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load evidence.",
      );
    } finally {
      setLoadingEvidence(false);
    }
  }

  const selected = engagements.find(
    (item) => item.engagement_id === selectedEngagement,
  );

  const evidenceTypes = useMemo(() => {
    const types = evidence
      .map(
        (item) =>
          item.evidence_type ||
          item.type ||
          "Other",
      )
      .filter(Boolean);

    return ["All", ...Array.from(new Set(types))];
  }, [evidence]);

  const filteredEvidence = useMemo(() => {
    const query = search.trim().toLowerCase();

    return evidence.filter((item) => {
      const fileName =
        item.file_name ||
        item.filename ||
        "Untitled evidence";

      const type =
        item.evidence_type ||
        item.type ||
        "Other";

      const description =
        item.description || "";

      const matchesSearch =
        !query ||
        fileName.toLowerCase().includes(query) ||
        type.toLowerCase().includes(query) ||
        description.toLowerCase().includes(query);

      const matchesType =
        typeFilter === "All" ||
        type === typeFilter;

      return matchesSearch && matchesType;
    });
  }, [evidence, search, typeFilter]);

  const verifiedCount = evidence.filter(
    (item) =>
      (item.status || "").toLowerCase() ===
      "verified",
  ).length;

  const pendingCount = evidence.filter(
    (item) =>
      !item.status ||
      (item.status || "").toLowerCase() ===
        "pending",
  ).length;

  return (
    <main className="evidence-page">
      <div className="evidence-glow evidence-glow-one" />
      <div className="evidence-glow evidence-glow-two" />

      <div className="evidence-content">
        <header className="evidence-header">
          <div>
            <div className="evidence-breadcrumb">
              <Shield size={14} />
              <span>Workspace</span>
              <span>/</span>
              <span>Evidence</span>
            </div>

            <div className="evidence-title-row">
              <div>
                <h1>Evidence</h1>
                <p>
                  Collect, review, and manage evidence
                  supporting security assessments.
                </p>
              </div>

              <span className="evidence-status">
                <span />
                Evidence Workspace
              </span>
            </div>
          </div>

          <button
            className="evidence-refresh"
            onClick={() => {
              if (selectedEngagement) {
                loadEvidence(selectedEngagement);
              } else {
                loadEngagements();
              }
            }}
            disabled={
              loadingEvidence ||
              loadingEngagements
            }
          >
            {loadingEvidence ||
            loadingEngagements ? (
              <Loader2
                size={16}
                className="evidence-spin"
              />
            ) : (
              <RefreshCw size={16} />
            )}
            Refresh
          </button>
        </header>

        {message && (
          <div className="evidence-message">
            <XCircle size={17} />
            <span>{message}</span>
          </div>
        )}

        <section className="evidence-kpis">
          <KpiCard
            icon={<FolderOpen size={18} />}
            label="Total Evidence"
            value={evidence.length}
            description="For selected engagement"
          />

          <KpiCard
            icon={<CheckCircle2 size={18} />}
            label="Verified"
            value={verifiedCount}
            description="Reviewed evidence"
          />

          <KpiCard
            icon={<Clock3 size={18} />}
            label="Pending Review"
            value={pendingCount}
            description="Awaiting validation"
          />

          <KpiCard
            icon={<FileCheck2 size={18} />}
            label="Engagement"
            value={selectedEngagement || "—"}
            description={
              selected?.client_name ||
              "No engagement selected"
            }
            compact
          />
        </section>

        <section className="evidence-workspace">
          <aside className="engagement-panel">
            <div className="panel-kicker">
              ENGAGEMENTS
            </div>

            <div className="panel-heading">
              <div>
                <h2>Evidence Scope</h2>
                <p>
                  Select an engagement to view its
                  evidence.
                </p>
              </div>
            </div>

            <div className="engagement-list">
              {loadingEngagements ? (
                <div className="panel-loading">
                  <Loader2
                    size={20}
                    className="evidence-spin"
                  />
                  Loading engagements...
                </div>
              ) : engagements.length === 0 ? (
                <div className="panel-empty">
                  <FolderOpen size={22} />
                  <strong>No engagements</strong>
                  <span>
                    Create an engagement first.
                  </span>
                </div>
              ) : (
                engagements.map((engagement) => (
                  <button
                    key={engagement.engagement_id}
                    className={`engagement-item ${
                      selectedEngagement ===
                      engagement.engagement_id
                        ? "selected"
                        : ""
                    }`}
                    onClick={() =>
                      setSelectedEngagement(
                        engagement.engagement_id,
                      )
                    }
                  >
                    <div className="engagement-icon">
                      <Shield size={16} />
                    </div>

                    <div>
                      <strong>
                        {engagement.engagement_id}
                      </strong>
                      <span>
                        {engagement.client_name}
                      </span>
                      <small>
                        {engagement.technology}
                      </small>
                    </div>
                  </button>
                ))
              )}
            </div>
          </aside>

          <section className="evidence-panel">
            <div className="evidence-panel-heading">
              <div>
                <div className="panel-kicker">
                  EVIDENCE REGISTER
                </div>

                <h2>
                  {selected?.client_name ||
                    "Select an engagement"}
                </h2>

                {selected && (
                  <p>
                    {selected.engagement_id} ·{" "}
                    {selected.technology} · Reviewer:{" "}
                    {selected.reviewer}
                  </p>
                )}
              </div>

              <button
                className="upload-button"
                type="button"
                title="Evidence upload will be connected to the backend schema"
              >
                <UploadCloud size={16} />
                Add Evidence
              </button>
            </div>

            <div className="evidence-toolbar">
              <div className="evidence-search">
                <Search size={15} />
                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder="Search evidence..."
                />
              </div>

              <div className="evidence-filter">
                <Filter size={14} />

                <select
                  value={typeFilter}
                  onChange={(event) =>
                    setTypeFilter(event.target.value)
                  }
                >
                  {evidenceTypes.map((type) => (
                    <option
                      key={type}
                      value={type}
                    >
                      {type}
                    </option>
                  ))}
                </select>
              </div>

              <span className="evidence-count">
                {filteredEvidence.length} items
              </span>
            </div>

            <div className="evidence-table">
              <div className="evidence-table-header">
                <span>Evidence</span>
                <span>Type</span>
                <span>Status</span>
                <span>Uploaded By</span>
                <span>Date</span>
              </div>

              {loadingEvidence ? (
                <div className="evidence-loading">
                  <Loader2
                    size={22}
                    className="evidence-spin"
                  />
                  Loading evidence...
                </div>
              ) : filteredEvidence.length === 0 ? (
                <div className="evidence-empty">
                  <div className="empty-icon">
                    <FileText size={24} />
                  </div>

                  <strong>
                    No evidence available
                  </strong>

                  <span>
                    Evidence associated with this
                    engagement will appear here.
                  </span>
                </div>
              ) : (
                filteredEvidence.map(
                  (item, index) => {
                    const fileName =
                      item.file_name ||
                      item.filename ||
                      `Evidence ${index + 1}`;

                    const type =
                      item.evidence_type ||
                      item.type ||
                      "Other";

                    const status =
                      item.status || "Pending";

                    const date =
                      item.created_at ||
                      item.uploaded_at ||
                      "—";

                    return (
                      <div
                        className="evidence-row"
                        key={
                          item.evidence_id ||
                          `${fileName}-${index}`
                        }
                      >
                        <div className="evidence-file">
                          <div className="file-icon">
                            <FileText size={17} />
                          </div>

                          <div>
                            <strong>
                              {fileName}
                            </strong>

                            <span>
                              {item.description ||
                                "Assessment evidence"}
                            </span>
                          </div>
                        </div>

                        <span className="type-badge">
                          {type}
                        </span>

                        <span
                          className={`status-badge ${status
                            .toLowerCase()
                            .replace(
                              /\s+/g,
                              "-",
                            )}`}
                        >
                          {status}
                        </span>

                        <span className="uploaded-by">
                          {item.uploaded_by ||
                            "—"}
                        </span>

                        <span className="evidence-date">
                          {date}
                        </span>
                      </div>
                    );
                  },
                )
              )}
            </div>
          </section>
        </section>

        <footer className="evidence-footer">
          <div>
            <Shield size={14} />
            <span>Sentinel GRC</span>
            <span>v1.0</span>
          </div>

          <span>
            Security Configuration &amp; Compliance
            Platform
          </span>
        </footer>
      </div>
    </main>
  );
}

function KpiCard({
  icon,
  label,
  value,
  description,
  compact = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  description: string;
  compact?: boolean;
}) {
  return (
    <div className="evidence-kpi">
      <div className="kpi-icon">{icon}</div>

      <div className="kpi-body">
        <span>{label}</span>

        <strong className={compact ? "compact" : ""}>
          {value}
        </strong>

        <small>{description}</small>
      </div>
    </div>
  );
}

export default Evidence;