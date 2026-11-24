import type { JobStatus } from "../api";

const STEPS = [
  { key: "extracting", label: "Extracting Clauses" },
  { key: "classifying", label: "Classifying Risks" },
  { key: "comparing", label: "Comparing to Templates" },
  { key: "reporting", label: "Generating Report" },
  { key: "done", label: "Complete" },
];

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500 text-white",
  high: "bg-orange-400 text-white",
  medium: "bg-yellow-300 text-black",
  low: "bg-green-400 text-white",
  unknown: "bg-gray-300 text-black",
};

function stepIndex(status: string): number {
  return STEPS.findIndex((s) => s.key === status);
}

interface Props {
  job: JobStatus;
}

export default function ProgressTracker({ job }: Props) {
  const current = stepIndex(job.status);

  return (
    <div className="w-full max-w-2xl flex flex-col gap-6">
      {/* Step indicators */}
      <ol className="flex items-center w-full">
        {STEPS.map((step, i) => {
          const done = current > i;
          const active = current === i;
          return (
            <li
              key={step.key}
              className={`flex items-center ${i < STEPS.length - 1 ? "flex-1" : ""}`}
            >
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                    ${done ? "bg-indigo-600 text-white" : active ? "bg-indigo-400 text-white animate-pulse" : "bg-gray-200 text-gray-500"}`}
                >
                  {done ? "✓" : i + 1}
                </div>
                <span className={`text-xs whitespace-nowrap ${active ? "text-indigo-600 font-semibold" : "text-gray-500"}`}>
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`h-1 flex-1 mx-1 rounded ${done ? "bg-indigo-600" : "bg-gray-200"}`} />
              )}
            </li>
          );
        })}
      </ol>

      {/* Error */}
      {job.status === "error" && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          <strong>Analysis failed:</strong> {job.error || "Unknown error"}
        </div>
      )}

      {/* Live clause table (shown once classifying begins) */}
      {job.clauses.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-white">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Severity</th>
                <th className="px-3 py-2 text-left">Score</th>
                <th className="px-3 py-2 text-left">Rationale</th>
              </tr>
            </thead>
            <tbody>
              {job.clauses.map((c) => (
                <tr key={c.clause_number} className="border-t border-gray-100 even:bg-gray-50">
                  <td className="px-3 py-2 font-mono">{c.clause_number}</td>
                  <td className="px-3 py-2 capitalize">{c.clause_type}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${SEVERITY_COLORS[c.risk_severity] || SEVERITY_COLORS.unknown}`}>
                      {(c.risk_severity || "unknown").toUpperCase()}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono">{c.risk_score?.toFixed(2) ?? "—"}</td>
                  <td className="px-3 py-2 text-gray-600 max-w-xs truncate">{c.risk_rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
