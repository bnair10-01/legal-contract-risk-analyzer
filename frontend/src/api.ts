const BASE = "/api";

export async function createJob(file: File): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/jobs`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

export interface Clause {
  clause_number: number;
  clause_type: string;
  risk_severity: string;
  risk_score: number;
  risk_rationale: string;
  similarity_score: number;
  deviation_notes: string;
}

export interface JobStatus {
  job_id: string;
  filename: string;
  status: string;
  created_at: string;
  has_report: boolean;
  error: string | null;
  clauses: Clause[];
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error("Failed to fetch job status");
  return res.json();
}

export function reportUrl(jobId: string): string {
  return `${BASE}/jobs/${jobId}/report`;
}
