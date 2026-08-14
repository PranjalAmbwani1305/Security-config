"""
Security Configuration & CIS Benchmark Compliance Tool
--------------------------------------------------------
A Streamlit app that lets a consultant/auditor walk a client through a
hardening checklist for a chosen technology (based on CIS Benchmark
categories and general security best practice where a formal CIS
benchmark doesn't apply), record compliance status + evidence/notes per
item, and view a live compliance dashboard.

Run with:
    pip install streamlit pandas plotly gspread google-auth
    streamlit run security_config_dashboard.py

Cloud persistence (optional):
    Set up a Google Sheet + service account and add its credentials to
    Streamlit secrets (see README.md -> "Cloud persistence setup") to get
    automatic save/load per client that survives app restarts on Streamlit
    Community Cloud. Without secrets configured, the app still works fully
    using the CSV export/import already built in.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

SHEETS_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource(show_spinner=False)
def get_gsheet_client():
    """Build an authorized gspread client from Streamlit secrets, if configured."""
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
    # Sheet tab names are capped at 100 chars and can't contain some symbols.
    raw = f"{client_name}__{technology}".strip() or "untitled"
    safe = "".join(c for c in raw if c.isalnum() or c in ("_", "-", " "))
    return safe[:95]


def save_to_cloud(client_name: str, technology: str, responses: dict) -> None:
    gc = get_gsheet_client()
    if gc is None:
        return
    sh = gc.open_by_key(st.secrets["gsheets"]["sheet_id"])
    tab_name = _sheet_tab_name(client_name, technology)
    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab_name, rows=200, cols=10)

    rows = [["item_id", "category", "control", "reference", "status", "notes", "reviewer", "date"]]
    for item_id, data in responses.items():
        rows.append([
            item_id,
            data.get("category", ""),
            data.get("control", ""),
            data.get("reference", ""),
            data.get("status", ""),
            data.get("notes", ""),
            data.get("reviewer", ""),
            data.get("date", ""),
        ])
    ws.update(rows)


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
            "reviewer": row.get("reviewer", ""),
            "date": row.get("date", ""),
        }
    return loaded

st.set_page_config(page_title="Security Config & CIS Compliance Tool", layout="wide")

# ---------------------------------------------------------------------------
# 1. CHECKLIST DATA
# Each technology maps to a list of controls: id, category, control text,
# guidance, and a rough CIS Benchmark cross-reference (where a formal CIS
# Benchmark exists for that technology). For technologies without a
# published CIS Benchmark, the list is a generic best-practice checklist
# built from common hardening/compliance frameworks (NIST, ISO 27001,
# vendor hardening guides) rather than a specific named source.
# ---------------------------------------------------------------------------

CHECKLISTS = {
    "Linux Server (CIS Benchmark based)": [
        ("L-1", "Initial Setup & Filesystem", "Separate partitions used for /tmp, /var, /var/log, /var/log/audit, /home", "CIS 1.1.x"),
        ("L-2", "Initial Setup & Filesystem", "Unused filesystems (cramfs, freevxfs, squashfs, udf) are disabled", "CIS 1.1.1.x"),
        ("L-3", "Initial Setup & Filesystem", "GPG keys are configured for package repositories", "CIS 1.2.x"),
        ("L-4", "Initial Setup & Filesystem", "AppArmor/SELinux is installed, enabled and enforcing", "CIS 1.6.x"),
        ("L-5", "Initial Setup & Filesystem", "Bootloader password is set and permissions restricted", "CIS 1.4.x"),
        ("L-6", "Services", "Unnecessary services (telnet, rsh, ypserv, tftp, xinetd) are removed/disabled", "CIS 2.1-2.2"),
        ("L-7", "Services", "Time synchronization (chrony/ntp) is enabled and configured", "CIS 2.1.1"),
        ("L-8", "Network Configuration", "IP forwarding is disabled unless the host is a router", "CIS 3.1.x"),
        ("L-9", "Network Configuration", "ICMP redirects, source routing are disabled", "CIS 3.2.x"),
        ("L-10", "Network Configuration", "Host-based firewall (nftables/iptables/firewalld) is enabled with default-deny", "CIS 3.5.x"),
        ("L-11", "Logging & Auditing", "auditd is installed, enabled, and logs are retained per policy", "CIS 4.1.x"),
        ("L-12", "Logging & Auditing", "rsyslog/journald forwards logs to a central log server", "CIS 4.2.x"),
        ("L-13", "Logging & Auditing", "Logrotate is configured to prevent disk exhaustion", "CIS 4.3"),
        ("L-14", "Access, Authentication & Authorization", "Password complexity, history, and lockout policy enforced via pam_pwquality/faillock", "CIS 5.3.x"),
        ("L-15", "Access, Authentication & Authorization", "SSH root login disabled, protocol 2 only, strong ciphers/MACs only", "CIS 5.2.x"),
        ("L-16", "Access, Authentication & Authorization", "sudo requires password and logs all sudo activity", "CIS 5.4.x"),
        ("L-17", "Access, Authentication & Authorization", "Empty passwords, unused/system accounts are locked or removed", "CIS 5.5.x"),
        ("L-18", "System Maintenance", "World-writable files and unowned files/directories are found and remediated", "CIS 6.1.x"),
        ("L-19", "System Maintenance", "Permissions on /etc/passwd, /etc/shadow, /etc/gshadow are correctly restricted", "CIS 6.1.x"),
        ("L-20", "System Maintenance", "OS and package patching cadence is documented and current", "CIS 1.9 / general"),
    ],
    "Windows Server / Active Directory (CIS Benchmark based)": [
        ("W-1", "Account Policies", "Password policy meets length/complexity/history/max-age requirements", "CIS 1.1.x"),
        ("W-2", "Account Policies", "Account lockout threshold, duration and reset counter are configured", "CIS 1.2.x"),
        ("W-3", "Local Policies / Audit Policy", "Advanced audit policy is enabled for logon, account management, policy change", "CIS 17.x"),
        ("W-4", "Local Policies / Audit Policy", "User rights assignment restricts 'Log on locally', 'Access this computer from the network' etc.", "CIS 2.2.x"),
        ("W-5", "Local Policies / Audit Policy", "Security options: LM hash storage disabled, NTLMv2 only, anonymous enumeration disabled", "CIS 2.3.x"),
        ("W-6", "Windows Firewall", "Domain/Private/Public firewall profiles are all enabled with logging on", "CIS 9.1-9.3"),
        ("W-7", "Network", "SMBv1 is disabled; SMB signing is required", "CIS 18.3.x"),
        ("W-8", "System Services", "Unnecessary services (Telnet, Remote Registry, SNMP if unused) are disabled", "CIS 5.x"),
        ("W-9", "Administrative Templates", "LAPS or equivalent local admin password rotation is in place", "CIS/MS best practice"),
        ("W-10", "Administrative Templates", "Windows Update is configured for timely patch deployment", "CIS 18.9.x"),
        ("W-11", "Administrative Templates", "PowerShell logging (module, script block, transcription) is enabled", "CIS 18.9.100.x"),
        ("W-12", "Active Directory", "Privileged groups (Domain Admins, Enterprise Admins) are reviewed and minimized", "AD hardening best practice"),
        ("W-13", "Active Directory", "Kerberos delegation is restricted (no unconstrained delegation on non-critical hosts)", "AD hardening best practice"),
        ("W-14", "Active Directory", "Tiered administration model separates workstation/server/DC admin credentials", "AD hardening best practice"),
        ("W-15", "Active Directory", "AD backups (including SYSVOL, NTDS.dit) are taken and tested regularly", "General best practice"),
        ("W-16", "Endpoint Protection", "Microsoft Defender / EDR is installed, updated and reporting centrally", "CIS 18.9.x"),
        ("W-17", "BitLocker / Data Protection", "BitLocker (or equivalent) full-disk encryption is enabled on all endpoints/servers with sensitive data", "CIS 18.9.x"),
    ],
    "Cloud (AWS / Azure / GCP - CIS Benchmark based)": [
        ("C-1", "Identity & Access Management", "Root/global admin account has MFA enabled and is not used for daily operations", "CIS 1.x"),
        ("C-2", "Identity & Access Management", "IAM policies follow least privilege; no wildcard (*:*) admin policies attached broadly", "CIS 1.x"),
        ("C-3", "Identity & Access Management", "Access keys/service credentials are rotated and unused ones are disabled", "CIS 1.x"),
        ("C-4", "Identity & Access Management", "Single sign-on / centralized identity provider is used instead of per-service local accounts", "General best practice"),
        ("C-5", "Logging & Monitoring", "Account-level audit logging (CloudTrail/Activity Log/Cloud Audit Logs) is enabled in all regions", "CIS 2.x/3.x"),
        ("C-6", "Logging & Monitoring", "Logs are shipped to a centralized, tamper-evident, access-controlled log store", "CIS 3.x"),
        ("C-7", "Logging & Monitoring", "Alerting is configured for root usage, IAM policy changes, and security group changes", "CIS 4.x"),
        ("C-8", "Networking", "Default security group / NSG denies all inbound traffic by default", "CIS 5.x"),
        ("C-9", "Networking", "No security group/NSG rule allows unrestricted inbound access (0.0.0.0/0) on admin ports (22/3389)", "CIS 5.x"),
        ("C-10", "Networking", "VPC/VNet flow logs are enabled", "CIS 3.x"),
        ("C-11", "Storage & Data Protection", "Object storage buckets/containers are not publicly readable/writable unless explicitly required", "CIS 2.x"),
        ("C-12", "Storage & Data Protection", "Data at rest is encrypted using platform-managed or customer-managed keys", "CIS 2.x"),
        ("C-13", "Storage & Data Protection", "Data in transit is enforced over TLS for all managed services", "CIS 2.x"),
        ("C-14", "Monitoring & Response", "A cloud security posture / config-drift tool (Security Hub, Defender for Cloud, Security Command Center) is enabled", "General best practice"),
        ("C-15", "Governance", "Budget/cost anomaly alerts and resource tagging standards are enforced", "General best practice"),
    ],
    "Containers - Docker / Kubernetes (CIS Benchmark based)": [
        ("K-1", "Host Configuration", "Container runtime (Docker/containerd) is kept patched to a supported version", "CIS Docker 1.x"),
        ("K-2", "Host Configuration", "Docker daemon socket is not exposed over an unauthenticated network port", "CIS Docker 2.x"),
        ("K-3", "Image & Build", "Images are built from minimal, trusted base images and scanned for CVEs before deployment", "CIS Docker 4.x"),
        ("K-4", "Image & Build", "Containers do not run as root unless explicitly required", "CIS Docker 4.1"),
        ("K-5", "Image & Build", "Secrets are not baked into images or environment variables in plaintext", "CIS Docker 5.x"),
        ("K-6", "Runtime", "Containers run with a read-only root filesystem where possible", "CIS Docker 5.x"),
        ("K-7", "Runtime", "Resource limits (CPU/memory) are set to prevent noisy-neighbor/DoS", "CIS Docker 5.x"),
        ("K-8", "Kubernetes - Control Plane", "kube-apiserver anonymous auth is disabled and RBAC authorization mode is enforced", "CIS Kubernetes 1.2.x"),
        ("K-9", "Kubernetes - Control Plane", "etcd is encrypted at rest and access is restricted to control-plane nodes only", "CIS Kubernetes 2.x"),
        ("K-10", "Kubernetes - Control Plane", "Audit logging is enabled on the API server", "CIS Kubernetes 1.2.x"),
        ("K-11", "Kubernetes - Workloads", "NetworkPolicies restrict pod-to-pod traffic to what's required", "CIS Kubernetes 5.3.x"),
        ("K-12", "Kubernetes - Workloads", "PodSecurity admission (or equivalent) blocks privileged/hostPath/hostNetwork pods by default", "CIS Kubernetes 5.2.x"),
        ("K-13", "Kubernetes - Workloads", "Namespaces and RBAC RoleBindings scope access per team/tenant", "CIS Kubernetes 5.1.x"),
        ("K-14", "Secrets Management", "Kubernetes Secrets are encrypted at rest or an external secrets manager (Vault, KMS) is used", "CIS Kubernetes 2.x / general"),
        ("K-15", "Supply Chain", "Only images from an approved, scanned registry can be deployed (admission control/policy)", "General best practice"),
    ],
    "Web Application / API (generic - no single CIS benchmark)": [
        ("A-1", "Authentication & Session", "MFA is available/enforced for privileged and customer-facing accounts", "OWASP ASVS aligned"),
        ("A-2", "Authentication & Session", "Session tokens are random, short-lived, and invalidated on logout/password change", "OWASP ASVS aligned"),
        ("A-3", "Input Handling", "All user input is validated/sanitized server-side; parameterized queries used (no raw SQL concatenation)", "OWASP Top 10 aligned"),
        ("A-4", "Access Control", "Authorization checks are enforced server-side on every request, not just in the UI", "OWASP Top 10 aligned"),
        ("A-5", "Transport & Headers", "TLS 1.2+ enforced; HSTS, CSP, X-Content-Type-Options headers set", "OWASP Secure Headers"),
        ("A-6", "Secrets & Config", "API keys/secrets are stored in a vault/secret manager, not in source control or client-side code", "General best practice"),
        ("A-7", "Logging & Monitoring", "Security-relevant events (auth failures, privilege changes) are logged without leaking sensitive data", "OWASP logging cheat sheet aligned"),
        ("A-8", "Dependency Management", "Third-party libraries/dependencies are scanned for known vulnerabilities on a regular cadence", "General best practice"),
        ("A-9", "Rate Limiting & Abuse", "Rate limiting / throttling is applied to authentication and other sensitive endpoints", "General best practice"),
        ("A-10", "Data Protection", "PII/sensitive fields are encrypted at rest and masked in logs/non-prod environments", "General best practice"),
    ],
}

STATUS_OPTIONS = ["Not Reviewed", "Compliant", "Non-Compliant", "Compensating Control", "Not Applicable"]
STATUS_COLORS = {
    "Compliant": "#2ecc71",
    "Non-Compliant": "#e74c3c",
    "Compensating Control": "#f39c12",
    "Not Applicable": "#95a5a6",
    "Not Reviewed": "#bdc3c7",
}

# ---------------------------------------------------------------------------
# 2. SESSION STATE
# ---------------------------------------------------------------------------

if "responses" not in st.session_state:
    # key: item_id -> dict(status, notes, reviewer, date)
    st.session_state.responses = {}

if "client_name" not in st.session_state:
    st.session_state.client_name = ""

# ---------------------------------------------------------------------------
# 3. SIDEBAR - client & technology setup, import/export
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Engagement Setup")
st.session_state.client_name = st.sidebar.text_input("Client / Engagement name", value=st.session_state.client_name)
reviewer = st.sidebar.text_input("Reviewer name", value="")
tech = st.sidebar.selectbox("Technology to assess", list(CHECKLISTS.keys()))

st.sidebar.markdown("---")
st.sidebar.subheader("💾 Save / Load Progress")

if cloud_persistence_enabled():
    st.sidebar.success("☁️ Cloud persistence connected")
    cc1, cc2 = st.sidebar.columns(2)
    if cc1.button("☁️ Save to cloud", use_container_width=True):
        save_to_cloud(st.session_state.client_name, tech, st.session_state.responses)
        st.sidebar.success("Saved.")
    if cc2.button("☁️ Load from cloud", use_container_width=True):
        loaded = load_from_cloud(st.session_state.client_name, tech)
        if loaded:
            st.session_state.responses.update(loaded)
            st.sidebar.success(f"Loaded {len(loaded)} items.")
        else:
            st.sidebar.warning("No saved data found for this client/technology.")
else:
    st.sidebar.caption(
        "☁️ Cloud persistence not configured — using manual CSV export/import "
        "below. See README.md to add Google Sheets persistence."
    )

# Export
if st.session_state.responses:
    export_rows = []
    for item_id, data in st.session_state.responses.items():
        export_rows.append({"item_id": item_id, **data})
    export_df = pd.DataFrame(export_rows)
    csv_buf = io.StringIO()
    export_df.to_csv(csv_buf, index=False)
    st.sidebar.download_button(
        "⬇️ Export progress (CSV)",
        data=csv_buf.getvalue(),
        file_name=f"{(st.session_state.client_name or 'client').replace(' ', '_')}_compliance_progress.csv",
        mime="text/csv",
    )

uploaded = st.sidebar.file_uploader("⬆️ Resume from CSV", type=["csv"])
if uploaded is not None:
    resume_df = pd.read_csv(uploaded)
    for _, row in resume_df.iterrows():
        st.session_state.responses[row["item_id"]] = {
            "status": row.get("status", "Not Reviewed"),
            "notes": row.get("notes", "") if pd.notna(row.get("notes", "")) else "",
            "reviewer": row.get("reviewer", "") if pd.notna(row.get("reviewer", "")) else "",
            "date": row.get("date", "") if pd.notna(row.get("date", "")) else "",
            "category": row.get("category", ""),
            "control": row.get("control", ""),
            "reference": row.get("reference", ""),
        }
    st.sidebar.success(f"Loaded {len(resume_df)} saved responses.")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Checklists are built from CIS Benchmark categories where a published "
    "benchmark exists for the technology. Where no formal CIS Benchmark "
    "applies (e.g. custom web apps), a generic best-practice checklist is "
    "used instead. Always validate against the current official benchmark "
    "PDF for the exact build/version in scope before sign-off."
)

# ---------------------------------------------------------------------------
# 4. MAIN - Tabs: Checklist / Dashboard
# ---------------------------------------------------------------------------

st.title("🛡️ Security Configuration & CIS Compliance Tool")
st.caption(f"Client: **{st.session_state.client_name or '—'}**  |  Technology: **{tech}**")

tab_checklist, tab_dashboard = st.tabs(["📋 Checklist", "📊 Compliance Dashboard"])

items = CHECKLISTS[tech]
categories = sorted(set(c for _, c, _, _ in items))

with tab_checklist:
    st.subheader("Configuration Checklist")
    filter_status = st.multiselect("Filter by status", STATUS_OPTIONS, default=[])
    search = st.text_input("Search controls", "")

    for cat in categories:
        cat_items = [it for it in items if it[1] == cat]
        if search:
            cat_items = [it for it in cat_items if search.lower() in it[2].lower()]
        if not cat_items:
            continue

        with st.expander(f"**{cat}**  ({len(cat_items)} controls)", expanded=False):
            for item_id, category, control, ref in cat_items:
                existing = st.session_state.responses.get(item_id, {})
                current_status = existing.get("status", "Not Reviewed")
                if filter_status and current_status not in filter_status:
                    continue

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{item_id}** — {control}")
                    st.caption(f"Reference: {ref}")
                with col2:
                    status = st.selectbox(
                        "Status", STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(current_status),
                        key=f"status_{item_id}",
                        label_visibility="collapsed",
                    )
                notes = st.text_area(
                    "Evidence / notes", value=existing.get("notes", ""),
                    key=f"notes_{item_id}", height=60,
                    placeholder="Evidence collected, deviation justification, remediation owner/date...",
                )

                st.session_state.responses[item_id] = {
                    "status": status,
                    "notes": notes,
                    "category": category,
                    "control": control,
                    "reference": ref,
                    "reviewer": reviewer,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }
                st.markdown("---")

with tab_dashboard:
    st.subheader("Compliance Dashboard")

    all_ids = [it[0] for it in items]
    recorded = {i: st.session_state.responses.get(i, {"status": "Not Reviewed", "category": next(c for iid, c, _, _ in items if iid == i)}) for i in all_ids}
    df = pd.DataFrame([
        {"item_id": i, "category": recorded[i].get("category", ""), "status": recorded[i].get("status", "Not Reviewed")}
        for i in all_ids
    ])

    total = len(df)
    compliant = (df["status"] == "Compliant").sum()
    noncompliant = (df["status"] == "Non-Compliant").sum()
    compensating = (df["status"] == "Compensating Control").sum()
    na = (df["status"] == "Not Applicable").sum()
    not_reviewed = (df["status"] == "Not Reviewed").sum()
    applicable = total - na
    compliance_pct = round(((compliant + compensating) / applicable) * 100, 1) if applicable else 0.0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Overall Compliance", f"{compliance_pct}%")
    m2.metric("Compliant", int(compliant))
    m3.metric("Non-Compliant", int(noncompliant))
    m4.metric("Compensating Control", int(compensating))
    m5.metric("Not Reviewed", int(not_reviewed))

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Status breakdown**")
        status_counts = df["status"].value_counts().reindex(STATUS_OPTIONS, fill_value=0).reset_index()
        status_counts.columns = ["status", "count"]
        fig_pie = px.pie(
            status_counts, names="status", values="count",
            color="status", color_discrete_map=STATUS_COLORS, hole=0.45,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.markdown("**Compliance % by category**")
        cat_stats = []
        for cat in categories:
            cat_df = df[df["category"] == cat]
            cat_applicable = cat_df[cat_df["status"] != "Not Applicable"]
            cat_good = cat_applicable[cat_applicable["status"].isin(["Compliant", "Compensating Control"])]
            pct = round((len(cat_good) / len(cat_applicable)) * 100, 1) if len(cat_applicable) else 0.0
            cat_stats.append({"category": cat, "compliance_pct": pct})
        cat_df_stats = pd.DataFrame(cat_stats).sort_values("compliance_pct")
        fig_bar = px.bar(
            cat_df_stats, x="compliance_pct", y="category", orientation="h",
            range_x=[0, 100], text="compliance_pct",
            color="compliance_pct", color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
        )
        fig_bar.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_bar.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")
    st.markdown("**⚠️ Open Non-Compliant Items (remediation tracker)**")
    open_items = []
    for i in all_ids:
        r = st.session_state.responses.get(i)
        if r and r.get("status") == "Non-Compliant":
            open_items.append({
                "Item": i, "Category": r.get("category"), "Control": r.get("control"),
                "Notes": r.get("notes"), "Reference": r.get("reference"),
            })
    if open_items:
        st.dataframe(pd.DataFrame(open_items), use_container_width=True, hide_index=True)
    else:
        st.success("No open non-compliant items recorded yet for this technology.")

    st.markdown("---")
    if st.session_state.responses:
        full_export = []
        for item_id, data in st.session_state.responses.items():
            full_export.append({"item_id": item_id, **data})
        full_df = pd.DataFrame(full_export)
        csv_buf2 = io.StringIO()
        full_df.to_csv(csv_buf2, index=False)
        st.download_button(
            "⬇️ Download full compliance report (CSV)",
            data=csv_buf2.getvalue(),
            file_name=f"{(st.session_state.client_name or 'client').replace(' ', '_')}_{tech.split(' ')[0]}_compliance_report.csv",
            mime="text/csv",
        )
