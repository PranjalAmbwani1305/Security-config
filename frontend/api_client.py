"""
HTTP client for the Sentinel GRC backend (backend/app/main.py).

This module ONLY makes HTTP calls to the existing FastAPI backend. It holds
no compliance scoring, risk scoring, or checklist content of its own - all
of that stays server-side in backend/app/core/*, untouched. The Streamlit
frontend (app.py) imports these functions instead of calling `requests`
directly all over the UI code.
"""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_TIMEOUT = 10  # seconds


class ApiError(Exception):
    """Raised when the backend can't be reached or returns an HTTP error."""


def _get(base_url: str, path: str) -> dict[str, Any]:
    try:
        resp = requests.get(f"{base_url}{path}", timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        raise ApiError(str(exc)) from exc


def _post(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = requests.post(f"{base_url}{path}", json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        raise ApiError(str(exc)) from exc


# ---- health -----------------------------------------------------------

def health_check(base_url: str) -> dict[str, Any]:
    return _get(base_url, "/health")


# ---- checklists ---------------------------------------------------------

def get_checklist(base_url: str, technology: str) -> dict[str, Any]:
    return _get(base_url, f"/checklists/{technology}")


def generate_checklist(base_url: str, technology: str) -> dict[str, Any]:
    return _get(base_url, f"/checklists/{technology}/generate")


# ---- engagements --------------------------------------------------------

def create_engagement(
    base_url: str, engagement_id: str, client_name: str, technology: str, reviewer: str
) -> dict[str, Any]:
    return _post(
        base_url,
        "/engagements",
        {
            "engagement_id": engagement_id,
            "client_name": client_name,
            "technology": technology,
            "reviewer": reviewer,
        },
    )


def list_engagements(base_url: str) -> dict[str, Any]:
    return _get(base_url, "/engagements")


def get_engagement(base_url: str, engagement_id: str) -> dict[str, Any]:
    return _get(base_url, f"/engagements/{engagement_id}")


# ---- assessments --------------------------------------------------------

def submit_assessment(
    base_url: str, engagement_id: str, results: list[dict[str, str]]
) -> dict[str, Any]:
    return _post(
        base_url,
        "/assessments",
        {"engagement_id": engagement_id, "results": results},
    )


def get_assessments(base_url: str, engagement_id: str) -> dict[str, Any]:
    return _get(base_url, f"/assessments/{engagement_id}")


# ---- evidence -------------------------------------------------------------

def add_evidence(base_url: str, engagement_id: str, item_id: str, evidence: str) -> dict[str, Any]:
    return _post(
        base_url,
        "/evidence",
        {"engagement_id": engagement_id, "item_id": item_id, "evidence": evidence},
    )


def get_evidence(base_url: str, engagement_id: str) -> dict[str, Any]:
    return _get(base_url, f"/evidence/{engagement_id}")


# ---- findings -------------------------------------------------------------

def create_finding(
    base_url: str,
    finding_id: str,
    engagement_id: str,
    item_id: str,
    title: str,
    description: str,
    severity: str,
    recommendation: str,
    status: str,
) -> dict[str, Any]:
    return _post(
        base_url,
        "/findings",
        {
            "finding_id": finding_id,
            "engagement_id": engagement_id,
            "item_id": item_id,
            "title": title,
            "description": description,
            "severity": severity,
            "recommendation": recommendation,
            "status": status,
        },
    )


def get_findings(base_url: str, engagement_id: str) -> dict[str, Any]:
    return _get(base_url, f"/findings/{engagement_id}")


# ---- risks ------------------------------------------------------------

def create_risk(
    base_url: str,
    risk_id: str,
    engagement_id: str,
    finding_id: str,
    title: str,
    likelihood: int,
    impact: int,
    treatment: str,
    owner: str,
    status: str,
) -> dict[str, Any]:
    return _post(
        base_url,
        "/risks",
        {
            "risk_id": risk_id,
            "engagement_id": engagement_id,
            "finding_id": finding_id,
            "title": title,
            "likelihood": likelihood,
            "impact": impact,
            "treatment": treatment,
            "owner": owner,
            "status": status,
        },
    )


def get_risks(base_url: str, engagement_id: str) -> dict[str, Any]:
    return _get(base_url, f"/risks/{engagement_id}")
