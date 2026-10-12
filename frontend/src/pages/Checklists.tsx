import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Edit3,
  FileCheck2,
  Filter,
  Layers3,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  WandSparkles,
  X,
  XCircle,
} from "lucide-react";

import "./Checklists.css";
import { apiFetch } from "../lib/api";

type ChecklistItem = {
  item_id: string;
  category: string;
  control: string;
  reference: string;
  audit_step: string;
  reference_verified?: boolean;
};

type ChecklistResponse = {
  technology: string;
  source?: string;
  approved?: boolean;
  version_no?: number | null;
  total_controls: number;
  checklist: ChecklistItem[];
};

type ReviewStatus = "Draft" | "Approved" | "Rejected";

type TechOption = {
  slug: string;
  name: string;
  category: string;
  basis: string;
  controls: number;
  origin: string;
  approved_version: number | null;
};

type VersionDetail = {
  id: string;
  technology: string;
  version_no: number;
  status: "draft" | "pending_review" | "approved" | "rejected" | "superseded";
  source: string;
  review_comment: string;
  total_controls: number;
  checklist: ChecklistItem[];
};

function Checklists() {
  const [selectedTechnology, setSelectedTechnology] = useState("linux-server");
  const [technologies, setTechnologies] = useState<TechOption[]>([]);
  const [version, setVersion] = useState<VersionDetail | null>(null);
  const [newControl, setNewControl] = useState({
    control_id: "",
    category: "",
    control: "",
    audit_step: "",
  });
  const [technologyInput, setTechnologyInput] = useState("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("All");

  const [checklist, setChecklist] =
    useState<ChecklistResponse | null>(null);

  const [draftChecklist, setDraftChecklist] =
    useState<ChecklistItem[]>([]);

  const [reviewStatus, setReviewStatus] =
    useState<ReviewStatus>("Draft");

  const [loading, setLoading] = useState(false);
  const [loadingExisting, setLoadingExisting] = useState(false);

  const [message, setMessage] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);

  const [editingControl, setEditingControl] = useState("");

  const [, setShowAiPanel] = useState(false);

  const [customTechnology, setCustomTechnology] =
    useState("");

  const [lastGenerated, setLastGenerated] =
    useState<string | null>(null);

  const categories = useMemo(() => {
    const source =
      draftChecklist.length > 0
        ? draftChecklist
        : checklist?.checklist || [];

    return [
      "All",
      ...Array.from(
        new Set(source.map((item) => item.category)),
      ),
    ];
  }, [checklist, draftChecklist]);

  const visibleItems = useMemo(() => {
    const source =
      draftChecklist.length > 0
        ? draftChecklist
        : checklist?.checklist || [];

    return source.filter((item) => {
      const matchesSearch =
        !search ||
        item.control
          .toLowerCase()
          .includes(search.toLowerCase()) ||
        item.audit_step
          .toLowerCase()
          .includes(search.toLowerCase()) ||
        item.item_id
          .toLowerCase()
          .includes(search.toLowerCase());

      const matchesCategory =
        categoryFilter === "All" ||
        item.category === categoryFilter;

      return matchesSearch && matchesCategory;
    });
  }, [
    checklist,
    draftChecklist,
    search,
    categoryFilter,
  ]);

  const errorText = async (response: Response, fallback: string) => {
    try {
      const body = await response.json();
      return body?.error?.message || body?.detail || fallback;
    } catch {
      return fallback;
    }
  };

  const loadTechnologies = async () => {
    const response = await apiFetch("/technologies");
    if (!response.ok) {
      setMessage(await errorText(response, "Unable to load technologies."));
      return;
    }
    const data: { technologies: TechOption[] } = await response.json();
    setTechnologies(data.technologies);
  };

  const applyVersion = (v: VersionDetail | null) => {
    setVersion(v);
    if (v && (v.status === "draft" || v.status === "pending_review")) {
      setDraftChecklist(v.checklist);
      setReviewStatus("Draft");
    } else {
      setDraftChecklist([]);
      setReviewStatus(v?.status === "rejected" ? "Rejected" : "Approved");
    }
  };

  const loadChecklist = async (technology: string) => {
    setLoadingExisting(true);
    setMessage("");

    try {
      const response = await apiFetch(
        `/checklists/${encodeURIComponent(technology)}`,
      );
      if (response.ok) {
        const data: ChecklistResponse = await response.json();
        setChecklist(data);
      } else if (response.status === 404) {
        setChecklist({ technology, total_controls: 0, checklist: [] });
      } else {
        throw new Error(
          await errorText(response, `Unable to load ${technology} checklist.`),
        );
      }

      // An open (draft / pending review) version, if any, takes over the review view.
      const list = await apiFetch(
        `/checklist-versions?technology=${encodeURIComponent(technology)}`,
      );
      let open: VersionDetail | null = null;
      if (list.ok) {
        const versions: VersionDetail[] = (await list.json()).versions;
        const found = versions.find(
          (v) => v.status === "draft" || v.status === "pending_review",
        );
        if (found) {
          const detail = await apiFetch(`/checklist-versions/${found.id}`);
          if (detail.ok) open = await detail.json();
        }
      }
      applyVersion(open);
      setLastGenerated(null);
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Unable to load checklist.",
      );
    } finally {
      setLoadingExisting(false);
    }
  };

  useEffect(() => {
    loadTechnologies();
    loadChecklist("linux-server");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const callVersion = async (
    path: string,
    init: RequestInit,
    failure: string,
  ) => {
    const response = await apiFetch(path, init);
    if (!response.ok) {
      setMessage(await errorText(response, failure));
      return null;
    }
    return response.json();
  };

  const startVersion = async (source: "library" | "baseline" | "manual") => {
    const technology = checklist?.technology || selectedTechnology;
    const created = await callVersion(
      "/checklist-versions",
      { method: "POST", body: JSON.stringify({ technology, source }) },
      "Unable to create a draft.",
    );
    if (created) {
      applyVersion(created);
      setMessage(`Draft v${created.version_no} created. Review, edit, then submit it for approval.`);
    }
  };

  const generateWithAI = async (technology?: string) => {
    const target =
      technology?.trim() ||
      customTechnology.trim() ||
      technologyInput.trim();

    if (!target) {
      setMessage(
        "Enter a technology name before generating an AI checklist.",
      );
      return;
    }

    setLoading(true);
    setMessage("");
    setShowAiPanel(true);

    try {
      const response = await apiFetch(
        `/checklists/${encodeURIComponent(
          target,
        )}/generate`,
      );

      if (!response.ok) {
        throw new Error(
          "AI checklist generation failed.",
        );
      }

      const data: ChecklistResponse =
        await response.json();

      setChecklist(data);
      setDraftChecklist(data.checklist || []);
      setReviewStatus("Draft");
      setSelectedTechnology(target);
      setLastGenerated(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      );

      setMessage(
        `AI generated ${data.total_controls} draft controls for ${target}.`,
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "AI generation failed.",
      );
    } finally {
      setLoading(false);
    }
  };

  const startEditing = (item: ChecklistItem) => {
    setEditingId(item.item_id);
    setEditingControl(item.control);
  };

  const saveEdit = async (itemId: string) => {
    const control = editingControl.trim();
    if (version && version.status === "draft") {
      if (!control) return;
      const updated = await callVersion(
        `/checklist-versions/${version.id}/controls/${encodeURIComponent(itemId)}`,
        { method: "PATCH", body: JSON.stringify({ control }) },
        "Unable to save the change.",
      );
      if (updated) {
        setDraftChecklist((items) =>
          items.map((item) => (item.item_id === itemId ? { ...item, ...updated } : item)),
        );
      }
    } else {
      setDraftChecklist((items) =>
        items.map((item) =>
          item.item_id === itemId ? { ...item, control: control || item.control } : item,
        ),
      );
    }
    setEditingId(null);
    setEditingControl("");
  };

  const removeControl = async (itemId: string) => {
    if (!version || version.status !== "draft") return;
    const done = await callVersion(
      `/checklist-versions/${version.id}/controls/${encodeURIComponent(itemId)}`,
      { method: "DELETE" },
      "Unable to remove the control.",
    );
    if (done) setDraftChecklist((items) => items.filter((i) => i.item_id !== itemId));
  };

  const addControl = async () => {
    if (!version || version.status !== "draft") return;
    const created = await callVersion(
      `/checklist-versions/${version.id}/controls`,
      { method: "POST", body: JSON.stringify(newControl) },
      "Unable to add the control.",
    );
    if (created) {
      setDraftChecklist((items) => [...items, created]);
      setNewControl({ control_id: "", category: "", control: "", audit_step: "" });
    }
  };

  // Persist an in-browser AI draft as a real draft version (so it goes through review).
  const saveAiDraftForReview = async () => {
    const technology = checklist?.technology || selectedTechnology;
    const created = await callVersion(
      "/checklist-versions",
      {
        method: "POST",
        body: JSON.stringify({
          technology,
          source: "manual",
          notes: "Imported from the AI draft generator; every control needs human verification.",
        }),
      },
      "Unable to save the draft.",
    );
    if (!created) return;
    for (const item of draftChecklist) {
      const ok = await callVersion(
        `/checklist-versions/${created.id}/controls`,
        {
          method: "POST",
          body: JSON.stringify({
            control_id: item.item_id,
            category: item.category,
            control: item.control,
            audit_step: item.audit_step,
            reference: item.reference,
          }),
        },
        `Unable to save control ${item.item_id}.`,
      );
      if (!ok) return;
    }
    await loadChecklist(technology);
    await loadTechnologies();
    setMessage("Draft saved. Submit it for review when you have validated every control.");
  };

  const approveChecklist = async () => {
    if (draftChecklist.length === 0) {
      setMessage("There is no draft to act on.");
      return;
    }
    if (!version) {
      await saveAiDraftForReview();
      return;
    }
    const action = version.status === "draft" ? "submit" : "approve";
    const result = await callVersion(
      `/checklist-versions/${version.id}/${action}`,
      { method: "POST", body: JSON.stringify({ comment: "" }) },
      action === "submit" ? "Unable to submit for review." : "Unable to approve.",
    );
    if (!result) return;
    if (action === "submit") {
      setVersion({ ...version, status: "pending_review" });
      setMessage("Submitted for review. A reviewer must approve it before it becomes the baseline.");
    } else {
      await loadChecklist(version.technology);
      await loadTechnologies();
      setMessage(`Version ${result.version_no} approved. It is now the audit baseline.`);
    }
  };

  const rejectChecklist = async () => {
    if (!version) {
      setDraftChecklist([]);
      setReviewStatus("Draft");
      setMessage("Draft discarded.");
      return;
    }
    const comment = window.prompt("Reason for rejection (required):")?.trim();
    if (!comment) return;
    const result = await callVersion(
      `/checklist-versions/${version.id}/reject`,
      { method: "POST", body: JSON.stringify({ comment }) },
      "Unable to reject.",
    );
    if (result) {
      await loadChecklist(version.technology);
      setMessage("Draft rejected. Start a new draft to continue.");
    }
  };

  return (
    <div className="checklists-page">
      <div className="checklists-glow glow-one" />
      <div className="checklists-glow glow-two" />

      <main className="checklists-content">
        {/* =====================================================
            HEADER
        ===================================================== */}

        <section className="checklists-header">
          <div>
            <div className="checklists-breadcrumb">
              <Shield size={15} />
              <span>Workspace</span>
              <ChevronDown size={13} />
              <span>Checklists</span>
            </div>

            <div className="checklists-title-row">
              <h1>Security Checklists</h1>

              <span className="library-status">
                <span />
                Library Operational
              </span>
            </div>

            <p>
              Manage security controls, review benchmark coverage,
              and generate AI-assisted draft checklists for new
              technologies.
            </p>
          </div>

          <button
            className="new-checklist-button"
            onClick={() => setShowAiPanel(true)}
          >
            <Plus size={17} />
            New Checklist
          </button>
        </section>

        {/* =====================================================
            AI HERO
        ===================================================== */}

        <section className="ai-hero">
          <div className="ai-hero-glow" />

          <div className="ai-hero-icon">
            <WandSparkles size={25} />
          </div>

          <div className="ai-hero-content">
            <div className="ai-label">
              <Sparkles size={13} />
              AI-ASSISTED CHECKLIST GENERATION
            </div>

            <h2>
              Generate a security checklist for a new technology.
            </h2>

            <p>
              Sentinel GRC can create a draft control set when a
              technology is not already available in the checklist
              library. The generated checklist remains a draft until
              a human reviewer validates it.
            </p>

            <div className="ai-workflow">
              <div className="workflow-step active">
                <span>01</span>
                Generate
              </div>

              <ArrowRight size={14} />

              <div className="workflow-step">
                <span>02</span>
                Review
              </div>

              <ArrowRight size={14} />

              <div className="workflow-step">
                <span>03</span>
                Approve
              </div>

              <ArrowRight size={14} />

              <div className="workflow-step">
                <span>04</span>
                Assess
              </div>
            </div>
          </div>

          <div className="ai-generator">
            <label>Technology</label>

            <div className="ai-input">
              <Sparkles size={16} />

              <input
                value={customTechnology}
                onChange={(event) =>
                  setCustomTechnology(event.target.value)
                }
                placeholder="e.g. AWS API Gateway"
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    generateWithAI();
                  }
                }}
              />
            </div>

            <button
              className="generate-button"
              onClick={() => generateWithAI()}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2
                    size={16}
                    className="spin"
                  />
                  Generating...
                </>
              ) : (
                <>
                  <WandSparkles size={16} />
                  Generate with AI
                </>
              )}
            </button>

            <span className="ai-disclaimer">
              AI output requires human review before approval.
            </span>
          </div>
        </section>

        {/* =====================================================
            MESSAGE
        ===================================================== */}

        {message && (
          <div
            className={`checklist-message ${
              reviewStatus === "Rejected"
                ? "error"
                : reviewStatus === "Approved"
                  ? "success"
                  : "info"
            }`}
          >
            {reviewStatus === "Rejected" ? (
              <AlertTriangle size={17} />
            ) : reviewStatus === "Approved" ? (
              <CheckCircle2 size={17} />
            ) : (
              <Sparkles size={17} />
            )}

            <span>{message}</span>

            <button
              onClick={() => setMessage("")}
              aria-label="Close"
            >
              <X size={15} />
            </button>
          </div>
        )}

        {/* =====================================================
            LIBRARY + REVIEW
        ===================================================== */}

        <section className="checklists-layout">
          {/* LIBRARY */}

          <aside className="library-panel panel">
            <div className="panel-heading">
              <div>
                <span className="panel-kicker">
                  CHECKLIST LIBRARY
                </span>

                <h2>Technologies</h2>
              </div>

              <Layers3 size={19} />
            </div>

            <div className="library-search">
              <Search size={15} />

              <input
                placeholder="Search technology"
                value={technologyInput}
                onChange={(event) =>
                  setTechnologyInput(event.target.value)
                }
              />
            </div>

            <div className="technology-list">
              {technologies.filter((technology) =>
                technology.name
                  .toLowerCase()
                  .includes(
                    technologyInput.toLowerCase(),
                  ),
              ).map((technology) => (
                <button
                  key={technology.slug}
                  className={`technology-list-item ${
                    selectedTechnology === technology.slug
                      ? "selected"
                      : ""
                  }`}
                  onClick={() => {
                    setSelectedTechnology(technology.slug);
                    loadChecklist(technology.slug);
                  }}
                >
                  <div className="technology-list-icon">
                    {technology.name.charAt(0)}
                  </div>

                  <div className="technology-list-info">
                    <strong>{technology.name}</strong>

                    <span>
                      {technology.controls > 0
                        ? `${technology.controls} controls · `
                        : ""}
                      {technology.approved_version
                        ? `Approved v${technology.approved_version}`
                        : technology.origin === "library"
                          ? "Library template"
                          : "Custom"}
                    </span>
                  </div>

                  <ChevronDown
                    size={15}
                    className="technology-chevron"
                  />
                </button>
              ))}

              {draftChecklist.length > 0 && (
                <button
                  className={`technology-list-item ai-item ${
                    selectedTechnology ===
                    (checklist?.technology || "")
                      ? "selected"
                      : ""
                  }`}
                  onClick={() => {
                    setSelectedTechnology(
                      checklist?.technology || "",
                    );
                  }}
                >
                  <div className="technology-list-icon ai">
                    <Sparkles size={15} />
                  </div>

                  <div className="technology-list-info">
                    <strong>
                      {checklist?.technology}
                    </strong>

                    <span>
                      {draftChecklist.length} AI draft controls
                    </span>
                  </div>

                  <span className="draft-badge">
                    DRAFT
                  </span>
                </button>
              )}
            </div>

            <div className="library-footer">
              <div>
                <FileCheck2 size={15} />
                <span>2 published checklists</span>
              </div>

              <span>Updated today</span>
            </div>
          </aside>

          {/* MAIN CHECKLIST */}

          <section className="checklist-panel panel">
            <div className="panel-heading checklist-heading">
              <div>
                <span className="panel-kicker">
                  {version
                    ? `DRAFT v${version.version_no} · ${version.status === "pending_review" ? "PENDING REVIEW" : "EDITING"}`
                    : draftChecklist.length > 0
                      ? "AI DRAFT (NOT SAVED)"
                      : "CONTROL LIBRARY"}
                </span>

                <div className="checklist-name-row">
                  <h2>
                    {checklist?.technology || selectedTechnology}
                  </h2>

                  {draftChecklist.length > 0 ? (
                    <span className="draft-status">
                      <Sparkles size={13} />
                      {version ? "Draft" : "AI Draft"}
                    </span>
                  ) : (
                    <span className="approved-status">
                      <CheckCircle2 size={13} />
                      {checklist?.approved
                        ? `Approved v${checklist.version_no}`
                        : checklist?.source === "library"
                          ? "Library template (not yet approved)"
                          : "No checklist yet"}
                    </span>
                  )}
                </div>

                <p>
                  {draftChecklist.length > 0
                    ? "Review every generated control before approving this checklist."
                    : "Security controls available for assessment."}
                </p>
              </div>

              <div className="checklist-actions">
                <button
                  className="secondary-button"
                  onClick={() =>
                    loadChecklist(selectedTechnology)
                  }
                  disabled={loadingExisting}
                >
                  {loadingExisting ? (
                    <Loader2
                      size={15}
                      className="spin"
                    />
                  ) : (
                    <RefreshCw size={15} />
                  )}

                  Refresh
                </button>

                {draftChecklist.length === 0 && checklist?.source === "library" && (
                  <button
                    className="secondary-button"
                    onClick={() => startVersion("library")}
                  >
                    <Edit3 size={15} />
                    Create draft from library
                  </button>
                )}

                {draftChecklist.length === 0 && checklist?.approved && (
                  <button
                    className="secondary-button"
                    onClick={() => startVersion("baseline")}
                  >
                    <Edit3 size={15} />
                    Modify baseline
                  </button>
                )}

                {draftChecklist.length === 0 && checklist && !checklist.source && (
                  <button
                    className="secondary-button"
                    onClick={() => startVersion("manual")}
                  >
                    <Edit3 size={15} />
                    Start manual checklist
                  </button>
                )}

                {draftChecklist.length > 0 && (!version || version.status === "pending_review") && (
                  <button className="reject-button" onClick={rejectChecklist}>
                    <XCircle size={15} />
                    {version ? "Reject" : "Discard"}
                  </button>
                )}

                {draftChecklist.length > 0 && (
                  <button className="approve-button" onClick={approveChecklist}>
                    <Check size={15} />
                    {!version
                      ? "Save draft for review"
                      : version.status === "draft"
                        ? "Submit for review"
                        : "Approve checklist"}
                  </button>
                )}
              </div>
            </div>

            {/* REVIEW BANNER */}

            {draftChecklist.length > 0 && (
              <div
                className={`review-banner ${
                  reviewStatus.toLowerCase()
                }`}
              >
                <div className="review-banner-icon">
                  {reviewStatus === "Draft" ? (
                    <Clock3 size={17} />
                  ) : reviewStatus === "Approved" ? (
                    <CheckCircle2 size={17} />
                  ) : (
                    <XCircle size={17} />
                  )}
                </div>

                <div>
                  <strong>
                    {reviewStatus === "Draft"
                      ? version?.status === "pending_review"
                        ? "Awaiting reviewer approval"
                        : "Human review required"
                      : reviewStatus === "Approved"
                        ? "Checklist approved"
                        : "Checklist rejected"}
                  </strong>

                  <span>
                    {reviewStatus === "Draft"
                      ? version?.status === "pending_review"
                        ? "Locked for review. A different reviewer must approve or reject it; it is not an audit baseline until approved."
                        : "Validate every control and reference, edit where required, then submit for review."

                      : reviewStatus === "Approved"
                        ? "This checklist has passed the reviewer checkpoint and can proceed to assessment."
                        : "This draft cannot be used for assessment until a new version is generated and approved."}
                  </span>
                </div>
              </div>
            )}

            {/* FILTERS */}

            <div className="checklist-toolbar">
              <div className="control-search">
                <Search size={15} />

                <input
                  value={search}
                  onChange={(event) =>
                    setSearch(event.target.value)
                  }
                  placeholder="Search controls..."
                />
              </div>

              <div className="category-filter">
                <Filter size={14} />

                <select
                  value={categoryFilter}
                  onChange={(event) =>
                    setCategoryFilter(event.target.value)
                  }
                >
                  {categories.map((category) => (
                    <option
                      key={category}
                      value={category}
                    >
                      {category}
                    </option>
                  ))}
                </select>
              </div>

              <div className="control-count">
                <span>
                  {visibleItems.length}
                </span>
                controls
              </div>
            </div>

            {version?.status === "draft" && (
              <div className="edit-control" style={{ margin: "0 0 12px" }}>
                <strong>Add a control</strong>
                {(["control_id", "category", "control", "audit_step"] as const).map((field) => (
                  <input
                    key={field}
                    placeholder={field.replace("_", " ")}
                    value={newControl[field]}
                    onChange={(event) =>
                      setNewControl({ ...newControl, [field]: event.target.value })
                    }
                  />
                ))}
                <div>
                  <button
                    className="save-edit"
                    onClick={addControl}
                    disabled={Object.values(newControl).some((v) => !v.trim())}
                  >
                    <Check size={14} />
                    Add control
                  </button>
                </div>
              </div>
            )}

            {/* CONTROLS */}

            <div className="controls-list">
              {visibleItems.length === 0 ? (
                <div className="controls-empty">
                  <Search size={25} />

                  <strong>
                    No controls found
                  </strong>

                  <span>
                    Try changing your search or category filter.
                  </span>
                </div>
              ) : (
                visibleItems.map((item, index) => (
                  <article
                    className="control-card"
                    key={item.item_id}
                  >
                    <div className="control-number">
                      {String(index + 1).padStart(2, "0")}
                    </div>

                    <div className="control-main">
                      <div className="control-topline">
                        <span className="control-id">
                          {item.item_id}
                        </span>

                        <span className="category-badge">
                          {item.category}
                        </span>

                        {draftChecklist.length > 0 && !version && (
                          <span className="ai-control-badge">
                            <Sparkles size={11} />
                            AI GENERATED
                          </span>
                        )}
                      </div>

                      {editingId === item.item_id ? (
                        <div className="edit-control">
                          <textarea
                            value={editingControl}
                            onChange={(event) =>
                              setEditingControl(
                                event.target.value,
                              )
                            }
                            autoFocus
                          />

                          <div>
                            <button
                              className="cancel-edit"
                              onClick={() => {
                                setEditingId(null);
                                setEditingControl("");
                              }}
                            >
                              Cancel
                            </button>

                            <button
                              className="save-edit"
                              onClick={() =>
                                saveEdit(item.item_id)
                              }
                            >
                              <Check size={14} />
                              Save change
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <h3>{item.control}</h3>

                          <p>{item.audit_step}</p>
                        </>
                      )}

                      <div className="control-reference">
                        <span>
                          Reference
                        </span>

                        <strong>
                          {item.reference || "None"}
                          {item.reference && item.reference_verified === false
                            ? " (unverified, check against the source)"
                            : ""}
                        </strong>
                      </div>
                    </div>

                    {draftChecklist.length > 0 &&
                      (!version || version.status === "draft") && (
                        <button
                          className="edit-control-button"
                          onClick={() => startEditing(item)}
                          title="Edit control"
                        >
                          <Edit3 size={15} />
                        </button>
                      )}

                    {version?.status === "draft" && (
                      <button
                        className="edit-control-button"
                        onClick={() => removeControl(item.item_id)}
                        title="Remove control"
                      >
                        <X size={15} />
                      </button>
                    )}

                    <div className="control-state">
                      {draftChecklist.length > 0 ? (
                        <span className="pending-state">
                          <Clock3 size={14} />
                          Review
                        </span>
                      ) : (
                        <span className="published-state">
                          <CheckCircle2 size={14} />
                          {checklist?.approved ? "Approved" : "Template"}
                        </span>
                      )}
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>
        </section>

        {/* =====================================================
            BOTTOM AI STATUS
        ===================================================== */}

        {lastGenerated && (
          <section className="generation-summary">
            <div className="generation-summary-icon">
              <Sparkles size={18} />
            </div>

            <div>
              <strong>AI generation completed</strong>

              <span>
                {draftChecklist.length} controls generated at{" "}
                {lastGenerated}. Human review is required before
                assessment.
              </span>
            </div>

            <div className="generation-summary-status">
              <span
                className={
                  reviewStatus === "Approved"
                    ? "approved"
                    : reviewStatus === "Rejected"
                      ? "rejected"
                      : "pending"
                }
              />

              {reviewStatus}
            </div>
          </section>
        )}

        {/* =====================================================
            FOOTER
        ===================================================== */}

        <footer className="checklists-footer">
          <div>
            <Shield size={14} />
            <span>Sentinel GRC</span>
            <span>v1.0</span>
          </div>

          <span>
            Security Configuration &amp; Compliance Platform
          </span>
        </footer>
      </main>
    </div>
  );
}

export default Checklists;