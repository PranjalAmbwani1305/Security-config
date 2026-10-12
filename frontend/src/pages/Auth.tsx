import { useCallback, useState } from "react";
import "./Auth.css";
import type { FormEvent } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  Shield,
  Sparkles,
  Building2,
  UserRound,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import GoogleSignInButton from "../auth/GoogleSignInButton";
import { ApiError, GOOGLE_CLIENT_ID } from "../lib/api";

type AuthMode = "login" | "register";

function Auth() {
  const navigate = useNavigate();

  const [mode, setMode] = useState<AuthMode>("login");
  const [showPassword, setShowPassword] = useState(false);

  const { login, register, loginWithGoogle } = useAuth();
  const [params] = useSearchParams();
  const invitationToken = params.get("invite") || undefined;

  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // A new Google user must name an organization; we keep the credential and
  // ask for it, then resubmit.
  const [pendingGoogle, setPendingGoogle] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    organization: "",
  });

  const fail = (err: unknown) => {
    setError(err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (pendingGoogle) {
        await loginWithGoogle(pendingGoogle, { organization_name: form.organization });
      } else if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register({
          email: form.email,
          password: form.password,
          full_name: form.name,
          organization_name: invitationToken ? undefined : form.organization,
          invitation_token: invitationToken,
        });
      }
      navigate("/");
    } catch (err) {
      fail(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogleCredential = useCallback(
    async (credential: string) => {
      setError("");
      try {
        await loginWithGoogle(credential, { invitation_token: invitationToken });
        navigate("/");
      } catch (err) {
        if (err instanceof ApiError && err.code === "organization_required") {
          setPendingGoogle(credential);
          setMode("register");
          setError("Welcome! Name your organization to finish creating your account.");
        } else {
          fail(err);
        }
      }
    },
    [loginWithGoogle, invitationToken, navigate],
  );

  const needsOrganization = !invitationToken && (mode === "register" || pendingGoogle !== null);

  return (
    <main className="auth-page">
      <div className="auth-background">
        <div className="auth-orb auth-orb-purple" />
        <div className="auth-orb auth-orb-pink" />
        <div className="auth-orb auth-orb-cyan" />
      </div>

      <div className="auth-layout">
        {/* LEFT */}
        <section className="auth-hero">
          <div className="auth-hero-content">
            <div className="auth-brand">
              <div className="auth-brand-icon">
                <Shield size={23} />
              </div>

              <div>
                <div className="auth-brand-name">
                  Sentinel <span>GRC</span>
                </div>

                <div className="auth-brand-subtitle">
                  Security Platform
                </div>
              </div>
            </div>

            <div className="auth-hero-main">
              <div className="auth-kicker">
                <Sparkles size={14} />
                Agentic Security & Compliance
              </div>

              <h1>
                Security posture.
                <br />
                <span>Smarter oversight.</span>
              </h1>

              <p>
                Assess security configurations, manage compliance,
                identify risks and build audit-ready evidence across
                your technology environment.
              </p>

              <div className="auth-features">
                <Feature
                  title="Automated Assessments"
                  description="Structured security control evaluation"
                />

                <Feature
                  title="Risk Intelligence"
                  description="Prioritize security findings"
                />

                <Feature
                  title="Evidence Management"
                  description="Centralized audit evidence"
                />

                <Feature
                  title="Compliance Reporting"
                  description="Audit-ready reporting workflows"
                />
              </div>
            </div>

            <div className="auth-metrics">
              <Metric label="Security Controls" value="AI Ready" />
              <Metric label="Risk Analysis" value="Automated" />
              <Metric label="Architecture" value="API First" />
            </div>
          </div>
        </section>

        {/* RIGHT */}
        <section className="auth-form-section">
          <div className="auth-card-wrapper">
            <div className="auth-card-glow" />

            <div className="auth-card">
              <div className="auth-card-header">
                <div className="auth-card-icon">
                  <Shield size={27} />
                </div>

                <h2>
                  {mode === "login"
                    ? "Welcome back"
                    : "Create your workspace"}
                </h2>

                <p>
                  {mode === "login"
                    ? "Sign in to your Sentinel GRC workspace."
                    : "Start managing security and compliance."}
                </p>
              </div>

              <div className="auth-tabs">
                <button
                  type="button"
                  className={mode === "login" ? "active" : ""}
                  onClick={() => setMode("login")}
                >
                  Sign In
                </button>

                <button
                  type="button"
                  className={mode === "register" ? "active" : ""}
                  onClick={() => setMode("register")}
                >
                  Register
                </button>
              </div>

              <form
                className="auth-form"
                onSubmit={handleSubmit}
              >
                {mode === "register" && (
                  <AuthInput
                    label="Full Name"
                    placeholder="Your name"
                    icon={UserRound}
                    value={form.name}
                    onChange={(value) =>
                      setForm({ ...form, name: value })
                    }
                  />
                )}

                {!pendingGoogle && (<AuthInput
                  label="Email Address"
                  placeholder="you@company.com"
                  icon={Mail}
                  type="email"
                  value={form.email}
                  onChange={(value) =>
                    setForm({ ...form, email: value })
                  }
                />)}

                {!pendingGoogle && (
                <div className="auth-field">
                  <label>Password</label>

                  <div className="auth-input-wrapper">
                    <LockKeyhole size={16} />

                    <input
                      required
                      type={showPassword ? "text" : "password"}
                      placeholder="Enter your password"
                      value={form.password}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          password: event.target.value,
                        })
                      }
                    />

                    <button
                      type="button"
                      onClick={() =>
                        setShowPassword(!showPassword)
                      }
                      className="auth-password-toggle"
                    >
                      {showPassword ? (
                        <EyeOff size={16} />
                      ) : (
                        <Eye size={16} />
                      )}
                    </button>
                  </div>
                </div>
                )}

                {needsOrganization && (
                  <AuthInput
                    label="Organization"
                    placeholder="Your company or team name"
                    icon={Building2}
                    value={form.organization}
                    onChange={(value) =>
                      setForm({ ...form, organization: value })
                    }
                  />
                )}

                {invitationToken && mode === "register" && (
                  <p className="auth-note">
                    You are joining an organization through an invitation.
                  </p>
                )}

                {error && (
                  <p className="auth-error" role="alert">
                    {error}
                  </p>
                )}

                <button className="auth-submit" type="submit" disabled={submitting}>
                  <span>
                    {submitting
                      ? "Please wait…"
                      : pendingGoogle
                        ? "Finish Sign-Up"
                        : mode === "login"
                          ? "Sign In"
                          : "Create Account"}
                  </span>

                  <ArrowRight size={16} />
                </button>
              </form>

              {GOOGLE_CLIENT_ID && !pendingGoogle && (
                <>
                  <div className="auth-divider">
                    <span />
                    <label>OR</label>
                    <span />
                  </div>

                  <GoogleSignInButton
                    onCredential={handleGoogleCredential}
                    onError={setError}
                  />
                </>
              )}

              <p className="auth-footer">
                Enterprise access is managed by your organization.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function AuthInput({
  label,
  placeholder,
  icon: Icon,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  placeholder: string;
  icon: typeof Mail;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <div className="auth-field">
      <label>{label}</label>

      <div className="auth-input-wrapper">
        <Icon size={16} />

        <input
          required
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
    </div>
  );
}

function Feature({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="auth-feature">
      <CheckCircle2 size={17} />

      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="auth-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

export default Auth;