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
    from huggingface_hub import InferenceClient
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

SHEETS_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
ACTIVITY_TAB = "_activity_log"
LIBRARY_TAB = "_checklist_library"
DEFAULT_AI_MODEL = "HuggingFaceH4/zephyr-7b-beta"

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
# AI CONNECTION - Hugging Face free Inference API, configured via Streamlit
# secrets:
#   [huggingface]
#   api_key = "hf_..."                          # free token from huggingface.co/settings/tokens
#   model   = "HuggingFaceH4/zephyr-7b-beta"     # optional, defaults to DEFAULT_AI_MODEL
#
# This is a hosted free tier: no cost, but requests can queue or be slower
# than a paid API, and a model can occasionally be unavailable if it's
# cold-starting on Hugging Face's shared infrastructure. If a request fails,
# ask_ai() surfaces the error rather than failing silently.
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_ai_client():
    if not HF_AVAILABLE:
        return None
    if "huggingface" not in st.secrets or "api_key" not in st.secrets.get("huggingface", {}):
        return None
    model = st.secrets["huggingface"].get("model", DEFAULT_AI_MODEL)
    try:
        return InferenceClient(model=model, token=st.secrets["huggingface"]["api_key"])
    except Exception:
        return None


def ai_enabled() -> bool:
    return get_ai_client() is not None


def ask_ai(prompt: str, system: str = "", max_tokens: int = 900) -> str:
    client = get_ai_client()
    if client is None:
        return "⚠️ AI features are not configured. Add a free token under [huggingface] in Streamlit secrets."
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = client.chat_completion(messages=messages, max_tokens=max_tokens, temperature=0.3)
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI request failed: {e}. The free Hugging Face tier can be slow to cold-start or occasionally unavailable — try again in a moment."


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
        return None, "AI is not configured. Add a free token under [huggingface] in Streamlit secrets."

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


# ---------------------------------------------------------------------------
# UI DATA HELPERS
# ---------------------------------------------------------------------------

STATUS_OPTIONS = ["Not Reviewed", "Compliant", "Non-Compliant", "Compensating Control", "Not Applicable"]
STATUS_COLORS = {
    "Not Reviewed": "#64748b",
    "Compliant": "#22c55e",
    "Non-Compliant": "#ef4444",
    "Compensating Control": "#eab308",
    "Not Applicable": "#475569",
}

# A small built-in starter so the app has something to load with zero setup.
# Everything else comes from the shared checklist library (built manually or
# by the AI drafting agent below).
STARTER_CHECKLISTS = {
    "Generic Baseline": [
        ("GEN-01", "Access Control", "Default or vendor-supplied credentials have been changed on all accounts.", "CIS Controls v8 - 5.2", "Attempt login with known default credentials; confirm failure."),
        ("GEN-02", "Access Control", "Multi-factor authentication is enforced for all administrative access.", "CIS Controls v8 - 6.5", "Review IAM/auth policy for MFA enforcement on privileged roles."),
        ("GEN-03", "Network Security", "Administrative interfaces are not exposed to the public internet.", "CIS Controls v8 - 4.4", "Scan public IP ranges for management ports (22, 3389, admin consoles)."),
        ("GEN-04", "Cryptography", "Data in transit is encrypted using TLS 1.2 or higher.", "CIS Controls v8 - 3.10", "Run a TLS scan against exposed endpoints and check the negotiated version."),
        ("GEN-05", "Logging & Monitoring", "Audit logging is enabled and forwarded to a central log store.", "CIS Controls v8 - 8.2", "Confirm log forwarding configuration and retention period."),
        ("GEN-06", "Vulnerability Management", "The system is on a supported version with current security patches.", "CIS Controls v8 - 7.1", "Compare the installed version against the vendor's current release/EOL list."),
    ],
}


def build_checklist_catalog():
    """Merge the built-in starter checklist with anything drafted into the shared library."""
    catalog = {name: list(items) for name, items in STARTER_CHECKLISTS.items()}
    for name, items in load_checklist_library().items():
        catalog[name] = items
    return catalog


def items_to_responses(items):
    """
    Accepts either 5-tuples (item_id, category, control, reference, audit_step)
    from the starter set / library, or the richer dicts agentic_draft_checklist()
    returns. Always outputs a normalized responses dict.
    """
    responses = {}
    for it in items:
        if isinstance(it, dict):
            item_id = it["item_id"]
            severity = it.get("severity") or classify_control(it.get("category", ""), it.get("control", ""))["severity"]
            category, control, reference, audit_step = (
                it.get("category", ""), it.get("control", ""), it.get("reference", ""), it.get("audit_step", ""),
            )
        else:
            item_id, category, control, reference, audit_step = it
            severity = classify_control(category, control)["severity"]

        responses[item_id] = {
            "category": category,
            "control": control,
            "reference": reference,
            "audit_step": audit_step,
            "severity": severity,
            "status": "Not Reviewed",
            "notes": "",
            "assigned_to": "",
            "last_updated_by": "",
            "last_updated_at": "",
        }
    return responses


def compute_totals(responses: dict) -> dict:
    statuses = [d.get("status", "Not Reviewed") for d in responses.values()]
    totals = {
        "total": len(statuses),
        "compliant": statuses.count("Compliant"),
        "noncompliant": statuses.count("Non-Compliant"),
        "compensating": statuses.count("Compensating Control"),
        "not_applicable": statuses.count("Not Applicable"),
        "not_reviewed": statuses.count("Not Reviewed"),
    }
    applicable = totals["total"] - totals["not_applicable"]
    good = totals["compliant"] + totals["compensating"]
    totals["raw_pct"] = round((good / applicable) * 100, 1) if applicable else 0.0

    weight_sum, good_weight_sum = 0, 0
    for d in responses.values():
        if d.get("status") == "Not Applicable":
            continue
        w = SEVERITY_WEIGHTS.get(d.get("severity"), 1)
        weight_sum += w
        if d.get("status") in ("Compliant", "Compensating Control"):
            good_weight_sum += w
    totals["weighted_pct"] = round((good_weight_sum / weight_sum) * 100, 1) if weight_sum else 0.0
    return totals


def init_session_state():
    defaults = {
        "client_name": "",
        "technology": "",
        "reviewer": TEAM_MEMBERS[0] if TEAM_MEMBERS else "",
        "responses": {},
        "exec_summary": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ---------------------------------------------------------------------------
# SIDEBAR - engagement setup
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🛡️ Sentinel GRC")
    st.session_state.client_name = st.text_input("Client", value=st.session_state.client_name, placeholder="Acme Corp")

    reviewer_index = TEAM_MEMBERS.index(st.session_state.reviewer) if st.session_state.reviewer in TEAM_MEMBERS else 0
    st.session_state.reviewer = st.selectbox("Lead reviewer", TEAM_MEMBERS, index=reviewer_index)

    st.markdown("---")
    catalog = build_checklist_catalog()
    catalog_names = sorted(catalog.keys())
    choice = st.selectbox("Technology / checklist", ["— select —"] + catalog_names + ["+ New (draft with AI)"])

    if choice == "+ New (draft with AI)":
        st.session_state.technology = st.text_input("New technology name", placeholder="e.g. Snowflake")
        st.caption("Head to the Agentic AI tab to draft its checklist automatically.")
    elif choice != "— select —":
        st.session_state.technology = choice
        if st.button("Load checklist", use_container_width=True):
            st.session_state.responses = items_to_responses(catalog[choice])
            st.session_state.exec_summary = ""
            st.rerun()

    if cloud_persistence_enabled() and st.session_state.technology and st.session_state.client_name:
        if st.button("☁️ Load saved progress", use_container_width=True):
            loaded = load_from_cloud(st.session_state.client_name, st.session_state.technology)
            if loaded:
                st.session_state.responses = loaded
                st.success(f"Loaded {len(loaded)} saved controls.")
            else:
                st.info("No saved progress found for this client/technology yet.")

    st.markdown("---")
    st.caption(f"☁️ Cloud sync: {'connected' if cloud_persistence_enabled() else 'not configured'}")
    ai_model_label = st.secrets.get("huggingface", {}).get("model", DEFAULT_AI_MODEL)
    st.caption(f"🤖 AI agent: {'connected (' + ai_model_label + ')' if ai_enabled() else 'not configured'}")

# ---------------------------------------------------------------------------
# HERO BANNER
# ---------------------------------------------------------------------------

st.markdown(f"""
<div class="hero-banner">
    <p class="hero-title">Sentinel GRC</p>
    <p class="hero-sub">Security Configuration &amp; Compliance Platform</p>
    <p class="hero-meta">
        <b>Client:</b> {st.session_state.client_name or '—'} &nbsp;|&nbsp;
        <b>Technology:</b> {st.session_state.technology or '—'} &nbsp;|&nbsp;
        <b>Reviewer:</b> {st.session_state.reviewer or '—'}
    </p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.technology:
    st.info("Pick a technology from the sidebar, or type a new one and draft its checklist automatically on the **Agentic AI** tab.")

tab_checklist, tab_agent, tab_dashboard, tab_log, tab_export = st.tabs(
    ["✅ Checklist", "🤖 Agentic AI", "📊 Dashboard", "🕘 Activity Log", "📄 Export"]
)

# ---------------------------------------------------------------------------
# CHECKLIST TAB
# ---------------------------------------------------------------------------

with tab_checklist:
    if not st.session_state.responses:
        st.warning("No checklist loaded yet. Select one in the sidebar or draft one on the Agentic AI tab.")
    else:
        col_a, col_b = st.columns([3, 1])
        with col_a:
            filter_status = st.multiselect("Filter by status", STATUS_OPTIONS, default=[])
        with col_b:
            if st.button("💾 Save progress", use_container_width=True, type="primary"):
                if not cloud_persistence_enabled():
                    st.error("Cloud sync isn't configured. Add [gsheets] and [gcp_service_account] to secrets to save centrally.")
                elif not st.session_state.client_name or not st.session_state.technology:
                    st.error("Set a client name and technology first.")
                else:
                    save_to_cloud(st.session_state.client_name, st.session_state.technology, st.session_state.responses, st.session_state.reviewer)
                    st.success("Saved to the shared workspace.")

        by_category = {}
        for item_id, data in st.session_state.responses.items():
            by_category.setdefault(data.get("category", "General"), []).append((item_id, data))

        for category, items in sorted(by_category.items()):
            st.markdown(f"#### {category}")
            for item_id, data in sorted(items):
                if filter_status and data.get("status", "Not Reviewed") not in filter_status:
                    continue
                sev = data.get("severity", "Low")
                with st.expander(f"**{item_id}** — {data.get('control', '')}  ·  {sev}"):
                    st.markdown(f"**Reference:** {data.get('reference') or '—'}")
                    if data.get("audit_step"):
                        st.markdown(f'<div class="audit-step">{data["audit_step"]}</div>', unsafe_allow_html=True)

                    c1, c2 = st.columns(2)
                    with c1:
                        status_idx = STATUS_OPTIONS.index(data.get("status", "Not Reviewed"))
                        new_status = st.selectbox("Status", STATUS_OPTIONS, index=status_idx, key=f"status_{item_id}")
                    with c2:
                        assignee_options = [""] + TEAM_MEMBERS
                        current_assignee = data.get("assigned_to", "") or ""
                        assignee_idx = assignee_options.index(current_assignee) if current_assignee in assignee_options else 0
                        new_assignee = st.selectbox("Assigned to", assignee_options, index=assignee_idx, key=f"assignee_{item_id}")

                    new_notes = st.text_area("Notes", value=data.get("notes", ""), key=f"notes_{item_id}", height=80)

                    if new_status != data.get("status") or new_notes != data.get("notes") or new_assignee != data.get("assigned_to"):
                        data["status"] = new_status
                        data["notes"] = new_notes
                        data["assigned_to"] = new_assignee
                        data["last_updated_by"] = st.session_state.reviewer
                        data["last_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

# ---------------------------------------------------------------------------
# AGENTIC AI TAB
# ---------------------------------------------------------------------------

with tab_agent:
    if not ai_enabled():
        st.warning("AI agent isn't configured. Add a free token under `[huggingface]` in Streamlit secrets to enable this tab (get one free at huggingface.co/settings/tokens).")
    else:
        st.markdown("#### 🤖 Auto-draft a checklist")
        st.caption("Give the agent a technology name and it drafts, classifies, and saves a full checklist in one pass — no further prompting needed.")
        draft_tech = st.text_input("Technology to draft", value=st.session_state.technology, key="draft_tech")
        draft_context = st.text_area(
            "Optional context for the agent (client environment, prior findings, scope notes)",
            key="draft_context", height=80,
        )
        draft_count = st.slider("Number of controls to draft", 10, 40, 20, key="draft_count")

        if st.button("🤖 Auto-Draft Checklist", type="primary"):
            if not draft_tech:
                st.error("Enter a technology name first.")
            else:
                with st.spinner("Agent is drafting and classifying controls..."):
                    items, error = agentic_draft_checklist(draft_tech, draft_context, draft_count)
                if error:
                    st.error(error)
                else:
                    st.session_state.technology = draft_tech
                    st.session_state.responses = items_to_responses(items)
                    st.session_state.exec_summary = ""
                    if cloud_persistence_enabled():
                        save_checklist_to_library(
                            draft_tech,
                            [(it["item_id"], it["category"], it["control"], it["reference"], it["audit_step"]) for it in items],
                            source="AI-drafted",
                            actor=st.session_state.reviewer,
                        )
                    st.success(f"Drafted {len(items)} controls for {draft_tech} and loaded them into the Checklist tab.")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 🛠️ Auto-remediate open findings")
        st.caption("Sweeps every Non-Compliant control in one batched call and drafts a remediation step into its notes.")
        if not st.session_state.responses:
            st.info("Load or draft a checklist first.")
        elif st.button("🛠️ Auto-Remediate Non-Compliant Items"):
            with st.spinner("Agent is drafting remediation steps..."):
                updated, error = agentic_remediation_sweep(st.session_state.technology, st.session_state.responses)
            if error:
                if "No Non-Compliant" in error:
                    st.info(error)
                else:
                    st.error(error)
            else:
                st.session_state.responses = updated
                st.success("Remediation notes drafted for all open findings.")
                st.rerun()

        st.markdown("---")
        st.markdown("#### 📝 Generate executive summary")
        if not st.session_state.responses:
            st.info("Load or draft a checklist first.")
        else:
            if st.button("📝 Generate Executive Summary"):
                totals = compute_totals(st.session_state.responses)
                open_items = [
                    {"Item": iid, "Severity": d.get("severity"), "Control": d.get("control")}
                    for iid, d in st.session_state.responses.items() if d.get("status") == "Non-Compliant"
                ]
                with st.spinner("Agent is writing the summary..."):
                    summary = agentic_executive_summary(
                        st.session_state.client_name or "Client", st.session_state.technology,
                        totals["weighted_pct"], totals, open_items,
                    )
                st.session_state.exec_summary = summary
                st.rerun()

            if st.session_state.exec_summary:
                st.markdown("**Current executive summary:**")
                st.info(st.session_state.exec_summary)

# ---------------------------------------------------------------------------
# DASHBOARD TAB
# ---------------------------------------------------------------------------

with tab_dashboard:
    if not st.session_state.responses:
        st.warning("No checklist loaded yet.")
    else:
        totals = compute_totals(st.session_state.responses)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Risk-Weighted Compliance", f"{totals['weighted_pct']}%")
        c2.metric("Raw Compliance", f"{totals['raw_pct']}%")
        c3.metric("Non-Compliant", totals["noncompliant"])
        c4.metric("Not Reviewed", totals["not_reviewed"])

        col_a, col_b = st.columns(2)
        with col_a:
            status_counts = pd.Series([d.get("status", "Not Reviewed") for d in st.session_state.responses.values()]).value_counts()
            fig = px.pie(
                names=status_counts.index, values=status_counts.values, title="Controls by Status",
                color=status_counts.index, color_discrete_map=STATUS_COLORS, hole=0.45,
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#cbd5e1")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            sev_counts = pd.Series([d.get("severity", "Low") for d in st.session_state.responses.values()]).value_counts()
            fig2 = px.bar(x=sev_counts.index, y=sev_counts.values, title="Controls by Severity", labels={"x": "Severity", "y": "Count"})
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#cbd5e1")
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("#### Open findings")
        open_df = pd.DataFrame([
            {"Item": iid, "Severity": d.get("severity"), "Control": d.get("control"), "Owner": d.get("assigned_to") or "Unassigned"}
            for iid, d in st.session_state.responses.items() if d.get("status") == "Non-Compliant"
        ])
        if open_df.empty:
            st.success("No open Non-Compliant findings.")
        else:
            sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            open_df["_sort"] = open_df["Severity"].map(sev_order).fillna(4)
            st.dataframe(open_df.sort_values("_sort").drop(columns="_sort"), use_container_width=True, hide_index=True)

        if cloud_persistence_enabled() and st.session_state.client_name:
            st.markdown("#### Other engagements for this client")
            rollup = list_client_engagements(st.session_state.client_name)
            if rollup:
                st.dataframe(pd.DataFrame(rollup), use_container_width=True, hide_index=True)
            else:
                st.caption("No other saved engagements found for this client.")

# ---------------------------------------------------------------------------
# ACTIVITY LOG TAB
# ---------------------------------------------------------------------------

with tab_log:
    if not cloud_persistence_enabled():
        st.info("Cloud sync isn't configured, so there's no shared activity log to show.")
    else:
        log = fetch_activity_log()
        if not log:
            st.caption("No activity recorded yet.")
        else:
            st.dataframe(pd.DataFrame(log), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# EXPORT TAB
# ---------------------------------------------------------------------------

with tab_export:
    if not st.session_state.responses:
        st.warning("No checklist loaded yet.")
    elif not DOCX_AVAILABLE:
        st.error("python-docx isn't installed, so Word export is unavailable.")
    else:
        totals = compute_totals(st.session_state.responses)
        open_items = [
            {
                "Item": iid, "Severity": d.get("severity"), "Control": d.get("control"),
                "Audit Step": d.get("audit_step"), "Notes": d.get("notes"), "Assigned": d.get("assigned_to"),
            }
            for iid, d in st.session_state.responses.items() if d.get("status") == "Non-Compliant"
        ]
        docx_totals = {
            "total": totals["total"], "compliant": totals["compliant"], "noncompliant": totals["noncompliant"],
            "compensating": totals["compensating"], "not_reviewed": totals["not_reviewed"],
        }
        if st.button("Generate Word Report", type="primary"):
            report_bytes = build_docx_report(
                st.session_state.client_name or "Client", st.session_state.technology, st.session_state.reviewer,
                totals["weighted_pct"], totals["raw_pct"], docx_totals, open_items,
                st.session_state.exec_summary, st.session_state.responses,
            )
            safe_client = (st.session_state.client_name or "client").replace(" ", "_")
            safe_tech = (st.session_state.technology or "technology").replace(" ", "_")
            st.download_button(
                "⬇️ Download Report (.docx)", data=report_bytes,
                file_name=f"{safe_client}_{safe_tech}_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
