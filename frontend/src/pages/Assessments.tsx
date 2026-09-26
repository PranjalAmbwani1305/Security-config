import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Clock3,
  FileText,
  Loader2,
  MessageSquareText,
  Save,
  Search,
  Shield,
  Sparkles,
  Target,
  X,
  XCircle,
} from "lucide-react";

import "./Assessments.css";

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

type ChecklistResponse = {
  technology: string;
  source?: string;
  total_controls: number;
  checklist: ChecklistItem[];
};

type ControlStatus =
  | "Not Reviewed"
  | "Compliant"
  | "Non-Compliant"
  | "Compensating Control"
  | "Not Applicable";

type AssessmentResult = {
  item_id: string;
  status: ControlStatus;
  notes: string;
};

type AssessmentResponse = {
  message: string;
  engagement_id: string;
  compliance_percentage: number;
  total_controls: number;
  compliant_controls: number;
  non_compliant_controls: number;
  assessment: {
    engagement_id: string;
    results: AssessmentResult[];
  };
};

const API_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

const STATUS_OPTIONS: ControlStatus[] = [
  "Not Reviewed",
  "Compliant",
  "Non-Compliant",
  "Compensating Control",
  "Not Applicable",
];

function Assessments() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);

  const [selectedEngagement, setSelectedEngagement] =
    useState("");

  const [checklist, setChecklist] =
    useState<ChecklistResponse | null>(null);

  const [results, setResults] = useState<
    Record<string, AssessmentResult>
  >({});

  const [search, setSearch] = useState("");

  const [categoryFilter, setCategoryFilter] =
    useState("All");

  const [loadingEngagements, setLoadingEngagements] =
    useState(true);

  const [loadingChecklist, setLoadingChecklist] =
    useState(false);

  const [submitting, setSubmitting] =
    useState(false);

  const [message, setMessage] = useState("");

  const [messageType, setMessageType] = useState<
    "success" | "error" | "info"
  >("info");

  const [submittedResult, setSubmittedResult] =
    useState<AssessmentResponse | null>(null);

  const [showSummary, setShowSummary] =
    useState(false);

  const [activeNotes, setActiveNotes] =
    useState<string | null>(null);

  /* ==========================================================
     LOAD ENGAGEMENTS
  ========================================================== */

  useEffect(() => {
    loadEngagements();
  }, []);

  const loadEngagements = async () => {
    setLoadingEngagements(true);

    try {
      const response = await fetch(
        `${API_URL}/engagements`,
      );

      if (!response.ok) {
        throw new Error(
          "Unable to load engagements.",
        );
      }

      const data = await response.json();

      const items: Engagement[] =
        data.engagements || data || [];

      setEngagements(items);

      if (items.length > 0) {
        setSelectedEngagement(
          items[0].engagement_id,
        );
      }
    } catch (error) {
      setMessageType("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load engagements.",
      );
    } finally {
      setLoadingEngagements(false);
    }
  };

  /* ==========================================================
     SELECTED ENGAGEMENT
  ========================================================== */

  const currentEngagement = useMemo(
    () =>
      engagements.find(
        (engagement) =>
          engagement.engagement_id ===
          selectedEngagement,
      ),
    [engagements, selectedEngagement],
  );

  /* ==========================================================
     LOAD CHECKLIST
  ========================================================== */

  useEffect(() => {
    if (!currentEngagement) {
      return;
    }

    loadChecklist(
      currentEngagement.technology,
    );
  }, [currentEngagement?.engagement_id]);

  const loadChecklist = async (
    technology: string,
  ) => {
    setLoadingChecklist(true);
    setChecklist(null);
    setSubmittedResult(null);
    setShowSummary(false);

    try {
      const response = await fetch(
        `${API_URL}/checklists/${encodeURIComponent(
          technology,
        )}`,
      );

      if (!response.ok) {
        throw new Error(
          `No checklist found for ${technology}.`,
        );
      }

      const data: ChecklistResponse =
        await response.json();

      setChecklist(data);

      const initialResults: Record<
        string,
        AssessmentResult
      > = {};

      data.checklist.forEach((item) => {
        initialResults[item.item_id] = {
          item_id: item.item_id,
          status: "Not Reviewed",
          notes: "",
        };
      });

      setResults(initialResults);
    } catch (error) {
      setMessageType("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load checklist.",
      );
    } finally {
      setLoadingChecklist(false);
    }
  };

  /* ==========================================================
     CATEGORIES
  ========================================================== */

  const categories = useMemo(() => {
    if (!checklist) {
      return ["All"];
    }

    return [
      "All",
      ...Array.from(
        new Set(
          checklist.checklist.map(
            (item) => item.category,
          ),
        ),
      ),
    ];
  }, [checklist]);

  /* ==========================================================
     FILTER CONTROLS
  ========================================================== */

  const visibleControls = useMemo(() => {
    if (!checklist) {
      return [];
    }

    return checklist.checklist.filter((item) => {
      const query = search.toLowerCase();

      const matchesSearch =
        !query ||
        item.item_id
          .toLowerCase()
          .includes(query) ||
        item.control
          .toLowerCase()
          .includes(query) ||
        item.audit_step
          .toLowerCase()
          .includes(query);

      const matchesCategory =
        categoryFilter === "All" ||
        item.category === categoryFilter;

      return (
        matchesSearch &&
        matchesCategory
      );
    });
  }, [
    checklist,
    search,
    categoryFilter,
  ]);

  /* ==========================================================
     UPDATE STATUS
  ========================================================== */

  const updateStatus = (
    itemId: string,
    status: ControlStatus,
  ) => {
    setResults((current) => ({
      ...current,
      [itemId]: {
        ...current[itemId],
        item_id: itemId,
        status,
      },
    }));

    setSubmittedResult(null);
  };

  /* ==========================================================
     UPDATE NOTES
  ========================================================== */

  const updateNotes = (
    itemId: string,
    notes: string,
  ) => {
    setResults((current) => ({
      ...current,
      [itemId]: {
        ...current[itemId],
        item_id: itemId,
        notes,
      },
    }));

    setSubmittedResult(null);
  };

  /* ==========================================================
     SUMMARY
  ========================================================== */

  const summary = useMemo(() => {
    const values = Object.values(results);

    const total = values.length;

    const compliant = values.filter(
      (item) =>
        item.status === "Compliant" ||
        item.status ===
          "Compensating Control",
    ).length;

    const nonCompliant = values.filter(
      (item) =>
        item.status === "Non-Compliant",
    ).length;

    const reviewed = values.filter(
      (item) =>
        item.status !== "Not Reviewed",
    ).length;

    const notApplicable = values.filter(
      (item) =>
        item.status === "Not Applicable",
    ).length;

    const compliance =
      reviewed > 0
        ? (compliant /
            (reviewed - notApplicable || 1)) *
          100
        : 0;

    return {
      total,
      reviewed,
      compliant,
      nonCompliant,
      notApplicable,
      compliance: Math.min(
        100,
        Math.round(compliance),
      ),
    };
  }, [results]);

  /* ==========================================================
     SUBMIT ASSESSMENT
  ========================================================== */

  const submitAssessment = async () => {
    if (!selectedEngagement) {
      setMessageType("error");
      setMessage(
        "Select an engagement before submitting.",
      );
      return;
    }

    if (!checklist) {
      setMessageType("error");
      setMessage(
        "No checklist is loaded.",
      );
      return;
    }

    if (summary.reviewed === 0) {
      setMessageType("error");
      setMessage(
        "Review at least one control before submitting.",
      );
      return;
    }

    setSubmitting(true);
    setMessage("");

    try {
      const payload = {
        engagement_id:
          selectedEngagement,
        results: checklist.checklist.map(
          (item) => ({
            item_id: item.item_id,
            status:
              results[item.item_id]?.status ||
              "Not Reviewed",
            notes:
              results[item.item_id]?.notes ||
              "",
          }),
        ),
      };

      const response = await fetch(
        `${API_URL}/assessments`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        throw new Error(
          "Assessment submission failed.",
        );
      }

      const data: AssessmentResponse =
        await response.json();

      setSubmittedResult(data);
      setShowSummary(true);
      setMessageType("success");
      setMessage(
        "Assessment submitted successfully. Compliance has been calculated.",
      );
    } catch (error) {
      setMessageType("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Assessment submission failed.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  /* ==========================================================
     STATUS CLASS
  ========================================================== */

  const getStatusClass = (
    status: ControlStatus,
  ) => {
    switch (status) {
      case "Compliant":
        return "status-compliant";

      case "Non-Compliant":
        return "status-non-compliant";

      case "Compensating Control":
        return "status-compensating";

      case "Not Applicable":
        return "status-na";

      default:
        return "status-not-reviewed";
    }
  };

  return (
    <div className="assessments-page">
      <div className="assessment-glow glow-one" />
      <div className="assessment-glow glow-two" />

      <main className="assessments-content">

        {/* ====================================================
            HEADER
        ==================================================== */}

        <header className="assessment-header">

          <div>
            <div className="assessment-breadcrumb">
              <Shield size={15} />

              <span>
                Workspace
              </span>

              <ChevronDown size={13} />

              <span>
                Assessments
              </span>
            </div>

            <div className="assessment-title-row">
              <h1>
                Security Assessment
              </h1>

              <span className="live-badge">
                <span />
                Assessment Workspace
              </span>
            </div>

            <p>
              Evaluate security controls, record evidence,
              and determine the compliance posture of an
              engagement.
            </p>
          </div>

          <div className="header-actions">

            <button
              className="refresh-button"
              onClick={loadEngagements}
            >
              <Save size={15} />
              Save Progress
            </button>

            <button
              className="submit-button"
              onClick={submitAssessment}
              disabled={
                submitting ||
                !checklist
              }
            >
              {submitting ? (
                <Loader2
                  size={16}
                  className="spin"
                />
              ) : (
                <ClipboardCheck size={16} />
              )}

              Submit Assessment
            </button>

          </div>
        </header>

        {/* ====================================================
            MESSAGE
        ==================================================== */}

        {message && (
          <div
            className={`assessment-message ${messageType}`}
          >
            {messageType === "success" ? (
              <CheckCircle2 size={17} />
            ) : messageType === "error" ? (
              <AlertCircle size={17} />
            ) : (
              <Sparkles size={17} />
            )}

            <span>
              {message}
            </span>

            <button
              onClick={() =>
                setMessage("")
              }
            >
              <X size={15} />
            </button>
          </div>
        )}

        {/* ====================================================
            ENGAGEMENT BAR
        ==================================================== */}

        <section className="engagement-selector panel">

          <div className="selector-icon">
            <Target size={19} />
          </div>

          <div className="selector-main">

            <span className="selector-label">
              ACTIVE ENGAGEMENT
            </span>

            <div className="selector-row">

              {loadingEngagements ? (
                <div className="loading-inline">
                  <Loader2
                    size={15}
                    className="spin"
                  />
                  Loading engagements...
                </div>
              ) : (
                <select
                  value={selectedEngagement}
                  onChange={(event) =>
                    setSelectedEngagement(
                      event.target.value,
                    )
                  }
                >
                  {engagements.map(
                    (engagement) => (
                      <option
                        key={
                          engagement.engagement_id
                        }
                        value={
                          engagement.engagement_id
                        }
                      >
                        {engagement.engagement_id} —{" "}
                        {engagement.client_name}
                      </option>
                    ),
                  )}
                </select>
              )}

            </div>

          </div>

          {currentEngagement && (
            <div className="engagement-meta">

              <div>
                <span>CLIENT</span>
                <strong>
                  {currentEngagement.client_name}
                </strong>
              </div>

              <div>
                <span>TECHNOLOGY</span>
                <strong>
                  {currentEngagement.technology}
                </strong>
              </div>

              <div>
                <span>REVIEWER</span>
                <strong>
                  {currentEngagement.reviewer}
                </strong>
              </div>

            </div>
          )}

        </section>

        {/* ====================================================
            KPI STRIP
        ==================================================== */}

        <section className="assessment-kpis">

          <div className="assessment-kpi">
            <div className="kpi-icon blue">
              <ClipboardCheck size={18} />
            </div>

            <div>
              <span>Total Controls</span>
              <strong>
                {summary.total}
              </strong>
            </div>
          </div>

          <div className="assessment-kpi">
            <div className="kpi-icon green">
              <CheckCircle2 size={18} />
            </div>

            <div>
              <span>Compliant</span>
              <strong>
                {summary.compliant}
              </strong>
            </div>
          </div>

          <div className="assessment-kpi">
            <div className="kpi-icon red">
              <XCircle size={18} />
            </div>

            <div>
              <span>Non-Compliant</span>
              <strong>
                {summary.nonCompliant}
              </strong>
            </div>
          </div>

          <div className="assessment-kpi">
            <div className="kpi-icon violet">
              <Clock3 size={18} />
            </div>

            <div>
              <span>Reviewed</span>
              <strong>
                {summary.reviewed}/{summary.total}
              </strong>
            </div>
          </div>

          <div className="assessment-kpi compliance-kpi">
            <div>
              <span>Current Compliance</span>
              <strong>
                {summary.compliance}%
              </strong>
            </div>

            <div className="mini-progress">
              <span
                style={{
                  width: `${summary.compliance}%`,
                }}
              />
            </div>
          </div>

        </section>

        {/* ====================================================
            MAIN WORKSPACE
        ==================================================== */}

        <section className="assessment-layout">

          {/* LEFT SIDE */}

          <aside className="assessment-sidebar panel">

            <div className="sidebar-heading">
              <div>
                <span className="panel-kicker">
                  ASSESSMENT
                </span>

                <h2>
                  Control Coverage
                </h2>
              </div>

              <Target size={18} />
            </div>

            <div className="coverage-ring">
              <div className="coverage-ring-inner">
                <strong>
                  {summary.compliance}%
                </strong>

                <span>
                  Compliance
                </span>
              </div>
            </div>

            <div className="coverage-stats">

              <div>
                <span>
                  <i className="dot green" />
                  Compliant
                </span>

                <strong>
                  {summary.compliant}
                </strong>
              </div>

              <div>
                <span>
                  <i className="dot red" />
                  Non-Compliant
                </span>

                <strong>
                  {summary.nonCompliant}
                </strong>
              </div>

              <div>
                <span>
                  <i className="dot violet" />
                  Pending
                </span>

                <strong>
                  {summary.total -
                    summary.reviewed}
                </strong>
              </div>

            </div>

            <div className="sidebar-divider" />

            <div className="assessment-progress">

              <div>
                <span>
                  Assessment progress
                </span>

                <strong>
                  {summary.reviewed}/
                  {summary.total}
                </strong>
              </div>

              <div className="progress-track">
                <span
                  style={{
                    width:
                      summary.total > 0
                        ? `${
                            (summary.reviewed /
                              summary.total) *
                            100
                          }%`
                        : "0%",
                  }}
                />
              </div>

            </div>

            <div className="assessment-help">

              <MessageSquareText size={16} />

              <div>
                <strong>
                  Reviewer guidance
                </strong>

                <span>
                  Mark controls based on observed
                  configuration and supporting evidence.
                </span>
              </div>

            </div>

          </aside>

          {/* RIGHT SIDE */}

          <section className="controls-workspace panel">

            <div className="workspace-heading">

              <div>
                <span className="panel-kicker">
                  CONTROL ASSESSMENT
                </span>

                <h2>
                  {currentEngagement
                    ? `${currentEngagement.technology} Security Controls`
                    : "Security Controls"}
                </h2>

                <p>
                  Review each control and record its
                  current implementation status.
                </p>
              </div>

              <div className="workspace-status">
                {checklist?.source ===
                "AI-Generated" ? (
                  <span className="ai-source">
                    <Sparkles size={12} />
                    AI Generated
                  </span>
                ) : (
                  <span className="benchmark-source">
                    <Shield size={12} />
                    Benchmark Checklist
                  </span>
                )}
              </div>

            </div>

            {/* FILTER */}

            <div className="assessment-toolbar">

              <div className="assessment-search">
                <Search size={15} />

                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(
                      event.target.value,
                    )
                  }
                  placeholder="Search controls..."
                />
              </div>

              <div className="assessment-filter">

                <select
                  value={categoryFilter}
                  onChange={(event) =>
                    setCategoryFilter(
                      event.target.value,
                    )
                  }
                >
                  {categories.map(
                    (category) => (
                      <option
                        key={category}
                        value={category}
                      >
                        {category}
                      </option>
                    ),
                  )}
                </select>

                <ChevronDown size={14} />

              </div>

              <span className="results-count">
                {visibleControls.length} controls
              </span>

            </div>

            {/* CONTROLS */}

            {loadingChecklist ? (
              <div className="assessment-loading">

                <Loader2
                  size={28}
                  className="spin"
                />

                <strong>
                  Loading security controls...
                </strong>

                <span>
                  Preparing the assessment workspace.
                </span>

              </div>
            ) : visibleControls.length === 0 ? (
              <div className="assessment-empty">

                <ClipboardCheck size={28} />

                <strong>
                  No controls available
                </strong>

                <span>
                  Select an engagement with an available
                  checklist.
                </span>

              </div>
            ) : (
              <div className="assessment-controls">

                {visibleControls.map(
                  (item, index) => {
                    const result =
                      results[item.item_id];

                    return (
                      <article
                        className={`assessment-control ${
                          getStatusClass(
                            result?.status ||
                              "Not Reviewed",
                          )
                        }`}
                        key={item.item_id}
                      >

                        <div className="control-index">
                          {String(
                            index + 1,
                          ).padStart(2, "0")}
                        </div>

                        <div className="assessment-control-main">

                          <div className="assessment-control-top">

                            <span className="assessment-id">
                              {item.item_id}
                            </span>

                            <span className="assessment-category">
                              {item.category}
                            </span>

                            <span className="assessment-reference">
                              {item.reference}
                            </span>

                          </div>

                          <h3>
                            {item.control}
                          </h3>

                          <p>
                            {item.audit_step}
                          </p>

                          <div className="evidence-row">

                            <FileText size={13} />

                            <input
                              value={
                                result?.notes ||
                                ""
                              }
                              onChange={(
                                event,
                              ) =>
                                updateNotes(
                                  item.item_id,
                                  event.target
                                    .value,
                                )
                              }
                              placeholder="Add evidence, observation, or reviewer notes..."
                            />

                            {result?.notes && (
                              <span className="saved-note">
                                <Check size={12} />
                              </span>
                            )}

                          </div>

                        </div>

                        <div className="control-status-area">

                          <label>
                            Status
                          </label>

                          <select
                            className={getStatusClass(
                              result?.status ||
                                "Not Reviewed",
                            )}
                            value={
                              result?.status ||
                              "Not Reviewed"
                            }
                            onChange={(
                              event,
                            ) =>
                              updateStatus(
                                item.item_id,
                                event.target
                                  .value as ControlStatus,
                              )
                            }
                          >
                            {STATUS_OPTIONS.map(
                              (status) => (
                                <option
                                  key={status}
                                  value={status}
                                >
                                  {status}
                                </option>
                              ),
                            )}
                          </select>

                          <button
                            className="notes-button"
                            onClick={() =>
                              setActiveNotes(
                                activeNotes ===
                                  item.item_id
                                  ? null
                                  : item.item_id,
                              )
                            }
                          >
                            <MessageSquareText
                              size={13}
                            />

                            {result?.notes
                              ? "Edit note"
                              : "Add note"}
                          </button>

                        </div>

                        {activeNotes ===
                          item.item_id && (
                          <div className="expanded-notes">

                            <div>
                              <MessageSquareText
                                size={14}
                              />

                              <span>
                                Reviewer Notes
                              </span>
                            </div>

                            <textarea
                              value={
                                result?.notes ||
                                ""
                              }
                              onChange={(
                                event,
                              ) =>
                                updateNotes(
                                  item.item_id,
                                  event.target
                                    .value,
                                )
                              }
                              placeholder="Document evidence, configuration details, exceptions, or remediation observations..."
                            />

                            <button
                              onClick={() =>
                                setActiveNotes(
                                  null,
                                )
                              }
                            >
                              Done
                            </button>

                          </div>
                        )}

                      </article>
                    );
                  },
                )}

              </div>
            )}

          </section>

        </section>

        {/* ====================================================
            SUBMISSION RESULT
        ==================================================== */}

        {showSummary &&
          submittedResult && (
            <section className="assessment-result panel">

              <div className="result-icon">
                <CheckCircle2 size={24} />
              </div>

              <div className="result-main">

                <span className="panel-kicker">
                  ASSESSMENT COMPLETE
                </span>

                <h2>
                  Assessment submitted successfully
                </h2>

                <p>
                  The assessment result has been
                  recorded for engagement{" "}
                  <strong>
                    {
                      submittedResult.engagement_id
                    }
                  </strong>
                  .
                </p>

              </div>

              <div className="result-metrics">

                <div>
                  <span>
                    Compliance
                  </span>

                  <strong>
                    {
                      submittedResult.compliance_percentage
                    }
                    %
                  </strong>
                </div>

                <div>
                  <span>
                    Compliant
                  </span>

                  <strong>
                    {
                      submittedResult.compliant_controls
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Non-Compliant
                  </span>

                  <strong className="red-text">
                    {
                      submittedResult.non_compliant_controls
                    }
                  </strong>
                </div>

              </div>

            </section>
          )}

        {/* ====================================================
            FOOTER
        ==================================================== */}

        <footer className="assessment-footer">

          <div>
            <Shield size={14} />

            <span>
              Sentinel GRC
            </span>

            <span>
              v1.0
            </span>
          </div>

          <span>
            Security Configuration &amp; Compliance Platform
          </span>

        </footer>

      </main>
    </div>
  );
}

export default Assessments;