import type { JobStatus } from "../api";
import { reportUrl } from "../api";

interface Props {
  job: JobStatus;
  onReset: () => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500 text-white",
  high: "bg-orange-400 text-white",
  medium: "bg-yellow-300 text-black",
  low: "bg-green-400 text-white",
};

function countBySeverity(clauses: JobStatus["clauses"]) {
  const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  clauses.forEach((c) => {
    if (c.risk_severity in counts) counts[c.risk_severity]++;
  });
  return counts;
}

export default function ReportDownload({ job, onReset }: Props) {
  const counts = countBySeverity(job.clauses);

  return (
    <div className="flex flex-col items-center gap-6 w-full max-w-2xl">
      <div className="text-5xl">✅</div>
      <h2 className="text-2xl font-bold text-gray-800">Analysis Complete</h2>
      <p className="text-gray-500 text-sm">{job.filename}</p>

      {/* Severity chips */}
      <div className="flex gap-3 flex-wrap justify-center">
        {(["critical", "high", "medium", "low"] as const).map((sev) => (
          <div
            key={sev}
            className={`px-4 py-2 rounded-full font-semibold text-sm ${SEVERITY_COLORS[sev]}`}
          >
            {sev.toUpperCase()}: {counts[sev]}
          </div>
        ))}
      </div>

      {/* Download button */}
      <a
        href={reportUrl(job.job_id)}
        download
        className="px-8 py-3 bg-indigo-600 text-white rounded-lg font-semibold text-lg hover:bg-indigo-700 transition-colors shadow"
      >
        Download PDF Report
      </a>

      {/* Clause table */}
      {job.clauses.length > 0 && (
        <div className="w-full overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-white">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Severity</th>
                <th className="px-3 py-2 text-left">Score</th>
                <th className="px-3 py-2 text-left">Rationale</th>
                <th className="px-3 py-2 text-left">Deviation</th>
              </tr>
            </thead>
            <tbody>
              {[...job.clauses]
                .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
                .map((c) => (
                  <tr key={c.clause_number} className="border-t border-gray-100 even:bg-gray-50">
                    <td className="px-3 py-2 font-mono">{c.clause_number}</td>
                    <td className="px-3 py-2 capitalize">{c.clause_type}</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${SEVERITY_COLORS[c.risk_severity] || "bg-gray-200 text-black"}`}>
                        {(c.risk_severity || "?").toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono">{c.risk_score?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2 text-gray-600 max-w-xs">{c.risk_rationale}</td>
                    <td className="px-3 py-2 text-gray-500 max-w-xs text-xs">{c.deviation_notes || "—"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      <button
        onClick={onReset}
        className="text-indigo-600 underline text-sm hover:text-indigo-800"
      >
        Analyze another contract
      </button>
    </div>
  );
}
