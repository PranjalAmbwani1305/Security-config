import { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Copy,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Webhook as WebhookIcon,
  XCircle,
} from "lucide-react";
import "./Webhooks.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Webhook = {
  webhook_id: string;
  name: string;
  url: string;
  event: string;
  active: boolean;
  created_at?: string;
  last_delivery?: string | null;
  last_status?: string | null;
};

export default function Webhooks() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "",
    url: "",
    event: "risk.created",
    active: true,
  });

  const loadWebhooks = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_URL}/webhooks`);

      if (!response.ok) {
        throw new Error("Failed to load webhooks");
      }

      const data = await response.json();
      setWebhooks(Array.isArray(data) ? data : data.webhooks || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load webhooks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWebhooks();
  }, []);

  const createWebhook = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setError("");
      setMessage("");

      const response = await fetch(`${API_URL}/webhooks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to create webhook");
      }

      setMessage("Webhook created successfully.");
      setShowModal(false);

      setForm({
        name: "",
        url: "",
        event: "risk.created",
        active: true,
      });

      await loadWebhooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create webhook");
    }
  };

  const testWebhook = async (webhookId: string) => {
    try {
      setTesting(webhookId);
      setError("");
      setMessage("");

      const response = await fetch(
        `${API_URL}/webhooks/${webhookId}/test`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Webhook test failed");
      }

      setMessage(
        `Webhook ${webhookId} delivered successfully. Status: ${
          data.status_code ?? "OK"
        }`
      );

      await loadWebhooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Webhook test failed");
    } finally {
      setTesting(null);
    }
  };

  const deleteWebhook = async (webhookId: string) => {
    const confirmed = window.confirm(
      "Are you sure you want to delete this webhook?"
    );

    if (!confirmed) return;

    try {
      setError("");
      setMessage("");

      const response = await fetch(`${API_URL}/webhooks/${webhookId}`, {
        method: "DELETE",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to delete webhook");
      }

      setMessage("Webhook deleted successfully.");
      await loadWebhooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete webhook");
    }
  };

  const copyUrl = async (url: string) => {
    await navigator.clipboard.writeText(url);
    setMessage("Webhook URL copied.");
  };

  const activeCount = webhooks.filter((item) => item.active).length;

  return (
    <div className="webhooks-page">
      <div className="webhooks-header">
        <div>
          <div className="webhooks-eyebrow">
            <WebhookIcon size={15} />
            INTEGRATIONS
          </div>

          <h1>Webhooks</h1>

          <p>
            Connect Sentinel GRC events with external systems and automation
            workflows.
          </p>
        </div>

        <div className="webhooks-actions">
          <button className="secondary-btn" onClick={loadWebhooks}>
            <RefreshCw size={16} />
            Refresh
          </button>

          <button
            className="primary-btn"
            onClick={() => {
              setError("");
              setMessage("");
              setShowModal(true);
            }}
          >
            <Plus size={17} />
            New Webhook
          </button>
        </div>
      </div>

      {message && (
        <div className="alert success-alert">
          <CheckCircle2 size={17} />
          {message}
        </div>
      )}

      {error && (
        <div className="alert error-alert">
          <XCircle size={17} />
          {error}
        </div>
      )}

      <div className="webhook-stats">
        <div className="webhook-stat-card">
          <div className="stat-icon">
            <WebhookIcon size={20} />
          </div>
          <div>
            <span>Total Webhooks</span>
            <strong>{webhooks.length}</strong>
          </div>
        </div>

        <div className="webhook-stat-card">
          <div className="stat-icon green">
            <Activity size={20} />
          </div>
          <div>
            <span>Active</span>
            <strong>{activeCount}</strong>
          </div>
        </div>

        <div className="webhook-stat-card">
          <div className="stat-icon blue">
            <Send size={20} />
          </div>
          <div>
            <span>Events</span>
            <strong>{webhooks.length}</strong>
          </div>
        </div>
      </div>

      <div className="webhooks-panel">
        <div className="panel-heading">
          <div>
            <h2>Configured Webhooks</h2>
            <p>Manage external event destinations.</p>
          </div>

          <span className="live-indicator">
            <span />
            Live
          </span>
        </div>

        {loading ? (
          <div className="empty-state">
            <RefreshCw className="spin" size={24} />
            <p>Loading webhooks...</p>
          </div>
        ) : webhooks.length === 0 ? (
          <div className="empty-state">
            <WebhookIcon size={32} />
            <h3>No webhooks configured</h3>
            <p>
              Create your first webhook to connect Sentinel GRC with another
              system.
            </p>

            <button
              className="primary-btn"
              onClick={() => setShowModal(true)}
            >
              <Plus size={16} />
              Create Webhook
            </button>
          </div>
        ) : (
          <div className="webhook-table-wrap">
            <table className="webhook-table">
              <thead>
                <tr>
                  <th>Webhook</th>
                  <th>Event</th>
                  <th>Endpoint</th>
                  <th>Status</th>
                  <th>Last Delivery</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {webhooks.map((webhook) => (
                  <tr key={webhook.webhook_id}>
                    <td>
                      <div className="webhook-name">
                        <div className="webhook-avatar">
                          <WebhookIcon size={16} />
                        </div>

                        <div>
                          <strong>{webhook.name}</strong>
                          <span>{webhook.webhook_id}</span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="event-badge">{webhook.event}</span>
                    </td>

                    <td>
                      <div className="endpoint-cell">
                        <span>{webhook.url}</span>

                        <button
                          className="icon-btn"
                          title="Copy URL"
                          onClick={() => copyUrl(webhook.url)}
                        >
                          <Copy size={14} />
                        </button>
                      </div>
                    </td>

                    <td>
                      <span
                        className={`status-badge ${
                          webhook.active ? "active" : "inactive"
                        }`}
                      >
                        <span />
                        {webhook.active ? "Active" : "Inactive"}
                      </span>
                    </td>

                    <td>
                      <div className="delivery-status">
                        {webhook.last_status ? (
                          <>
                            <strong>{webhook.last_status}</strong>
                            <span>
                              {webhook.last_delivery || "Recent"}
                            </span>
                          </>
                        ) : (
                          <span className="muted">Not tested</span>
                        )}
                      </div>
                    </td>

                    <td>
                      <div className="row-actions">
                        <button
                          className="test-btn"
                          disabled={testing === webhook.webhook_id}
                          onClick={() => testWebhook(webhook.webhook_id)}
                        >
                          <Send size={14} />
                          {testing === webhook.webhook_id
                            ? "Testing..."
                            : "Test"}
                        </button>

                        <button
                          className="delete-btn"
                          title="Delete webhook"
                          onClick={() => deleteWebhook(webhook.webhook_id)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowModal(false)}
        >
          <div
            className="webhook-modal"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <span className="modal-icon">
                  <WebhookIcon size={19} />
                </span>

                <div>
                  <h2>Create Webhook</h2>
                  <p>Configure an external event destination.</p>
                </div>
              </div>

              <button
                className="close-btn"
                onClick={() => setShowModal(false)}
              >
                ×
              </button>
            </div>

            <form onSubmit={createWebhook}>
              <label>
                Webhook Name
                <input
                  required
                  value={form.name}
                  placeholder="e.g. Security Operations"
                  onChange={(e) =>
                    setForm({ ...form, name: e.target.value })
                  }
                />
              </label>

              <label>
                Endpoint URL
                <input
                  required
                  type="url"
                  value={form.url}
                  placeholder="https://example.com/webhook"
                  onChange={(e) =>
                    setForm({ ...form, url: e.target.value })
                  }
                />
              </label>

              <label>
                Event
                <select
                  value={form.event}
                  onChange={(e) =>
                    setForm({ ...form, event: e.target.value })
                  }
                >
                  <option value="risk.created">risk.created</option>
                  <option value="finding.created">finding.created</option>
                  <option value="assessment.completed">
                    assessment.completed
                  </option>
                  <option value="engagement.created">
                    engagement.created
                  </option>
                </select>
              </label>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) =>
                    setForm({ ...form, active: e.target.checked })
                  }
                />
                <span>Enable webhook immediately</span>
              </label>

              <div className="modal-footer">
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>

                <button type="submit" className="primary-btn">
                  <Plus size={16} />
                  Create Webhook
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}