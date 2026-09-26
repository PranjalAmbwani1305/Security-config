import { Link } from "react-router-dom";
import Sidebar from "../components/Sidebar";

function Dashboard() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="flex min-h-screen">
        <Sidebar />

        <main className="min-w-0 flex-1 p-8">

          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-blue-400">
                Security Operations
              </p>

              <h1 className="mt-2 text-3xl font-bold tracking-tight">
                Security Compliance Dashboard
              </h1>

              <p className="mt-2 text-slate-400">
                Monitor security configuration and compliance assessments.
              </p>
            </div>

            <Link
              to="/engagements"
              className="rounded-xl bg-blue-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/10 transition hover:bg-blue-400"
            >
              + New Assessment
            </Link>
          </div>

          {/* Stats */}
          <div className="mt-8 grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">

            <StatCard
              label="Engagements"
              value="0"
              description="Active assessments"
            />

            <StatCard
              label="Compliance"
              value="0%"
              description="Overall security posture"
            />

            <StatCard
              label="Open Findings"
              value="0"
              description="Require attention"
            />

            <StatCard
              label="Critical Risks"
              value="0"
              description="Immediate attention"
            />

          </div>

          {/* Main grid */}
          <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-3">

            {/* Compliance */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 xl:col-span-2">

              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">
                    Compliance Overview
                  </h2>

                  <p className="mt-1 text-sm text-slate-500">
                    Current security assessment posture
                  </p>
                </div>

                <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-400">
                  No data
                </span>
              </div>

              <div className="mt-8 flex items-center gap-8">

                {/* Circle */}
                <div className="relative flex h-40 w-40 shrink-0 items-center justify-center rounded-full border-[12px] border-slate-800">
                  <div className="text-center">
                    <p className="text-3xl font-bold">0%</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Compliance
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  <StatusRow
                    label="Compliant"
                    value="0"
                  />

                  <StatusRow
                    label="Non-Compliant"
                    value="0"
                  />

                  <StatusRow
                    label="Not Reviewed"
                    value="0"
                  />
                </div>

              </div>
            </div>

            {/* Risk */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

              <h2 className="text-lg font-semibold">
                Risk Overview
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Current risk distribution
              </p>

              <div className="mt-7 space-y-5">

                <RiskRow
                  label="Critical"
                  value="0"
                  width="0%"
                />

                <RiskRow
                  label="High"
                  value="0"
                  width="0%"
                />

                <RiskRow
                  label="Medium"
                  value="0"
                  width="0%"
                />

                <RiskRow
                  label="Low"
                  value="0"
                  width="0%"
                />

              </div>

            </div>
          </div>

          {/* Getting Started */}
          <div className="mt-6 rounded-2xl border border-blue-500/10 bg-gradient-to-r from-blue-500/10 to-transparent p-6">

            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">

              <div>
                <p className="text-sm font-medium text-blue-400">
                  Get started
                </p>

                <h2 className="mt-1 text-xl font-semibold">
                  Start a Security Assessment
                </h2>

                <p className="mt-2 max-w-2xl text-sm text-slate-400">
                  Create an engagement, select a technology, review
                  security controls, and begin your assessment.
                </p>
              </div>

              <Link
                to="/engagements"
                className="shrink-0 rounded-xl border border-slate-700 bg-slate-900 px-5 py-3 text-sm font-medium transition hover:border-slate-600 hover:bg-slate-800"
              >
                Create Engagement →
              </Link>

            </div>
          </div>

        </main>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div className="group rounded-2xl border border-slate-800 bg-slate-900 p-6 transition duration-200 hover:-translate-y-1 hover:border-slate-700 hover:bg-slate-900/80">

      <p className="text-sm text-slate-400">
        {label}
      </p>

      <p className="mt-3 text-3xl font-bold tracking-tight">
        {value}
      </p>

      <p className="mt-2 text-xs text-slate-600">
        {description}
      </p>

    </div>
  );
}

function StatusRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex w-48 items-center justify-between">
      <span className="text-sm text-slate-400">
        {label}
      </span>

      <span className="font-semibold">
        {value}
      </span>
    </div>
  );
}

function RiskRow({
  label,
  value,
  width,
}: {
  label: string;
  value: string;
  width: string;
}) {
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span className="text-slate-400">
          {label}
        </span>

        <span className="font-medium">
          {value}
        </span>
      </div>

      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-slate-500 transition-all"
          style={{ width }}
        />
      </div>
    </div>
  );
}

export default Dashboard;