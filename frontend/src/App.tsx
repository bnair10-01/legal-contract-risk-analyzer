import { useCallback, useEffect, useRef, useState } from "react";
import { createJob, getJob, type JobStatus } from "./api";
import UploadZone from "./components/UploadZone";
import ProgressTracker from "./components/ProgressTracker";
import ReportDownload from "./components/ReportDownload";

type Screen = "upload" | "progress" | "done";

export default function App() {
  const [screen, setScreen] = useState<Screen>("upload");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const startPolling = useCallback((jobId: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJob(jobId);
        setJob(status);
        if (status.status === "done") {
          stopPolling();
          setScreen("done");
        } else if (status.status === "error") {
          stopPolling();
        }
      } catch {
        // keep polling
      }
    }, 2000);
  }, []);

  useEffect(() => () => stopPolling(), []);

  const handleUpload = async (file: File) => {
    setUploadError(null);
    setUploading(true);
    try {
      const { job_id } = await createJob(file);
      const initialJob = await getJob(job_id);
      setJob(initialJob);
      setScreen("progress");
      startPolling(job_id);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    setJob(null);
    setUploadError(null);
    setScreen("upload");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-indigo-900 flex flex-col items-center justify-start py-16 px-4">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-white mb-2">
          Legal Contract Risk Analyzer
        </h1>
        <p className="text-indigo-300 text-lg">
          Autonomous AI agent — extract, classify, and score contract risks in minutes
        </p>
      </div>

      {/* Card */}
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-4xl flex flex-col items-center gap-6">
        {screen === "upload" && (
          <>
            <UploadZone onUpload={handleUpload} loading={uploading} />
            {uploading && (
              <p className="text-indigo-600 text-sm animate-pulse">Uploading…</p>
            )}
            {uploadError && (
              <p className="text-red-500 text-sm">{uploadError}</p>
            )}
          </>
        )}

        {screen === "progress" && job && (
          <>
            <h2 className="text-xl font-semibold text-gray-700">
              Analyzing: <span className="text-indigo-600">{job.filename}</span>
            </h2>
            <ProgressTracker job={job} />
            {job.status === "error" && (
              <button
                onClick={handleReset}
                className="text-indigo-600 underline text-sm"
              >
                Start over
              </button>
            )}
          </>
        )}

        {screen === "done" && job && (
          <ReportDownload job={job} onReset={handleReset} />
        )}
      </div>

      {/* Pipeline diagram footer */}
      <div className="mt-10 flex items-center gap-2 text-indigo-300 text-xs flex-wrap justify-center">
        {["PDF Upload", "Clause Extraction", "Risk Classification", "Template Comparison", "PDF Report"].map(
          (step, i, arr) => (
            <>
              <span key={step} className="bg-indigo-800 bg-opacity-60 px-3 py-1 rounded-full">
                {step}
              </span>
              {i < arr.length - 1 && <span key={`arrow-${i}`}>→</span>}
            </>
          )
        )}
      </div>
    </div>
  );
}
