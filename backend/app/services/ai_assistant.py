from typing import Any


class GrcAIAssistant:
    """
    Demo AI assistant for Sentinel GRC.

    Current implementation uses deterministic responses so the
    prototype works without an external LLM/API dependency.
    """

    def answer(self, question: str, context: dict[str, Any] | None = None) -> dict:
        question_lower = question.lower().strip()

        if not question_lower:
            return {
                "answer": "Please enter a GRC question.",
                "source": "sentinel-grc-ai-demo",
            }

        if "risk" in question_lower:
            answer = (
                "Risk management in Sentinel GRC uses likelihood × impact "
                "to calculate a risk score. Scores are classified as Low, "
                "Medium, High, or Critical. High and Critical risks should "
                "have documented treatment, ownership, and remediation tracking."
            )

        elif "finding" in question_lower:
            answer = (
                "A finding represents a security or compliance gap identified "
                "during an assessment. A useful finding should include the "
                "affected control, description, severity, recommendation, "
                "and remediation status."
            )

        elif "compliance" in question_lower:
            answer = (
                "Compliance is calculated from assessed controls. Controls "
                "marked Compliant or Compensating Control contribute positively, "
                "while Non-Compliant controls reduce the overall compliance percentage."
            )

        elif "remediation" in question_lower:
            answer = (
                "Recommended remediation workflow: identify the affected "
                "control, document the evidence and gap, assign an owner, "
                "define a remediation action, set a target date, and verify "
                "the control again after remediation."
            )

        elif "assessment" in question_lower:
            answer = (
                "An assessment evaluates security controls against the selected "
                "technology checklist. Each control can be marked Compliant, "
                "Non-Compliant, Compensating Control, Not Applicable, or "
                "Not Reviewed."
            )

        elif "checklist" in question_lower:
            answer = (
                "Sentinel GRC can generate technology-specific checklist drafts. "
                "AI-generated controls should be reviewed and approved by a "
                "human reviewer before being used as the final assessment baseline."
            )

        elif "sentinel" in question_lower or "what can you do" in question_lower:
            answer = (
                "I am the Sentinel GRC AI Assistant. I can help explain "
                "security controls, assessment results, findings, risks, "
                "compliance status, and remediation activities."
            )

        else:
            answer = (
                "I can help with Sentinel GRC topics such as security controls, "
                "assessments, compliance, findings, risks, remediation, and "
                "AI-generated checklists."
            )

        return {
            "answer": answer,
            "source": "sentinel-grc-ai-demo",
            "ai_generated": True,
            "human_review_required": True,
            "context_used": context or {},
        }


ai_assistant = GrcAIAssistant()