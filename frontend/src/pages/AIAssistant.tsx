import { useState } from "react";
import type { FormEvent } from "react";
import {
  Bot,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import "./AIAssistant.css";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Message = {
  role: "assistant" | "user";
  content: string;
};

export default function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello. I’m the Sentinel GRC AI Assistant. Ask me about security controls, assessments, compliance, findings, risks, remediation, or AI-generated checklists.",
    },
  ]);

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const askAssistant = async (e?: FormEvent) => {
    e?.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) return;

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: trimmedQuestion,
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/ai/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          context: {},
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "AI Assistant request failed"
        );
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "Unable to connect to the AI Assistant.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const suggestedQuestions = [
    "What is risk management?",
    "Explain compliance assessment",
    "How should we remediate a finding?",
    "What is an AI-generated checklist?",
  ];

  return (
    <div className="ai-page">
      <div className="ai-header">
        <div>
          <div className="ai-eyebrow">
            <Sparkles size={14} />
            SENTINEL INTELLIGENCE
          </div>

          <h1>AI Assistant</h1>

          <p>
            AI-assisted security and compliance guidance for GRC
            teams.
          </p>
        </div>

        <div className="ai-status">
          <span />
          AI Assistant Online
        </div>
      </div>

      <div className="ai-layout">
        <aside className="ai-sidebar">
          <div className="ai-profile">
            <div className="ai-avatar">
              <Bot size={22} />
            </div>

            <div>
              <strong>Sentinel AI</strong>
              <span>GRC Assistant</span>
            </div>
          </div>

          <div className="ai-capabilities">
            <h3>Capabilities</h3>

            <div>
              <ShieldCheck size={16} />
              Security Controls
            </div>

            <div>
              <ShieldCheck size={16} />
              Compliance
            </div>

            <div>
              <ShieldCheck size={16} />
              Findings & Risks
            </div>

            <div>
              <ShieldCheck size={16} />
              Remediation
            </div>

            <div>
              <ShieldCheck size={16} />
              AI Checklists
            </div>
          </div>

          <div className="ai-notice">
            <Sparkles size={15} />

            <p>
              AI-generated guidance should be reviewed by a
              qualified human before being used for a final
              security or compliance decision.
            </p>
          </div>
        </aside>

        <section className="chat-panel">
          <div className="chat-header">
            <div>
              <h2>Security & Compliance Copilot</h2>
              <span>
                Ask questions about your GRC workflow
              </span>
            </div>
          </div>

          <div className="chat-messages">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`message-row ${message.role}`}
              >
                <div className="message-avatar">
                  {message.role === "assistant" ? (
                    <Bot size={16} />
                  ) : (
                    <User size={16} />
                  )}
                </div>

                <div className="message-content">
                  <span className="message-label">
                    {message.role === "assistant"
                      ? "Sentinel AI"
                      : "You"}
                  </span>

                  <div className="message-bubble">
                    {message.content}
                  </div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row assistant">
                <div className="message-avatar">
                  <Bot size={16} />
                </div>

                <div className="message-content">
                  <span className="message-label">
                    Sentinel AI
                  </span>

                  <div className="message-bubble typing">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="suggestions">
            {suggestedQuestions.map((item) => (
              <button
                key={item}
                onClick={() => setQuestion(item)}
              >
                {item}
              </button>
            ))}
          </div>

          <form
            className="chat-input-area"
            onSubmit={askAssistant}
          >
            <input
              value={question}
              onChange={(e) =>
                setQuestion(e.target.value)
              }
              placeholder="Ask Sentinel AI about security or compliance..."
              disabled={loading}
            />

            <button
              type="submit"
              disabled={!question.trim() || loading}
              aria-label="Send message"
            >
              <Send size={17} />
            </button>
          </form>

          <div className="ai-footer">
            <Sparkles size={12} />
            AI-generated responses · Human review required
          </div>
        </section>
      </div>
    </div>
  );
}