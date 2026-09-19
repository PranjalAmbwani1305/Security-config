from backend.app.config import LLM_PROVIDER
from backend.app.core.checklist_generator import (
    ChecklistGenerator,
    MockLLMProvider,
)


def get_checklist_generator() -> ChecklistGenerator:

    if LLM_PROVIDER == "mock":
        provider = MockLLMProvider()
    else:
        raise ValueError(
            f"Unsupported LLM provider: {LLM_PROVIDER}"
        )

    return ChecklistGenerator(provider)