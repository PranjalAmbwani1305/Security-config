from app.config import get_settings
from app.core.checklist_generator import ChecklistGenerator, MockLLMProvider


def get_checklist_generator() -> ChecklistGenerator:
    provider_name = get_settings().llm_provider

    if provider_name == "mock":
        provider = MockLLMProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")

    return ChecklistGenerator(provider)
