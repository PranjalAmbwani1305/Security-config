"""
Sentinel GRC - Streamlit frontend.

This is a pure frontend: every piece of business logic (checklist content,
compliance scoring, risk scoring, storage) lives in the existing FastAPI
backend under backend/app/*. This file only renders UI and calls that API
through api_client.py. Nothing in backend/ is imported, read from, or
changed by this app.

Run the backend first (from the repo root):
    uvicorn backend.app.main:app --reload

Then run this app (from the repo root):
    streamlit run frontend/app.py
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import api_client as api

STATUS_OPTIONS = [
    "Not Reviewed",
    "Compliant",
    "Non-Compliant",
    "Compensating Control",
    "Not Applicable",
]
SEVERITY_OPTIONS = ["Low", "Medium", "High", "Critical"]
FINDING_STATUS_OPTIONS = ["Open", "Remediated", "Risk Accepted", "False Positive"]
TREATMENT_OPTIONS = ["Mitigate", "Accept", "Transfer", "Avoid"]
RISK_STATUS_OPTIONS = ["Open", "Monitoring", "Closed"]
BUILT_IN_TECHNOLOGIES = ["linux", "windows"]  # technologies with a static, submittable checklist

st.set_page_config(page_title="Sentinel GRC", page_icon="\U0001F6E1\uFE0F", layout="wide")


# ---------------------------------------------------------------------------
# Session state / small helpers
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "base_url": "http://localhost:8000",
        "engagement_id": None,
        "client_name": None,
        "technology": None,
        "reviewer": None,
        "last_assessment_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _has_engagement() -> bool:
    return bool(st.session_state.get("engagement_id"))


def _engagement_banner() -> None:
    st.info(
        "No engagement selected yet. Create or load one from the **sidebar** first.",
        icon="\u2139\uFE0F",
    )


def _is_built_in(technology: str | None) -> bool:
    return (technology or "").lower() in BUILT_IN_TECHNOLOGIES


# ---------------------------------------------------------------------------
# Sidebar: backend connection + engagement management
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    st.sidebar.title("\U0001F6E1\uFE0F Sentinel GRC")

    st.sidebar.subheader("Backend connection")
    st.session_state["base_url"] = st.sidebar.text_input(
        "Backend URL", value=st.session_state["base_url"]
    )
    if st.sidebar.button("Check connection"):
        try:
            health = api.health_check(st.session_state["base_url"])
            st.sidebar.success(f"Connected \u2014 {health.get('service', 'backend')} is up")
        except api.ApiError as exc:
            st.sidebar.error(f"Can't reach backend: {exc}")

    st.sidebar.divider()
    st.sidebar.subheader("Engagement")

    mode = st.sidebar.radio("Engagement", ["Start new", "Load existing"], label_visibility="collapsed")

    if mode == "Start new":
        with st.sidebar.form("new_engagement_form"):
            client_name = st.text_input("Client name")
            technology = st.text_input(
                "Technology", placeholder="linux, windows, aws, custom web app..."
            )
            reviewer = st.text_input("Reviewer")
            suggested_id = (
                f"{(client_name or 'client').strip().lower().replace(' ', '-')}"
                f"-{(technology or 'tech').strip().lower().replace(' ', '-')}"
                f"-{date.today().isoformat()}"
            )
            engagement_id = st.text_input("Engagement ID", value=suggested_id)
            submitted = st.form_submit_button("Create engagement")

        if submitted:
            if not (client_name and technology and reviewer and engagement_id):
                st.sidebar.warning("Fill in all fields first.")
            else:
                try:
                    api.create_engagement(
                        st.session_state["base_url"], engagement_id, client_name, technology, reviewer
                    )
                    st.session_state.update(
                        {
                            "engagement_id": engagement_id,
                            "client_name": client_name,
                            "technology": technology,
                            "reviewer": reviewer,
                            "last_assessment_result": None,
                        }
                    )
                    st.sidebar.success(f"Engagement '{engagement_id}' created and loaded.")
                except api.ApiError as exc:
                    st.sidebar.error(f"Couldn't create engagement: {exc}")
    else:
        if st.sidebar.button("Refresh list"):
            st.session_state.pop("_engagement_options", None)

        try:
            data = api.list_engagements(st.session_state["base_url"])
            engagements = data.get("engagements", [])
        except api.ApiError as exc:
            engagements = []
            st.sidebar.error(f"Couldn't load engagements: {exc}")

        if engagements:
            options = {e["engagement_id"]: e for e in engagements}
            chosen = st.sidebar.selectbox("Existing engagements", list(options.keys()))
            if st.sidebar.button("Load engagement"):
                picked = options[chosen]
                st.session_state.update(
                    {
                        "engagement_id": picked["engagement_id"],
                        "client_name": picked["client_name"],
                        "technology": picked["technology"],
                        "reviewer": picked["reviewer"],
                        "last_assessment_result": None,
                    }
                )
                st.sidebar.success(f"Loaded '{picked['engagement_id']}'.")
        else:
            st.sidebar.caption("No engagements on the backend yet.")

    if _has_engagement():
        st.sidebar.divider()
        st.sidebar.caption("Current engagement")
        st.sidebar.markdown(
            f"**{st.session_state['engagement_id']}**  \n"
            f"Client: {st.session_state['client_name']}  \n"
            f"Technology: {st.session_state['technology']}  \n"
            f"Reviewer: {st.session_state['reviewer']}"
        )
        if not _is_built_in(st.session_state["technology"]):
            st.sidebar.warning(
                "This technology has no built-in CIS checklist, so the backend "
                "can only offer an AI-generated preview \u2014 assessments, evidence "
                "and findings can't be recorded for it yet.",
                icon="\u26A0\uFE0F",
            )


# ---------------------------------------------------------------------------
# Tab: Assessment
# ---------------------------------------------------------------------------

def render_assessment_tab() -> None:
    st.header("Checklist & Assessment")
    if not _has_engagement():
        _engagement_banner()
        return

    base_url = st.session_state["base_url"]
    technology = st.session_state["technology"]
    engagement_id = st.session_state["engagement_id"]
    built_in = _is_built_in(technology)

    try:
        if built_in:
            data = api.get_checklist(base_url, technology)
        else:
            data = api.generate_checklist(base_url, technology)
    except api.ApiError as exc:
        st.error(f"Couldn't load checklist: {exc}")
        return

    checklist = data.get("checklist", [])
    if not checklist:
        st.warning("No checklist items returned for this technology.")
        return

    if not built_in:
        st.caption("AI-generated preview \u2014 view only, can't be submitted as an assessment.")

    by_category: dict[str, list[dict]] = {}
    for item in checklist:
        by_category.setdefault(item["category"], []).append(item)

    for category, items in by_category.items():
        with st.expander(f"{category} ({len(items)})", expanded=True):
            for item in items:
                item_id = item["item_id"]
                cols = st.columns([3, 1, 2])
                cols[0].markdown(
                    f"**{item['control']}**  \n{item['audit_step']}  \n"
                    f"<span style='color:gray'>Ref: {item['reference']} \u00b7 {item_id}</span>",
                    unsafe_allow_html=True,
                )
                cols[1].selectbox(
                    "Status",
                    STATUS_OPTIONS,
                    key=f"status_{item_id}",
                    disabled=not built_in,
                    label_visibility="collapsed",
                )
                cols[2].text_area(
                    "Notes",
                    key=f"notes_{item_id}",
                    height=68,
                    disabled=not built_in,
                    label_visibility="collapsed",
                )

    if built_in:
        if st.button("Save assessment", type="primary"):
            results = [
                {
                    "item_id": item["item_id"],
                    "status": st.session_state.get(f"status_{item['item_id']}", "Not Reviewed"),
                    "notes": st.session_state.get(f"notes_{item['item_id']}", ""),
                }
                for item in checklist
            ]
            try:
                result = api.submit_assessment(base_url, engagement_id, results)
            except api.ApiError as exc:
                st.error(f"Couldn't submit assessment: {exc}")
                return

            if "compliance_percentage" not in result:
                st.error(result.get("message", "Submission failed."))
                return

            st.session_state["last_assessment_result"] = result
            st.success("Assessment saved.")
            m1, m2, m3 = st.columns(3)
            m1.metric("Compliance", f"{result['compliance_percentage']:.1f}%")
            m2.metric("Compliant controls", result["compliant_controls"])
            m3.metric("Non-compliant controls", result["non_compliant_controls"])


# ---------------------------------------------------------------------------
# Tab: Evidence
# ---------------------------------------------------------------------------

def render_evidence_tab() -> None:
    st.header("Evidence")
    if not _has_engagement():
        _engagement_banner()
        return

    base_url = st.session_state["base_url"]
    engagement_id = st.session_state["engagement_id"]
    technology = st.session_state["technology"]

    if not _is_built_in(technology):
        st.warning("Evidence can only be recorded for Linux or Windows engagements right now.")
        return

    try:
        checklist = api.get_checklist(base_url, technology).get("checklist", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load checklist: {exc}")
        return

    item_ids = [item["item_id"] for item in checklist]

    with st.form("evidence_form"):
        item_id = st.selectbox("Checklist item", item_ids)
        evidence_text = st.text_area("Evidence / notes")
        submitted = st.form_submit_button("Add evidence")

    if submitted:
        if not evidence_text:
            st.warning("Enter some evidence text first.")
        else:
            try:
                api.add_evidence(base_url, engagement_id, item_id, evidence_text)
                st.success("Evidence recorded.")
            except api.ApiError as exc:
                st.error(f"Couldn't record evidence: {exc}")

    st.subheader("Recorded evidence")
    try:
        evidence = api.get_evidence(base_url, engagement_id).get("evidence", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load evidence: {exc}")
        return

    if evidence:
        st.dataframe(pd.DataFrame(evidence), width="stretch", hide_index=True)
    else:
        st.caption("No evidence recorded yet.")


# ---------------------------------------------------------------------------
# Tab: Findings
# ---------------------------------------------------------------------------

def render_findings_tab() -> None:
    st.header("Findings")
    if not _has_engagement():
        _engagement_banner()
        return

    base_url = st.session_state["base_url"]
    engagement_id = st.session_state["engagement_id"]
    technology = st.session_state["technology"]

    if not _is_built_in(technology):
        st.warning("Findings can only be recorded for Linux or Windows engagements right now.")
        return

    try:
        checklist = api.get_checklist(base_url, technology).get("checklist", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load checklist: {exc}")
        return

    item_ids = [item["item_id"] for item in checklist]

    with st.form("finding_form"):
        finding_id = st.text_input("Finding ID", value=f"FIND-{uuid.uuid4().hex[:6].upper()}")
        item_id = st.selectbox("Checklist item (must already be assessed)", item_ids)
        title = st.text_input("Title")
        description = st.text_area("Description")
        severity = st.selectbox("Severity", SEVERITY_OPTIONS)
        recommendation = st.text_area("Recommendation")
        status = st.selectbox("Status", FINDING_STATUS_OPTIONS)
        submitted = st.form_submit_button("Create finding")

    if submitted:
        if not title:
            st.warning("Give the finding a title first.")
        else:
            try:
                result = api.create_finding(
                    base_url,
                    finding_id=finding_id,
                    engagement_id=engagement_id,
                    item_id=item_id,
                    title=title,
                    description=description,
                    severity=severity,
                    recommendation=recommendation,
                    status=status,
                )
                if "finding" in result:
                    st.success("Finding created.")
                else:
                    st.error(result.get("message", "Couldn't create finding."))
            except api.ApiError as exc:
                st.error(f"Couldn't create finding: {exc}")

    st.subheader("Findings on this engagement")
    try:
        findings = api.get_findings(base_url, engagement_id).get("findings", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load findings: {exc}")
        return

    if findings:
        st.dataframe(pd.DataFrame(findings), width="stretch", hide_index=True)
    else:
        st.caption("No findings yet.")


# ---------------------------------------------------------------------------
# Tab: Risk register
# ---------------------------------------------------------------------------

def render_risk_tab() -> None:
    st.header("Risk register")
    if not _has_engagement():
        _engagement_banner()
        return

    base_url = st.session_state["base_url"]
    engagement_id = st.session_state["engagement_id"]

    try:
        findings = api.get_findings(base_url, engagement_id).get("findings", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load findings: {exc}")
        return

    if not findings:
        st.info("Create a finding first \u2014 every risk has to reference one.")
        return

    finding_ids = [f["finding_id"] for f in findings]

    with st.form("risk_form"):
        risk_id = st.text_input("Risk ID", value=f"RISK-{uuid.uuid4().hex[:6].upper()}")
        finding_id = st.selectbox("Related finding", finding_ids)
        title = st.text_input("Title")
        col1, col2 = st.columns(2)
        likelihood = col1.slider("Likelihood", 1, 5, 3)
        impact = col2.slider("Impact", 1, 5, 3)
        treatment = st.selectbox("Treatment", TREATMENT_OPTIONS)
        owner = st.text_input("Owner")
        status = st.selectbox("Status", RISK_STATUS_OPTIONS)
        submitted = st.form_submit_button("Create risk")

    if submitted:
        if not (title and owner):
            st.warning("Give the risk a title and an owner first.")
        else:
            try:
                result = api.create_risk(
                    base_url,
                    risk_id=risk_id,
                    engagement_id=engagement_id,
                    finding_id=finding_id,
                    title=title,
                    likelihood=likelihood,
                    impact=impact,
                    treatment=treatment,
                    owner=owner,
                    status=status,
                )
                if "risk" in result:
                    r = result["risk"]
                    st.success(f"Risk created \u2014 score {r['risk_score']} ({r['risk_level']}).")
                else:
                    st.error(result.get("message", "Couldn't create risk."))
            except api.ApiError as exc:
                st.error(f"Couldn't create risk: {exc}")

    st.subheader("Risks on this engagement")
    try:
        risks = api.get_risks(base_url, engagement_id).get("risks", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load risks: {exc}")
        return

    if risks:
        st.dataframe(pd.DataFrame(risks), width="stretch", hide_index=True)
    else:
        st.caption("No risks yet.")


# ---------------------------------------------------------------------------
# Tab: Dashboard
# ---------------------------------------------------------------------------

def render_dashboard_tab() -> None:
    st.header("Compliance dashboard")
    if not _has_engagement():
        _engagement_banner()
        return

    base_url = st.session_state["base_url"]
    engagement_id = st.session_state["engagement_id"]

    last_result = st.session_state.get("last_assessment_result")
    if last_result:
        m1, m2, m3 = st.columns(3)
        m1.metric("Latest compliance", f"{last_result['compliance_percentage']:.1f}%")
        m2.metric("Compliant controls", last_result["compliant_controls"])
        m3.metric("Non-compliant controls", last_result["non_compliant_controls"])
    else:
        st.caption("Save an assessment on the Assessment tab to see a compliance score here.")

    try:
        assessments = api.get_assessments(base_url, engagement_id).get("assessments", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load assessments: {exc}")
        assessments = []

    col_left, col_right = st.columns(2)

    if assessments:
        latest = assessments[-1]
        status_counts = Counter(r["status"] for r in latest["results"])
        fig = px.pie(
            names=list(status_counts.keys()),
            values=list(status_counts.values()),
            title="Latest assessment \u2014 status breakdown",
        )
        col_left.plotly_chart(fig, width="stretch")
    else:
        col_left.caption("No assessments submitted yet.")

    try:
        findings = api.get_findings(base_url, engagement_id).get("findings", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load findings: {exc}")
        findings = []

    if findings:
        sev_counts = Counter(f["severity"] for f in findings)
        fig = px.bar(
            x=list(sev_counts.keys()),
            y=list(sev_counts.values()),
            labels={"x": "Severity", "y": "Findings"},
            title="Open findings by severity",
        )
        col_right.plotly_chart(fig, width="stretch")
    else:
        col_right.caption("No findings yet.")

    try:
        risks = api.get_risks(base_url, engagement_id).get("risks", [])
    except api.ApiError as exc:
        st.error(f"Couldn't load risks: {exc}")
        risks = []

    st.subheader("Risk register summary")
    if risks:
        risk_counts = Counter(r["risk_level"] for r in risks)
        fig = px.bar(
            x=list(risk_counts.keys()),
            y=list(risk_counts.values()),
            labels={"x": "Risk level", "y": "Risks"},
            title="Risks by level",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("No risks recorded yet.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _init_state()
    render_sidebar()

    st.title("Sentinel GRC")
    st.caption("Security Configuration & Compliance Platform \u2014 frontend")

    tabs = st.tabs(
        ["\U0001F4CB Assessment", "\U0001F4CE Evidence", "\U0001F6A9 Findings", "\u26A0\uFE0F Risk register", "\U0001F4CA Dashboard"]
    )
    with tabs[0]:
        render_assessment_tab()
    with tabs[1]:
        render_evidence_tab()
    with tabs[2]:
        render_findings_tab()
    with tabs[3]:
        render_risk_tab()
    with tabs[4]:
        render_dashboard_tab()


if __name__ == "__main__":
    main()
