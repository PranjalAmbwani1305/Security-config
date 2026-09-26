from abc import ABC, abstractmethod
import json

from backend.app.core.models import ChecklistItem
from backend.app.core.checklist_validator import GeneratedChecklistItem


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass


class MockLLMProvider(LLMProvider):

    def generate(self, prompt: str) -> str:
        return """
[
    {
        "item_id": "AI-001",
        "category": "Authentication",
        "control": "Authentication settings must follow security policy",
        "reference": "AI-Generated",
        "audit_step": "Review authentication configuration"
    },
    {
        "item_id": "AI-002",
        "category": "Access Control",
        "control": "User privileges must follow least privilege",
        "reference": "AI-Generated",
        "audit_step": "Review user and privilege assignments"
    }
]
"""


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

        response = self.provider.generate(prompt)

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