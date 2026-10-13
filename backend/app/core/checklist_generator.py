from abc import ABC, abstractmethod
import json

from app.core.models import ChecklistItem
from app.core.checklist_validator import GeneratedChecklistItem


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str, technology: str = "") -> str:
        pass


# (category, control template, audit step template, rationale-free reference)
_MOCK_CONTROLS = [
    ("Authentication", "Default and vendor accounts on {t} must be disabled or have their credentials changed",
     "List accounts on {t} and confirm no default credentials remain"),
    ("Authentication", "Multi-factor authentication must be enforced for all administrative access to {t}",
     "Review the {t} admin login configuration and confirm MFA is required"),
    ("Access Control", "Access to {t} must follow least privilege and be reviewed periodically",
     "Export {t} role/permission assignments and compare them with the approved access list"),
    ("Access Control", "Shared and unused administrative accounts on {t} must be removed",
     "Review {t} account inventory for shared, dormant or orphaned accounts"),
    ("Encryption", "Data in transit to and from {t} must use current TLS versions and strong ciphers",
     "Scan the {t} endpoints and confirm TLS 1.2+ with no weak ciphers"),
    ("Encryption", "Sensitive data at rest in {t} must be encrypted and keys managed securely",
     "Verify encryption-at-rest settings and key management for {t}"),
    ("Logging & Monitoring", "Security-relevant events on {t} must be logged and forwarded to central monitoring",
     "Confirm {t} audit logging is enabled and logs reach the SIEM/log server"),
    ("Logging & Monitoring", "Log retention for {t} must meet the organization's retention policy",
     "Check {t} log retention settings against policy"),
    ("Patch Management", "{t} must run a vendor-supported version with current security patches",
     "Compare the installed {t} version and patch level with the vendor's latest security release"),
    ("Network Security", "Network exposure of {t} must be restricted to required sources and ports only",
     "Review firewall rules and listening ports for {t}"),
    ("Configuration Hardening", "Unnecessary services, features and sample content on {t} must be disabled",
     "Review enabled services/features on {t} against the hardening baseline"),
    ("Backup & Recovery", "{t} configuration and data must be backed up and restores tested",
     "Inspect the {t} backup schedule and the date of the last successful restore test"),
    ("Vulnerability Management", "{t} must be included in regular vulnerability scans and findings remediated on time",
     "Review the latest scan report covering {t} and open-finding ageing"),
    ("Incident Response", "Procedures for detecting and responding to security incidents involving {t} must exist",
     "Obtain the incident response runbook covering {t} and confirm owners and contacts"),
]


class MockLLMProvider(LLMProvider):
    """Deterministic stand-in for a real LLM: a broad, technology-aware baseline.

    NOT real AI output - it exists so the draft -> review -> approve workflow can be
    demonstrated and tested without an external API.  Real providers plug in via
    provider_factory and must return the same JSON shape."""

    def generate(self, prompt: str, technology: str = "") -> str:
        t = (technology or "the target technology").strip()
        items = [
            {"item_id": f"AI-{i:03d}", "category": cat, "control": ctl.format(t=t),
             "reference": "AI-Generated", "audit_step": step.format(t=t)}
            for i, (cat, ctl, step) in enumerate(_MOCK_CONTROLS, start=1)
        ]
        return json.dumps(items)


class ChecklistGenerator:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def generate(self, technology: str) -> list[ChecklistItem]:

        prompt = f"""
Generate a security compliance checklist for {technology}.

Each control must include:
- item_id
- category
- control
- reference
- audit_step

Return structured checklist data.
"""

        response = self.provider.generate(prompt, technology=technology)

        try:
            data = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM provider returned invalid JSON"
            ) from exc

        try:
            validated_items = [
                GeneratedChecklistItem(**item)
                for item in data
            ]
        except Exception as exc:
            raise ValueError(
                "LLM provider returned invalid checklist data"
            ) from exc

        item_ids = [item.item_id for item in validated_items]

        if len(item_ids) != len(set(item_ids)):
            raise ValueError(
                "LLM provider returned duplicate checklist item IDs"
            )

        checklist = [
            ChecklistItem(**item.model_dump())
            for item in validated_items
        ]

        return checklist