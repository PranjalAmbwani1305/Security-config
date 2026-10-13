"""Placeholder AI endpoints still backed by legacy code (NOT real AI).

The checklist library moved to app/api/checklists.py (increment 3). The generator and
assistant are replaced by the multi-agent AI layer in later increments.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthContext, require_permission
from app.core.provider_factory import get_checklist_generator
from app.core.rbac import Permission as P
from app.services.ai_assistant import ai_assistant

router = APIRouter(tags=["library"])
checklist_generator_service = get_checklist_generator()


@router.get("/checklists/{technology:path}/generate")
def generate_checklist_api(technology: str, _: AuthContext = Depends(require_permission(P.AI_GENERATE))):
    checklist = checklist_generator_service.generate(technology)
    return {"technology": technology, "source": "AI-Generated",
            "total_controls": len(checklist), "checklist": checklist}


class AIAssistantRequest(BaseModel):
    question: str
    context: dict | None = None


@router.post("/ai/ask")
def ask_ai_assistant(request: AIAssistantRequest, _: AuthContext = Depends(require_permission(P.DATA_READ))):
    return ai_assistant.answer(request.question, request.context)
