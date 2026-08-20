import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import json

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

SHEETS_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
ACTIVITY_TAB = "_activity_log"
LIBRARY_TAB = "_checklist_library"
DEFAULT_AI_MODEL = "claude-sonnet-5"

# ---------------------------------------------------------------------------
# TEAM / IDENTITY
# Configure real reviewer names in secrets.toml:
#   [team]
#   members = ["Jane Doe", "Alex Rivera", "Priya Nair"]
# Falls back to three generic seats so the app runs out of the box.
# ---------------------------------------------------------------------------

def get_team_members():
    configured = st.secrets.get("team", {}).get("members", None)
    if configured and len(configured) > 0:
        return list(configured)
    return ["Reviewer 1", "Reviewer 2", "Reviewer 3"]


# ---------------------------------------------------------------------------
# GOOGLE SHEETS - shared, multi-user persistence layer
# One spreadsheet, one tab per client__technology engagement, plus a single
# _activity_log tab so every seat can see who changed what, when.
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_gsheet_client():
    if not GSPREAD_AVAILABLE:
        return None
    if "gcp_service_account" not in st.secrets or "sheet_id" not in st.secrets.get("gsheets", {}):
        return None
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SHEETS_SCOPE
    )
    return gspread.authorize(creds)


def cloud_persistence_enabled() -> bool:
    return get_gsheet_client() is not None


def _sheet_tab_name(client_name: str, technology: str) -> str:
    raw = f"{client_name}__{technology}".strip() or "untitled"
    safe = "".join(c for c in raw if c.isalnum() or c in ("_", "-", " "))
    return safe[:95]


RESPONSE_COLUMNS = [
    "item_id", "category", "control", "reference", "audit_step", "status",
    "severity", "notes", "assigned_to", "last_updated_by", "last_updated_at",
]


def save_to_cloud(client_name: str, technology: str, responses: dict, actor: str) -> None:
    gc = get_gsheet_client()
    if gc is None:
        return
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    tab_name = _sheet_tab_name(client_name, technology)
    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=max(200, len(responses) + 20), cols=len(RESPONSE_COLUMNS) + 2)

    rows = [RESPONSE_COLUMNS]
    for item_id, data in responses.items():
        rows.append([item_id] + [str(data.get(col, "") or "") for col in RESPONSE_COLUMNS[1:]])
    ws.update(rows)
    log_activity(sh, actor, client_name, technology, f"Saved {len(responses)} control(s) to the shared workspace.")


def load_from_cloud(client_name: str, technology: str) -> dict:
    gc = get_gsheet_client()
    if gc is None:
        return {}
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    tab_name = _sheet_tab_name(client_name, technology)
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return {}

    records = ws.get_all_records()
    loaded = {}
    for row in records:
        item_id = row.get("item_id")
        if not item_id:
            continue
        loaded[item_id] = {
            "status": row.get("status", "Not Reviewed") or "Not Reviewed",
            "notes": row.get("notes", ""),
            "category": row.get("category", ""),
            "control": row.get("control", ""),
            "reference": row.get("reference", ""),
            "audit_step": row.get("audit_step", ""),
            "severity": row.get("severity", ""),
            "assigned_to": row.get("assigned_to", ""),
            "last_updated_by": row.get("last_updated_by", ""),
            "last_updated_at": row.get("last_updated_at", ""),
        }
    return loaded


def log_activity(sh, actor, client_name, technology, message):
    try:
        try:
            log_ws = sh.worksheet(ACTIVITY_TAB)
        except gspread.WorksheetNotFound:
            log_ws = sh.add_worksheet(title=ACTIVITY_TAB, rows=500, cols=5)
            log_ws.update([["timestamp", "user", "client", "technology", "action"]])
        log_ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actor, client_name, technology, message,
        ])
    except Exception:
        pass  # activity logging is best-effort and must never block a save


def fetch_activity_log(limit=25):
    gc = get_gsheet_client()
    if gc is None:
        return []
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    try:
        log_ws = sh.worksheet(ACTIVITY_TAB)
    except gspread.WorksheetNotFound:
        return []
    records = log_ws.get_all_records()
    return list(reversed(records))[:limit]


def list_client_engagements(client_name: str):
    """Return per-technology rollups for every tab belonging to this client."""
    gc = get_gsheet_client()
    if gc is None:
        return []
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    prefix = f"{client_name}__"
    out = []
    for ws in sh.worksheets():
        if ws.title == ACTIVITY_TAB or ws.title == LIBRARY_TAB or not ws.title.startswith(prefix):
            continue
        technology = ws.title[len(prefix):]
        try:
            records = ws.get_all_records()
        except Exception:
            continue
        if not records:
            continue
        df = pd.DataFrame(records)
        if "severity" not in df.columns or "status" not in df.columns:
            continue
        df["weight"] = df["severity"].map(SEVERITY_WEIGHTS).fillna(1)
        applicable = df[df["status"] != "Not Applicable"]
        good = applicable[applicable["status"].isin(["Compliant", "Compensating Control"])]
        weighted_pct = round((good["weight"].sum() / applicable["weight"].sum()) * 100, 1) if len(applicable) else 0.0
        crit_open = int(((df["status"] == "Non-Compliant") & (df["severity"] == "Critical")).sum())
        out.append({
            "technology": technology,
            "controls": len(df),
            "weighted_compliance": weighted_pct,
            "non_compliant": int((df["status"] == "Non-Compliant").sum()),
            "critical_open": crit_open,
            "not_reviewed": int((df["status"] == "Not Reviewed").sum()),
        })
    return sorted(out, key=lambda x: x["weighted_compliance"])


# ---------------------------------------------------------------------------
# CHECKLIST LIBRARY - the "client brought a technology we don't have yet"
# problem. Any AI-drafted or manually-typed checklist is written to a single
# shared _checklist_library tab so it becomes a PERMANENT addition to the
# platform for every reviewer, not just something that exists for the rest
# of one browser session. On startup every seat pulls the current library
# and it's merged on top of the built-in CHECKLISTS.
# ---------------------------------------------------------------------------

LIBRARY_COLUMNS = ["technology", "item_id", "category", "control", "reference", "audit_step", "source", "added_by", "added_at"]


def save_checklist_to_library(technology: str, items: list, source: str, actor: str) -> None:
    """items: list of (item_id, category, control, reference, audit_step) tuples."""
    gc = get_gsheet_client()
    if gc is None:
        return
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    try:
        ws = sh.worksheet(LIBRARY_TAB)
        existing = ws.get_all_records()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=LIBRARY_TAB, rows=1000, cols=len(LIBRARY_COLUMNS) + 2)
        ws.update([LIBRARY_COLUMNS])
        existing = []

    # Drop any prior rows for this exact technology name (re-drafts overwrite), keep everything else.
    keep_rows = [LIBRARY_COLUMNS] + [
        [r.get(c, "") for c in LIBRARY_COLUMNS] for r in existing if r.get("technology") != technology
    ]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_rows = [
        [technology, item_id, category, control, reference, audit_step, source, actor, now]
        for item_id, category, control, reference, audit_step in items
    ]
    ws.clear()
    ws.update(keep_rows + new_rows)
    log_activity(sh, actor, "—", technology, f"Added '{technology}' to the shared checklist library ({len(items)} controls, {source}).")


def load_checklist_library() -> dict:
    """Returns {technology_display_name: [(item_id, category, control, reference, audit_step), ...]}."""
    gc = get_gsheet_client()
    if gc is None:
        return {}
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    try:
        ws = sh.worksheet(LIBRARY_TAB)
    except gspread.WorksheetNotFound:
        return {}
    records = ws.get_all_records()
    out = {}
    for r in records:
        tech = r.get("technology")
        if not tech:
            continue
        out.setdefault(tech, []).append((
            r.get("item_id", ""), r.get("category", ""), r.get("control", ""),
            r.get("reference", ""), r.get("audit_step", ""),
        ))
    return out


# ---------------------------------------------------------------------------
# AI CONNECTION - Anthropic (Claude), configured via Streamlit secrets:
#   [anthropic]
#   api_key = "sk-ant-..."
#   model   = "claude-sonnet-5"   # optional, defaults to DEFAULT_AI_MODEL
#
# The previous Hugging Face integration required a separate HF token that
# was never configured in this app's secrets, so ai_enabled() always
# returned False and every AI feature silently no-oped. Anthropic is used
# here instead since it needs only one key and matches the rest of the
# platform's tooling.
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_ai_client():
    if not ANTHROPIC_AVAILABLE:
        return None
    if "anthropic" not in st.secrets or "api_key" not in st.secrets.get("anthropic", {}):
        return None
    try:
        return anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])
    except Exception:
        return None


def ai_enabled() -> bool:
    return get_ai_client() is not None


def ask_ai(prompt: str, system: str = "", max_tokens: int = 900) -> str:
    client = get_ai_client()
    if client is None:
        return "⚠️ AI features are not configured. Add an API key under [anthropic] in Streamlit secrets."
    model = st.secrets.get("anthropic", {}).get("model", DEFAULT_AI_MODEL)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or "You are a precise, audit-focused security assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    except Exception as e:
        return f"⚠️ AI request failed: {e}"


# ---------------------------------------------------------------------------
# AGENTIC AI - autonomous, multi-step drafting & remediation
#
# ask_ai() above is a single request/response call. The functions below
# chain several calls together, enforce structured output, and self-correct
# on malformed JSON — so a reviewer triggers one action ("draft a checklist
# for this technology", "remediate all open findings") and the agent carries
# it through to a usable, structured result without further prompting.
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = (
    "You are a GRC security configuration auditor. You produce precise, "
    "audit-ready output only. When asked for JSON, return ONLY valid JSON - "
    "no markdown fences, no commentary, no preamble, no trailing text."
)


def _call_ai_json(prompt: str, system: str = AGENT_SYSTEM_PROMPT, max_tokens: int = 2000, retries: int = 2):
    """Call the model expecting JSON; self-correct up to `retries` times on parse failure."""
    if not ai_enabled():
        return None, "AI is not configured. Add an API key under [anthropic] in Streamlit secrets."

    last_error = None
    current_prompt = prompt
    for _ in range(retries + 1):
        raw = ask_ai(current_prompt, system=system, max_tokens=max_tokens)
        if raw.startswith("⚠️"):
            return None, raw
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned), None
        except json.JSONDecodeError as e:
            last_error = str(e)
            current_prompt = (
                f"{prompt}\n\nYour previous response could not be parsed as JSON "
                f"(error: {last_error}). Return ONLY valid JSON this time, with no "
                f"markdown fences and no extra text before or after it."
            )
    return None, f"AI returned malformed JSON after {retries + 1} attempts: {last_error}"


def agentic_draft_checklist(technology: str, context_notes: str = "", target_count: int = 20):
    """
    Autonomous drafting agent: given just a technology name, produces a full
    audit checklist (items + severity + framework mapping) with no further
    human input required. Returns (items, error).
    """
    prompt = f"""Draft a security configuration audit checklist for: {technology}

{f"Additional context from the reviewer: {context_notes}" if context_notes else ""}

Produce {target_count} distinct, specific, testable controls covering areas such as
authentication, access control, network exposure, encryption, logging/monitoring,
patching, and backup/recovery as applicable to this technology.

Return ONLY a JSON array. Each element must have exactly these keys:
"item_id" (short unique code like "AWS-01"), "category", "control" (one sentence),
"reference" (a plausible official hardening/benchmark reference, e.g. "CIS Benchmark 1.2"),
"audit_step" (a concrete, executable command or verification step an auditor would run)."""

    items, error = _call_ai_json(prompt, max_tokens=3000)
    if error:
        return [], error
    if not isinstance(items, list):
        return [], "AI response was valid JSON but not a list of controls."

    enriched = []
    for it in items:
        if not isinstance(it, dict) or "control" not in it:
            continue
        classification = classify_control(it.get("category", ""), it.get("control", ""))
        enriched.append({
            "item_id": it.get("item_id") or f"{technology[:3].upper()}-{len(enriched)+1:02d}",
            "category": it.get("category", "General"),
            "control": it.get("control", ""),
            "reference": it.get("reference", ""),
            "audit_step": it.get("audit_step", ""),
            "severity": classification["severity"],
            "frameworks": classification["frameworks"],
        })
    return enriched, None


def agentic_remediation_sweep(technology: str, responses: dict):
    """
    Autonomous remediation agent: scans every Non-Compliant item in one pass
    and drafts a remediation note for each in a single batched call, instead
    of requiring one prompt per finding. Returns (updated_responses, error).
    """
    open_items = {
        item_id: data for item_id, data in responses.items()
        if data.get("status") == "Non-Compliant"
    }
    if not open_items:
        return responses, "No Non-Compliant items to remediate."

    items_block = "\n".join(
        f'- {item_id}: {data.get("control", "")} (severity: {data.get("severity", "")}, '
        f'notes: {data.get("notes", "") or "none"})'
        for item_id, data in open_items.items()
    )
    prompt = f"""Technology under review: {technology}

The following controls are marked Non-Compliant:
{items_block}

For each item, draft a concise, actionable remediation step (1-2 sentences,
specific enough for an engineer to execute without further clarification).

Return ONLY a JSON object mapping each item_id to its remediation string, e.g.:
{{"AWS-01": "Enable MFA delete on the S3 bucket via ..."}}"""

    remediations, error = _call_ai_json(prompt, max_tokens=2000)
    if error:
        return responses, error
    if not isinstance(remediations, dict):
        return responses, "AI response was valid JSON but not an object."

    updated = {k: dict(v) for k, v in responses.items()}
    tag = "[AI-drafted remediation]"
    for item_id, remediation in remediations.items():
        if item_id in updated:
            existing_notes = updated[item_id].get("notes", "") or ""
            if tag not in existing_notes:
                updated[item_id]["notes"] = (
                    f"{existing_notes}\n\n{tag} {remediation}".strip()
                    if existing_notes else f"{tag} {remediation}"
                )
    return updated, None


def agentic_executive_summary(client_name: str, technology: str, weighted_pct: float,
                               totals: dict, top_findings: list) -> str:
    """Single-shot summary agent — plain prose, not JSON."""
    findings_block = "\n".join(
        f"- [{f.get('Severity', '')}] {f.get('Control', '')}" for f in top_findings[:8]
    )
    prompt = f"""Write a 3-4 paragraph executive summary for a security configuration
audit report.

Client: {client_name}
Technology assessed: {technology}
Risk-weighted compliance: {weighted_pct}%
Totals: {json.dumps(totals)}

Top open findings:
{findings_block if findings_block else "None - no open Non-Compliant findings."}

Write for a non-technical executive audience. Be direct about risk. Do not
use markdown headers or bullet lists - plain prose paragraphs only."""

    return ask_ai(prompt, system=AGENT_SYSTEM_PROMPT, max_tokens=700)


st.set_page_config(page_title="Sentinel GRC | Security Configuration & Compliance Platform", layout="wide", page_icon="🛡️")

# ---------------------------------------------------------------------------
# THEME - dark, professional GRC-console styling
# ---------------------------------------------------------------------------

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.stApp {
    background: linear-gradient(180deg, #0b1120 0%, #0f172a 100%);
}
h1, h2, h3, h4 { color: #e2e8f0 !important; letter-spacing: -0.01em; }
p, li, span, label, .stMarkdown { color: #cbd5e1; }
.stCaption, [data-testid="stCaptionContainer"] { color: #64748b !important; }

.hero-banner {
    background: linear-gradient(120deg, #0f172a 0%, #1e293b 60%, #0f172a 100%);
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 22px 28px;
    margin-bottom: 18px;
    box-shadow: 0 0 0 1px rgba(56,189,248,0.06), 0 8px 24px rgba(0,0,0,0.35);
}
.hero-title { font-size: 26px; font-weight: 700; color: #f1f5f9; margin: 0; }
.hero-sub { font-size: 13.5px; color: #7dd3fc; margin-top: 4px; font-weight: 500; letter-spacing: 0.02em; text-transform: uppercase; }
.hero-meta { font-size: 13px; color: #94a3b8; margin-top: 10px; }
.hero-meta b { color: #e2e8f0; }

[data-testid="stMetric"] {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 12px 14px 8px 14px;
}
[data-testid="stMetricLabel"] { color: #94a3b8 !important; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; }

section[data-testid="stSidebar"] {
    background: #0b1120;
    border-right: 1px solid #1e293b;
}
.badge {
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.02em;
}
.badge-you { background: rgba(56,189,248,0.15); color: #7dd3fc; border: 1px solid rgba(56,189,248,0.35); }
.audit-step {
    background: #0b1120; border: 1px solid #1e293b; border-radius: 6px;
    padding: 6px 10px; font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 12.5px; color: #a5b4fc; margin: 4px 0;
}
div[data-testid="stExpander"] {
    background: #0f172a; border: 1px solid #1e293b !important; border-radius: 10px;
}
hr { border-color: #1e293b; }
</style>
""", unsafe_allow_html=True)

TEAM_MEMBERS = get_team_members()

# ---------------------------------------------------------------------------
# CONTROL CLASSIFICATION - severity + compliance-framework cross-mapping
# Rule-based on category/control keywords rather than hand-tagged per item.
# This is a starting point a reviewer should confirm before client delivery -
# keyword rules can misclassify an unusual control, so treat this as triage,
# not a final audit opinion.
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

_SEVERITY_RULES = [
    (4, ["root login", "default password", "empty password", "anonymous", "sa account",
         "enable secret", "encryption key", "unencrypted", "public", "0.0.0.0/0",
         "xp_cmdshell", "anonymous auth", "trust-all", "hardcoded"]),
    (3, ["authentication", "password", "mfa", "multi-factor", "privilege", "admin",
         "encrypt", "tls", "ssl", "firewall", "acl", "access control", "rbac",
         "vault", "secrets", "delegation", "superuser", "sa ", "audit trail"]),
    (2, ["logging", "audit", "monitoring", "patch", "update", "backup", "session",
         "timeout", "ntp", "dns", "certificate", "header"]),
]


def classify_control(category: str, control: str) -> dict:
    text = f"{category} {control}".lower()
    severity = "Low"
    for weight, keywords in _SEVERITY_RULES:
        if any(k in text for k in keywords):
            severity = {4: "Critical", 3: "High", 2: "Medium"}[weight]
            break

    frameworks = {}
    if any(k in text for k in ["auth", "password", "mfa", "admin", "privilege", "access control", "acl", "rbac"]):
        frameworks = {"ISO 27001": "A.9 Access Control", "NIST CSF": "PR.AC", "PCI DSS": "Req 7-8", "SOC 2": "CC6.1"}
    elif any(k in text for k in ["log", "audit", "monitor"]):
        frameworks = {"ISO 27001": "A.12.4 Logging & Monitoring", "NIST CSF": "DE.AE / DE.CM", "PCI DSS": "Req 10", "SOC 2": "CC7.2"}
    elif any(k in text for k in ["encrypt", "tls", "ssl", "certificate"]):
        frameworks = {"ISO 27001": "A.10 Cryptography", "NIST CSF": "PR.DS", "PCI DSS": "Req 3-4", "SOC 2": "CC6.7"}
    elif any(k in text for k in ["firewall", "network", "vpn", "interface", "acl", "flow log"]):
        frameworks = {"ISO 27001": "A.13 Network Security", "NIST CSF": "PR.AC / PR.PT", "PCI DSS": "Req 1", "SOC 2": "CC6.6"}
    elif any(k in text for k in ["patch", "version", "update", "cpu", "installation"]):
        frameworks = {"ISO 27001": "A.12.6 Vulnerability Management", "NIST CSF": "ID.RA / PR.MA", "PCI DSS": "Req 6", "SOC 2": "CC7.1"}
    elif any(k in text for k in ["backup", "recovery", "ha ", "high availability", "replication"]):
        frameworks = {"ISO 27001": "A.17 Business Continuity", "NIST CSF": "PR.IP / RC.RP", "PCI DSS": "Req 12", "SOC 2": "A1.2"}
    else:
        frameworks = {"ISO 27001": "A.12 Operations Security", "NIST CSF": "PR.IP", "PCI DSS": "Req 2", "SOC 2": "CC6.8"}

    return {"severity": severity, "frameworks": frameworks}


def build_docx_report(client_name, technology, reviewer_name, weighted_pct, raw_pct,
                       totals, open_items, exec_summary, all_responses) -> bytes:
    if not DOCX_AVAILABLE:
        return b""

    doc = Document()

    title = doc.add_heading("Security Configuration Assessment Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f"Client: {client_name}\n").bold = True
    meta.add_run(f"Technology Assessed: {technology}\n")
    meta.add_run(f"Lead Reviewer: {reviewer_name or '—'}\n")
    meta.add_run(f"Report Date: {datetime.now().strftime('%Y-%m-%d')}")

    doc.add_page_break()

    doc.add_heading("Executive Summary", level=1)
    if exec_summary:
        doc.add_paragraph(exec_summary)
    else:
        doc.add_paragraph(
            "Executive summary not generated for this report. Use the "
            "'Generate Executive Summary' AI feature on the Compliance "
            "Dashboard tab before exporting to include one here."
        )

    doc.add_heading("Compliance Overview", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text = "Metric", "Value"
    metrics = [
        ("Risk-Weighted Compliance", f"{weighted_pct}%"),
        ("Raw Compliance", f"{raw_pct}%"),
        ("Total Controls Assessed", str(totals["total"])),
        ("Compliant", str(totals["compliant"])),
        ("Non-Compliant", str(totals["noncompliant"])),
        ("Compensating Control", str(totals["compensating"])),
        ("Not Reviewed", str(totals["not_reviewed"])),
    ]
    for label, value in metrics:
        row = table.add_row().cells
        row[0].text, row[1].text = label, value

    doc.add_heading("Open Findings (Remediation Tracker)", level=1)
    if open_items:
        sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        sorted_items = sorted(open_items, key=lambda x: sev_order.get(x.get("Severity"), 4))
        ftable = doc.add_table(rows=1, cols=6)
        ftable.style = "Light Grid Accent 1"
        fhdr = ftable.rows[0].cells
        for idx, label in enumerate(["Item", "Severity", "Control", "Audit Step", "Notes", "Owner"]):
            fhdr[idx].text = label
        for it in sorted_items:
            row = ftable.add_row().cells
            row[0].text = str(it.get("Item", ""))
            row[1].text = str(it.get("Severity", ""))
            row[2].text = str(it.get("Control", ""))
            row[3].text = str(it.get("Audit Step", ""))
            row[4].text = str(it.get("Notes", "") or "")
            row[5].text = str(it.get("Assigned", "") or "Unassigned")
    else:
        doc.add_paragraph("No open Non-Compliant findings at time of report generation.")

    doc.add_heading("Full Control Detail", level=1)
    dtable = doc.add_table(rows=1, cols=6)
    dtable.style = "Light Grid Accent 1"
    dhdr = dtable.rows[0].cells
    for idx, label in enumerate(["Item", "Control", "Status", "Severity", "Reference", "Reviewed By"]):
        dhdr[idx].text = label
    for item_id, data in sorted(all_responses.items()):
        row = dtable.add_row().cells
        row[0].text = item_id
        row[1].text = str(data.get("control", ""))
        row[2].text = str(data.get("status", ""))
        row[3].text = str(data.get("severity", ""))
        row[4].text = str(data.get("reference", ""))
        row[5].text = str(data.get("last_updated_by", "") or "")

    footer_note = doc.add_paragraph()
    footer_run = footer_note.add_run(
        "This report was generated by Sentinel GRC. Findings reflect the state of "
        "configuration reviews as of the report date and should be validated against "
        "current production state before remediation sign-off."
    )
    footer_run.italic = True
    footer_run.font.size = Pt(9)
    footer_run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
