import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  FileCheck2,
  FileText,
  Printer,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Target,
} from "lucide-react";
import "./Reports.css";

const API_URL = import.meta.env.VITE_API_URL;

type Engagement = {
  engagement_id: string;
  client_name: string;
  technology: string;
  reviewer: string;
};

type Assessment = {
  results?: AssessmentResult[];
};

type AssessmentResult = {
  item_id: string;
  status: string;
  notes?: string;
};

type Finding = {
  finding_id: string;
  title: string;
  description?: string;
  severity: string;
  status: string;
  recommendation?: string;
};

type Risk = {
  risk_id: string;
  title: string;
  likelihood: number;
  impact: number;
  risk_score: number;
  risk_level: string;
  treatment?: string;
  owner?: string;
  status: string;
  finding_id?: string;
};

type Evidence = {
  item_id?: string;
  evidence?: string;
};

type ApiCollection<T> = T[] | Record<string, unknown>;

function extractCollection<T>(
  data: ApiCollection<T>,
  key: string
): T[] {
  if (Array.isArray(data)) {
    return data;
  }

  const value = data[key];

  return Array.isArray(value) ? (value as T[]) : [];
}

function getRiskClass(level: string) {
  switch (level.toLowerCase()) {
    case "critical":
      return "report-badge report-badge-critical";
    case "high":
      return "report-badge report-badge-high";
    case "medium":
      return "report-badge report-badge-medium";
    case "low":
      return "report-badge report-badge-low";
    default:
      return "report-badge";
  }
}

function getStatusClass(status: string) {
  const normalized = status.toLowerCase();

  if (
    normalized.includes("resolved") ||
    normalized.includes("closed") ||
    normalized.includes("approved")
  ) {
    return "report-badge report-badge-success";
  }

  if (
    normalized.includes("open") ||
    normalized.includes("pending")
  ) {
    return "report-badge report-badge-warning";
  }

  return "report-badge";
}

function calculateCompliance(results: AssessmentResult[]) {
  const assessed = results.filter((result) =>
    [
      "compliant",
      "non-compliant",
      "compensating control",
    ].includes(result.status.toLowerCase())
  );

  if (!assessed.length) {
    return 0;
  }

  const compliant = assessed.filter((result) =>
    ["compliant", "compensating control"].includes(
      result.status.toLowerCase()
    )
  ).length;

  return Math.round((compliant / assessed.length) * 100);
}

function Reports() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [selectedId, setSelectedId] = useState("");

  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);

  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadEngagements() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_URL}/engagements`);

      if (!response.ok) {
        throw new Error("Unable to load engagements.");
      }

      const data = await response.json();

      const list = extractCollection<Engagement>(
        data,
        "engagements"
      );

      setEngagements(list);

      if (!selectedId && list.length > 0) {
        setSelectedId(list[0].engagement_id);
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

  async function loadReportData(engagementId: string) {
    if (!engagementId) return;

    try {
      setReportLoading(true);
      setError("");

      const [
        assessmentsResponse,
        findingsResponse,
        risksResponse,
        evidenceResponse,
      ] = await Promise.all([
        fetch(`${API_URL}/assessments/${engagementId}`),
        fetch(`${API_URL}/findings/${engagementId}`),
        fetch(`${API_URL}/risks/${engagementId}`),
        fetch(`${API_URL}/evidence/${engagementId}`),
      ]);

      const [
        assessmentsData,
        findingsData,
        risksData,
        evidenceData,
      ] = await Promise.all([
        assessmentsResponse.ok
          ? assessmentsResponse.json()
          : [],
        findingsResponse.ok
          ? findingsResponse.json()
          : [],
        risksResponse.ok
          ? risksResponse.json()
          : [],
        evidenceResponse.ok
          ? evidenceResponse.json()
          : [],
      ]);

      setAssessments(
        extractCollection<Assessment>(
          assessmentsData,
          "assessments"
        )
      );

      setFindings(
        extractCollection<Finding>(
          findingsData,
          "findings"
        )
      );

      setRisks(
        extractCollection<Risk>(
          risksData,
          "risks"
        )
      );

      setEvidence(
        extractCollection<Evidence>(
          evidenceData,
          "evidence"
        )
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load report data."
      );
    } finally {
      setReportLoading(false);
    }
  }

  useEffect(() => {
    loadEngagements();
  }, []);

  useEffect(() => {
    if (selectedId) {
      loadReportData(selectedId);
    }
  }, [selectedId]);

  const selectedEngagement = useMemo(
    () =>
      engagements.find(
        (engagement) =>
          engagement.engagement_id === selectedId
      ),
    [engagements, selectedId]
  );

  const latestAssessment = assessments.length
    ? assessments[assessments.length - 1]
    : undefined;

  const assessmentResults =
    latestAssessment?.results ?? [];

  const compliance = calculateCompliance(
    assessmentResults
  );

  const compliantCount = assessmentResults.filter(
    (result) =>
      ["compliant", "compensating control"].includes(
        result.status.toLowerCase()
      )
  ).length;

  const nonCompliantCount = assessmentResults.filter(
    (result) =>
      result.status.toLowerCase() === "non-compliant"
  ).length;

  const criticalFindings = findings.filter(
    (finding) =>
      finding.severity.toLowerCase() === "critical"
  ).length;

  const highFindings = findings.filter(
    (finding) =>
      finding.severity.toLowerCase() === "high"
  ).length;

  const criticalRisks = risks.filter(
    (risk) =>
      risk.risk_level.toLowerCase() === "critical"
  ).length;

  const highRisks = risks.filter(
    (risk) =>
      risk.risk_level.toLowerCase() === "high"
  ).length;

  const aggregateRiskScore = risks.reduce(
    (total, risk) => total + Number(risk.risk_score || 0),
    0
  );

  const executiveSummary = selectedEngagement
    ? `The ${selectedEngagement.technology} security assessment for ${selectedEngagement.client_name} currently has an overall compliance level of ${compliance}%.`
    : "";

  function handleGenerateReport() {
    window.print();
  }

  async function handleRefresh() {
    await loadEngagements();

    if (selectedId) {
      await loadReportData(selectedId);
    }
  }

  return (
    <main className="reports-page">
      <div className="reports-container">

        {/* Header */}
        <header className="reports-header">
          <div>
            <div className="reports-eyebrow">
              <span className="reports-eyebrow-dot" />
              SENTINEL GRC / REPORTING
            </div>

            <h1>Security &amp; Compliance Reports</h1>

            <p>
              Executive security posture and compliance
              reporting for assessment engagements.
            </p>
          </div>

          <div className="reports-header-actions">
            <button
              className="reports-icon-button"
              onClick={handleRefresh}
              title="Refresh report"
              disabled={reportLoading}
            >
              <RefreshCw
                size={17}
                className={
                  reportLoading
                    ? "reports-spin"
                    : ""
                }
              />
            </button>

            <button
              className="reports-primary-button"
              onClick={handleGenerateReport}
              disabled={!selectedEngagement}
            >
              <Printer size={17} />
              Generate Report
            </button>
          </div>
        </header>

        {/* Error */}
        {error && (
          <div className="reports-error">
            <AlertTriangle size={18} />
            <span>{error}</span>
          </div>
        )}

        {/* Engagement selector */}
        <section className="report-selector-card">
          <div className="report-selector-info">
            <div className="report-section-icon">
              <ClipboardList size={18} />
            </div>

            <div>
              <span className="report-label">
                Assessment Engagement
              </span>

              <strong>
                {selectedEngagement
                  ? selectedEngagement.client_name
                  : "No engagement selected"}
              </strong>
            </div>
          </div>

          <div className="report-selector-right">
            <select
              value={selectedId}
              onChange={(event) =>
                setSelectedId(event.target.value)
              }
              disabled={
                loading || engagements.length === 0
              }
            >
              {engagements.length === 0 ? (
                <option value="">
                  No engagements available
                </option>
              ) : (
                engagements.map((engagement) => (
                  <option
                    key={engagement.engagement_id}
                    value={engagement.engagement_id}
                  >
                    {engagement.client_name} —{" "}
                    {engagement.engagement_id}
                  </option>
                ))
              )}
            </select>
          </div>
        </section>

        {loading || reportLoading ? (
          <div className="reports-loading">
            <RefreshCw
              size={22}
              className="reports-spin"
            />
            <span>Loading security report...</span>
          </div>
        ) : selectedEngagement ? (
          <>
            {/* Report identity */}
            <section className="report-identity">
              <div className="report-identity-main">
                <div className="report-document-icon">
                  <FileText size={24} />
                </div>

                <div>
                  <span className="report-document-label">
                    SECURITY POSTURE REPORT
                  </span>

                  <h2>
                    {selectedEngagement.client_name}
                  </h2>

                  <div className="report-meta">
                    <span>
                      {selectedEngagement.engagement_id}
                    </span>

                    <span className="report-meta-divider">
                      •
                    </span>

                    <span>
                      {selectedEngagement.technology}
                    </span>

                    <span className="report-meta-divider">
                      •
                    </span>

                    <span>
                      Reviewer:{" "}
                      {selectedEngagement.reviewer}
                    </span>
                  </div>
                </div>
              </div>

              <div className="report-status">
                <span className="report-status-dot" />
                Assessment Report
              </div>
            </section>

            {/* KPI row */}
            <section className="report-kpis">

              <div className="report-kpi-card report-kpi-primary">
                <div className="report-kpi-top">
                  <span>Compliance</span>
                  <ShieldCheck size={18} />
                </div>

                <strong>{compliance}%</strong>

                <small>
                  Overall compliance posture
                </small>
              </div>

              <div className="report-kpi-card">
                <div className="report-kpi-top">
                  <span>Controls Assessed</span>
                  <Target size={18} />
                </div>

                <strong>
                  {assessmentResults.length}
                </strong>

                <small>
                  {compliantCount} compliant
                </small>
              </div>

              <div className="report-kpi-card">
                <div className="report-kpi-top">
                  <span>Findings</span>
                  <ShieldAlert size={18} />
                </div>

                <strong>{findings.length}</strong>

                <small>
                  {criticalFindings} critical ·{" "}
                  {highFindings} high
                </small>
              </div>

              <div className="report-kpi-card">
                <div className="report-kpi-top">
                  <span>Risk Items</span>
                  <AlertTriangle size={18} />
                </div>

                <strong>{risks.length}</strong>

                <small>
                  {criticalRisks} critical ·{" "}
                  {highRisks} high
                </small>
              </div>

              <div className="report-kpi-card">
                <div className="report-kpi-top">
                  <span>Evidence</span>
                  <FileCheck2 size={18} />
                </div>

                <strong>{evidence.length}</strong>

                <small>Evidence records</small>
              </div>

            </section>

            {/* 01 + 02 */}
            <section className="report-grid report-grid-two">

              <article className="report-card">
                <div className="report-card-heading">
                  <span className="report-number">
                    01
                  </span>

                  <div>
                    <h3>Compliance Overview</h3>
                    <p>
                      Current control assessment status
                    </p>
                  </div>
                </div>

                <div className="compliance-content">
                  <div className="compliance-ring">
                    <div>
                      <strong>{compliance}%</strong>
                      <span>Compliant</span>
                    </div>
                  </div>

                  <div className="compliance-stats">
                    <div>
                      <span className="stat-dot stat-dot-success" />
                      <div>
                        <strong>
                          {compliantCount}
                        </strong>
                        <span>Compliant</span>
                      </div>
                    </div>

                    <div>
                      <span className="stat-dot stat-dot-danger" />
                      <div>
                        <strong>
                          {nonCompliantCount}
                        </strong>
                        <span>Non-Compliant</span>
                      </div>
                    </div>
                  </div>
                </div>
              </article>

              <article className="report-card">
                <div className="report-card-heading">
                  <span className="report-number">
                    02
                  </span>

                  <div>
                    <h3>Risk Exposure</h3>
                    <p>
                      Aggregate security risk profile
                    </p>
                  </div>
                </div>

                <div className="risk-score-block">
                  <span>Aggregate Risk Score</span>

                  <strong>
                    {aggregateRiskScore}
                  </strong>
                </div>

                <div className="risk-summary-row">
                  <div>
                    <span className="mini-risk-dot critical" />
                    <strong>{criticalRisks}</strong>
                    <span>Critical</span>
                  </div>

                  <div>
                    <span className="mini-risk-dot high" />
                    <strong>{highRisks}</strong>
                    <span>High</span>
                  </div>

                  <div>
                    <span className="mini-risk-dot medium" />
                    <strong>
                      {
                        risks.filter(
                          (risk) =>
                            risk.risk_level.toLowerCase() ===
                            "medium"
                        ).length
                      }
                    </strong>
                    <span>Medium</span>
                  </div>
                </div>
              </article>

            </section>

            {/* 03 Findings */}
            <section className="report-card">
              <div className="report-card-heading">
                <span className="report-number">
                  03
                </span>

                <div>
                  <h3>Finding Summary</h3>
                  <p>
                    Security findings identified during
                    the assessment
                  </p>
                </div>
              </div>

              {findings.length === 0 ? (
                <div className="report-empty">
                  <CheckCircle2 size={22} />
                  <div>
                    <strong>No findings recorded</strong>
                    <span>
                      No findings are currently associated
                      with this engagement.
                    </span>
                  </div>
                </div>
              ) : (
                <div className="finding-list">
                  {findings.map((finding) => (
                    <div
                      className="finding-row"
                      key={finding.finding_id}
                    >
                      <div className="finding-main">
                        <div className="finding-icon">
                          <ShieldAlert size={17} />
                        </div>

                        <div>
                          <strong>
                            {finding.title}
                          </strong>

                          <span>
                            {finding.finding_id}
                          </span>
                        </div>
                      </div>

                      <span
                        className={getRiskClass(
                          finding.severity
                        )}
                      >
                        {finding.severity}
                      </span>

                      <span
                        className={getStatusClass(
                          finding.status
                        )}
                      >
                        {finding.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* 04 Risk register */}
            <section className="report-card">
              <div className="report-card-heading">
                <span className="report-number">
                  04
                </span>

                <div>
                  <h3>Risk Register</h3>
                  <p>
                    Recorded risks and calculated exposure
                  </p>
                </div>
              </div>

              {risks.length === 0 ? (
                <div className="report-empty">
                  <CheckCircle2 size={22} />
                  <div>
                    <strong>No risks recorded</strong>
                    <span>
                      No risk items are currently associated
                      with this engagement.
                    </span>
                  </div>
                </div>
              ) : (
                <div className="risk-table">

                  <div className="risk-table-header">
                    <span>Risk</span>
                    <span>Risk ID</span>
                    <span>Level</span>
                    <span>Score</span>
                    <span>Status</span>
                  </div>

                  {risks.map((risk) => (
                    <div
                      className="risk-table-row"
                      key={risk.risk_id}
                    >
                      <div className="risk-title-cell">
                        <strong>{risk.title}</strong>

                        <small>
                          {risk.owner
                            ? `Owner: ${risk.owner}`
                            : "Security risk"}
                        </small>
                      </div>

                      <span className="risk-id">
                        {risk.risk_id}
                      </span>

                      <span
                        className={getRiskClass(
                          risk.risk_level
                        )}
                      >
                        {risk.risk_level}
                      </span>

                      <strong className="risk-score">
                        {risk.risk_score}
                      </strong>

                      <span
                        className={getStatusClass(
                          risk.status
                        )}
                      >
                        {risk.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* 05 Executive summary */}
            <section className="report-executive">
              <div className="report-executive-icon">
                <BarChart3 size={22} />
              </div>

              <div className="report-executive-content">
                <div className="report-card-heading">
                  <span className="report-number">
                    05
                  </span>

                  <div>
                    <h3>Executive Summary</h3>
                    <p>
                      High-level assessment interpretation
                    </p>
                  </div>
                </div>

                <div className="executive-text">
                  <p>{executiveSummary}</p>

                  <p>
                    A total of{" "}
                    <strong>{findings.length}</strong>{" "}
                    findings and{" "}
                    <strong>{risks.length}</strong>{" "}
                    risk items are recorded for this
                    engagement.
                  </p>

                  <p>
                    The report contains{" "}
                    <strong>{evidence.length}</strong>{" "}
                    evidence records associated with the
                    assessment.
                  </p>
                </div>
              </div>
            </section>

            {/* Footer */}
            <footer className="report-footer">
              <div>
                <span className="footer-dot" />
                Sentinel GRC
              </div>

              <span>
                Security Configuration &amp; Compliance
                Platform
              </span>
            </footer>
          </>
        ) : (
          <div className="reports-empty-state">
            <FileText size={38} />
            <h2>Select an assessment engagement</h2>
            <p>
              Choose an engagement above to generate its
              security posture report.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}

export default Reports;