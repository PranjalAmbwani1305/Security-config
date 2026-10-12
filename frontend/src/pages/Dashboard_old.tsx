import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  FileWarning,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

import Sidebar from "../components/Sidebar";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Engagement = {
  engagement_id: string;
  client_name: string;
  technology: string;
  reviewer: string;
};

type Assessment = {
  item_id: string;
  status: string;
  notes: string;
};

type Finding = {
  finding_id?: string;
  title?: string;
  status?: string;
  severity?: string;
};

type Risk = {
  risk_id: string;
  engagement_id: string;
  finding_id: string;
  title: string;
  likelihood: number;
  impact: number;
  risk_score: number;
  risk_level: string;
  treatment: string;
  owner: string;
  status: string;
};

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }

  return response.json();
}

function arrayFrom<T>(data: unknown, key: string): T[] {
  if (Array.isArray(data)) {
    return data as T[];
  }

  if (
    typeof data === "object" &&
    data !== null &&
    Array.isArray((data as Record<string, unknown>)[key])
  ) {
    return (data as Record<string, unknown>)[key] as T[];
  }

  return [];
}

function Dashboard() {
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const loadDashboard = useCallback(async () => {
    try {
      setError("");

      const engagementData = await getJson<unknown>(
        `${API_URL}/engagements`,
      );

      const engagementList = arrayFrom<Engagement>(
        engagementData,
        "engagements",
      );

      const allAssessments: Assessment[] = [];
      const allFindings: Finding[] = [];
      const allRisks: Risk[] = [];

      await Promise.all(
        engagementList.map(async (engagement) => {
          const [assessmentData, findingData, riskData] =
            await Promise.all([
              getJson<unknown>(
                `${API_URL}/assessments/${engagement.engagement_id}`,
              ).catch(() => ({ assessments: [] })),

              getJson<unknown>(
                `${API_URL}/findings/${engagement.engagement_id}`,
              ).catch(() => ({ findings: [] })),

              getJson<unknown>(
                `${API_URL}/risks/${engagement.engagement_id}`,
              ).catch(() => ({ risks: [] })),
            ]);

          allAssessments.push(
            ...arrayFrom<Assessment>(
              assessmentData,
              "assessments",
            ),
          );

          allFindings.push(
            ...arrayFrom<Finding>(
              findingData,
              "findings",
            ),
          );

          allRisks.push(
            ...arrayFrom<Risk>(riskData, "risks"),
          );
        }),
      );

      setEngagements(engagementList);
      setAssessments(allAssessments);
      setFindings(allFindings);
      setRisks(allRisks);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to Sentinel GRC API.",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const compliance = useMemo(() => {
    const assessed = assessments.filter((item) =>
      [
        "compliant",
        "non-compliant",
        "compensating control",
      ].includes(item.status.toLowerCase()),
    );

    if (!assessed.length) return null;

    const compliant = assessed.filter((item) =>
      [
        "compliant",
        "compensating control",
      ].includes(item.status.toLowerCase()),
    ).length;

    return Math.round((compliant / assessed.length) * 100);
  }, [assessments]);

  const riskCounts = useMemo(
    () => ({
      critical: risks.filter(
        (risk) =>
          risk.risk_level.toLowerCase() === "critical",
      ).length,

      high: risks.filter(
        (risk) => risk.risk_level.toLowerCase() === "high",
      ).length,

      medium: risks.filter(
        (risk) =>
          risk.risk_level.toLowerCase() === "medium",
      ).length,

      low: risks.filter(
        (risk) => risk.risk_level.toLowerCase() === "low",
      ).length,
    }),
    [risks],
  );

  const technologyCoverage = useMemo(() => {
    const map: Record<string, number> = {};

    engagements.forEach((item) => {
      map[item.technology] =
        (map[item.technology] || 0) + 1;
    });

    return Object.entries(map);
  }, [engagements]);

  const filteredEngagements = useMemo(() => {
    const value = search.toLowerCase().trim();

    if (!value) return engagements;

    return engagements.filter((item) =>
      `${item.client_name} ${item.engagement_id} ${item.technology} ${item.reviewer}`
        .toLowerCase()
        .includes(value),
    );
  }, [engagements, search]);

  const refresh = async () => {
    setRefreshing(true);
    await loadDashboard();
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#070711] text-slate-200">
      {/* Ambient animated background */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="dashboard-orb dashboard-orb-one" />
        <div className="dashboard-orb dashboard-orb-two" />
        <div className="dashboard-orb dashboard-orb-three" />

        <div className="absolute inset-0 opacity-[0.025] [background-image:linear-gradient(rgba(255,255,255,0.8)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.8)_1px,transparent_1px)] [background-size:80px_80px]" />
      </div>

      <div className="relative flex min-h-screen">
        <Sidebar />

        <main className="min-w-0 flex-1">
          {/* Header */}
          <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#070711]/85 backdrop-blur-xl">
            <div className="flex h-[72px] items-center justify-between px-6 lg:px-8">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span>Workspace</span>
                <ChevronRight className="h-3.5 w-3.5" />
                <span className="text-slate-300">
                  Command Center
                </span>
              </div>

              <div className="flex items-center gap-3">
                <div className="hidden items-center gap-2 rounded-full border border-emerald-400/10 bg-emerald-400/5 px-3 py-1.5 md:flex">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  <span className="text-[11px] text-emerald-400">
                    Platform Operational
                  </span>
                </div>

                <button
                  onClick={refresh}
                  disabled={refreshing}
                  className="flex h-9 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 text-xs text-slate-400 transition hover:border-violet-400/30 hover:text-white disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${
                      refreshing ? "animate-spin" : ""
                    }`}
                  />
                  Refresh
                </button>

                <Link
                  to="/engagements"
                  className="hidden h-9 items-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-pink-500 px-4 text-xs font-semibold text-white shadow-lg shadow-violet-500/10 transition hover:-translate-y-0.5 hover:shadow-violet-500/25 sm:flex"
                >
                  <BriefcaseBusiness className="h-3.5 w-3.5" />
                  New Engagement
                </Link>

                <div className="flex h-9 w-9 items-center justify-center rounded-full border border-violet-400/20 bg-gradient-to-br from-violet-500/30 to-pink-500/20 text-xs font-bold text-violet-200">
                  P
                </div>
              </div>
            </div>
          </header>

          <div className="p-6 lg:p-8">
            {/* Error */}
            {error && (
              <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-400/20 bg-red-500/5 px-4 py-3">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                <span className="text-xs text-red-300">
                  {error}
                </span>
              </div>
            )}

            {/* Hero */}
            <section className="relative overflow-hidden rounded-2xl border border-violet-400/10 bg-gradient-to-br from-[#121021] via-[#0c0b17] to-[#17101b] p-7 lg:p-9">
              <div className="absolute -right-20 -top-40 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
              <div className="absolute -bottom-40 left-1/3 h-72 w-72 rounded-full bg-pink-500/5 blur-3xl" />

              <div className="relative grid gap-8 lg:grid-cols-[1fr_320px] lg:items-center">
                <div>
                  <div className="mb-4 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-violet-400">
                    <Sparkles className="h-3.5 w-3.5" />
                    Command Center
                  </div>

                  <h1 className="text-3xl font-bold tracking-tight text-white lg:text-4xl">
                    Security Posture,
                    <br />
                    <span className="dashboard-gradient-text">
                      Smarter Oversight.
                    </span>
                  </h1>

                  <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-500">
                    Monitor assessments, controls, findings and
                    risks across your infrastructure through one
                    security and compliance workspace.
                  </p>
                </div>

                {/* Animated shield */}
                <div className="relative mx-auto hidden h-44 w-44 lg:block">
                  <div className="absolute inset-0 animate-pulse rounded-full bg-violet-500/10 blur-3xl" />

                  <div className="absolute inset-8 animate-[spin_18s_linear_infinite] rounded-3xl border border-violet-400/20" />

                  <div className="absolute inset-10 flex rotate-45 items-center justify-center rounded-2xl border border-violet-400/30 bg-gradient-to-br from-violet-500/20 to-pink-500/10 shadow-[0_0_50px_rgba(168,85,247,0.2)]">
                    <Shield className="h-14 w-14 -rotate-45 text-violet-300" />
                  </div>
                </div>
              </div>
            </section>

            {/* KPI */}
            <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Kpi
                title="Engagements"
                value={loading ? "—" : engagements.length}
                description="Security assessments"
                icon={BriefcaseBusiness}
                accent="violet"
              />

              <Kpi
                title="Controls Assessed"
                value={loading ? "—" : assessments.length}
                description="Across all engagements"
                icon={ClipboardCheck}
                accent="cyan"
              />

              <Kpi
                title="Open Findings"
                value={loading ? "—" : findings.length}
                description="Requires review"
                icon={FileWarning}
                accent="pink"
              />

              <Kpi
                title="Active Risks"
                value={loading ? "—" : risks.length}
                description={`${riskCounts.critical} critical`}
                icon={ShieldAlert}
                accent="orange"
              />
            </section>

            {/* Analytics */}
            <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
              {/* Compliance */}
              <Panel
                title="Security Posture"
                subtitle="Current assessment state across all engagements"
                icon={Shield}
              >
                <div className="grid items-center gap-8 md:grid-cols-[190px_1fr]">
                  <div className="mx-auto flex h-44 w-44 items-center justify-center rounded-full bg-[conic-gradient(#a855f7_0deg,#ec4899_120deg,#22d3ee_230deg,#34d399_295deg,#1e293b_295deg)] p-[10px]">
                    <div className="flex h-full w-full flex-col items-center justify-center rounded-full bg-[#0c0c16]">
                      <span className="text-3xl font-bold text-white">
                        {compliance === null
                          ? "—"
                          : `${compliance}%`}
                      </span>
                      <span className="mt-1 text-[10px] uppercase tracking-wider text-slate-600">
                        Compliant
                      </span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <StatusLine
                      label="Compliant"
                      value={
                        assessments.filter((item) =>
                          [
                            "compliant",
                            "compensating control",
                          ].includes(
                            item.status.toLowerCase(),
                          ),
                        ).length
                      }
                      color="bg-emerald-400"
                    />

                    <StatusLine
                      label="Non-Compliant"
                      value={
                        assessments.filter(
                          (item) =>
                            item.status.toLowerCase() ===
                            "non-compliant",
                        ).length
                      }
                      color="bg-pink-400"
                    />

                    <StatusLine
                      label="Not Reviewed"
                      value={
                        assessments.filter(
                          (item) =>
                            ![
                              "compliant",
                              "non-compliant",
                              "compensating control",
                            ].includes(
                              item.status.toLowerCase(),
                            ),
                        ).length
                      }
                      color="bg-slate-500"
                    />
                  </div>
                </div>
              </Panel>

              {/* Risk */}
              <Panel
                title="Risk Overview"
                subtitle="Current risk distribution"
                icon={ShieldAlert}
              >
                <div className="grid grid-cols-4 gap-3 pt-3">
                  <RiskColumn
                    label="Critical"
                    value={riskCounts.critical}
                    color="bg-pink-500"
                    height="h-28"
                  />

                  <RiskColumn
                    label="High"
                    value={riskCounts.high}
                    color="bg-orange-400"
                    height="h-20"
                  />

                  <RiskColumn
                    label="Medium"
                    value={riskCounts.medium}
                    color="bg-amber-300"
                    height="h-14"
                  />

                  <RiskColumn
                    label="Low"
                    value={riskCounts.low}
                    color="bg-emerald-400"
                    height="h-8"
                  />
                </div>
              </Panel>
            </section>

            {/* Engagements + technology */}
            <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
              <Panel
                title="Active Engagements"
                subtitle="Security assessments currently in progress"
                icon={BriefcaseBusiness}
                action={
                  <Link
                    to="/engagements"
                    className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300"
                  >
                    View all
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                }
              >
                <div className="mb-4 relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-700" />

                  <input
                    value={search}
                    onChange={(event) =>
                      setSearch(event.target.value)
                    }
                    placeholder="Search engagements..."
                    className="h-10 w-full rounded-lg border border-white/[0.06] bg-black/20 pl-9 pr-3 text-xs text-white outline-none placeholder:text-slate-700 focus:border-violet-500/40"
                  />
                </div>

                {filteredEngagements.length === 0 ? (
                  <EmptyState
                    text={
                      loading
                        ? "Loading engagements..."
                        : "No engagements found."
                    }
                  />
                ) : (
                  <div className="space-y-2">
                    {filteredEngagements
                      .slice(0, 6)
                      .map((item) => (
                        <Link
                          key={item.engagement_id}
                          to={`/engagements?engagement=${encodeURIComponent(
                            item.engagement_id,
                          )}`}
                          className="group grid grid-cols-[1fr_auto_auto] items-center gap-4 rounded-xl border border-transparent px-3 py-3 transition hover:border-violet-400/10 hover:bg-violet-500/[0.03]"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-slate-200 group-hover:text-violet-300">
                              {item.client_name}
                            </p>

                            <p className="mt-1 font-mono text-[10px] text-slate-700">
                              {item.engagement_id}
                            </p>
                          </div>

                          <span className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-[10px] text-slate-500">
                            {item.technology}
                          </span>

                          <ChevronRight className="h-4 w-4 text-slate-700 transition group-hover:translate-x-1 group-hover:text-violet-400" />
                        </Link>
                      ))}
                  </div>
                )}
              </Panel>

              <Panel
                title="Technology Coverage"
                subtitle="Engagement distribution"
                icon={BarChart3}
              >
                {technologyCoverage.length === 0 ? (
                  <EmptyState text="No technology data yet." />
                ) : (
                  <div className="space-y-5">
                    {technologyCoverage.map(
                      ([technology, count]) => {
                        const percentage =
                          engagements.length > 0
                            ? Math.round(
                                (count /
                                  engagements.length) *
                                  100,
                              )
                            : 0;

                        return (
                          <div key={technology}>
                            <div className="mb-2 flex justify-between text-xs">
                              <span className="text-slate-400">
                                {technology}
                              </span>

                              <span className="text-slate-600">
                                {count}
                              </span>
                            </div>

                            <div className="h-2 overflow-hidden rounded-full bg-slate-900">
                              <div
                                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-pink-400 transition-all duration-700"
                                style={{
                                  width: `${percentage}%`,
                                }}
                              />
                            </div>
                          </div>
                        );
                      },
                    )}
                  </div>
                )}
              </Panel>
            </section>

            {/* Agentic banner */}
            <section className="relative mt-6 overflow-hidden rounded-2xl border border-pink-400/20 bg-gradient-to-r from-violet-600/10 via-pink-500/5 to-orange-400/10 p-5">
              <div className="absolute inset-y-0 right-0 w-1/2 bg-gradient-to-l from-pink-500/10 to-transparent" />

              <div className="relative flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div className="flex items-center gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/20 to-pink-500/20 text-violet-300">
                    <Sparkles className="h-5 w-5" />
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      Agentic Automation
                    </h3>

                    <p className="mt-1 text-xs text-slate-500">
                      AI-powered configuration assessment,
                      risk analysis and compliance workflows.
                    </p>
                  </div>
                </div>

                <Link
                  to="/checklists"
                  className="flex shrink-0 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-violet-600 to-pink-500 px-4 py-2.5 text-xs font-semibold text-white transition hover:scale-[1.02]"
                >
                  Explore AI Features
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </section>

            <footer className="mt-8 flex justify-between border-t border-white/[0.05] pt-5 text-[10px] text-slate-700">
              <span>Sentinel GRC v1.0</span>
              <span>
                Security Configuration & Compliance Platform
              </span>
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}

function Kpi({
  title,
  value,
  description,
  icon: Icon,
  accent,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: typeof Shield;
  accent: "violet" | "cyan" | "pink" | "orange";
}) {
  const styles = {
    violet:
      "from-violet-500/20 to-violet-500/5 text-violet-300",
    cyan: "from-cyan-500/20 to-cyan-500/5 text-cyan-300",
    pink: "from-pink-500/20 to-pink-500/5 text-pink-300",
    orange:
      "from-orange-500/20 to-orange-500/5 text-orange-300",
  };

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/[0.07] bg-[#0c0c16]/80 p-5 transition duration-300 hover:-translate-y-1 hover:border-white/15 hover:shadow-2xl">
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-violet-500/5 blur-2xl transition group-hover:bg-violet-500/10" />

      <div
        className={`relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${styles[accent]}`}
      >
        <Icon className="h-5 w-5" />
      </div>

      <p className="mt-5 text-xs text-slate-600">
        {title}
      </p>

      <div className="mt-1 flex items-end justify-between">
        <p className="text-2xl font-bold text-white">
          {value}
        </p>

        <Activity className="h-4 w-4 text-slate-800 transition group-hover:text-violet-400" />
      </div>

      <p className="mt-1 text-[10px] text-slate-700">
        {description}
      </p>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  icon: Icon,
  children,
  action,
}: {
  title: string;
  subtitle: string;
  icon: typeof Shield;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-[#0b0b15]/80 p-6 backdrop-blur-xl">
      <div className="mb-6 flex items-start justify-between">
        <div className="flex gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-500/10 text-violet-300">
            <Icon className="h-4 w-4" />
          </div>

          <div>
            <h2 className="text-sm font-semibold text-white">
              {title}
            </h2>

            <p className="mt-1 text-[10px] text-slate-600">
              {subtitle}
            </p>
          </div>
        </div>

        {action}
      </div>

      {children}
    </div>
  );
}

function StatusLine({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.05] pb-3 last:border-0">
      <div className="flex items-center gap-3">
        <span className={`h-2 w-2 rounded-full ${color}`} />
        <span className="text-xs text-slate-500">
          {label}
        </span>
      </div>

      <span className="text-sm font-semibold text-slate-200">
        {value}
      </span>
    </div>
  );
}

function RiskColumn({
  label,
  value,
  color,
  height,
}: {
  label: string;
  value: number;
  color: string;
  height: string;
}) {
  return (
    <div className="flex flex-col items-center justify-end">
      <span className="mb-2 text-sm font-semibold text-white">
        {value}
      </span>

      <div className="flex h-32 w-full items-end justify-center rounded-xl bg-white/[0.02]">
        <div
          className={`w-7 rounded-t-lg ${color} ${height} shadow-lg transition-all duration-700`}
        />
      </div>

      <span className="mt-2 text-[9px] text-slate-600">
        {label}
      </span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-32 flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.06]">
      <CheckCircle2 className="h-6 w-6 text-slate-800" />
      <p className="mt-2 text-xs text-slate-600">{text}</p>
    </div>
  );
}

export default Dashboard;