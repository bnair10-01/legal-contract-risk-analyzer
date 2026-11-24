import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";

interface Props {
  onUpload: (file: File) => void;
  loading: boolean;
}

export default function UploadZone({ onUpload, loading }: Props) {
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[]) => {
      setError(null);
      if (accepted.length === 0) {
        setError("Please upload a PDF file.");
        return;
      }
      onUpload(accepted[0]);
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: loading,
  });

  return (
    <div className="flex flex-col items-center gap-4">
      <div
        {...getRootProps()}
        className={`w-full max-w-lg border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-indigo-500 bg-indigo-50" : "border-gray-300 bg-gray-50 hover:border-indigo-400"}
          ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <input {...getInputProps()} />
        <div className="text-5xl mb-4">📄</div>
        <p className="text-lg font-medium text-gray-700">
          {isDragActive ? "Drop the PDF here" : "Drag & drop a contract PDF"}
        </p>
        <p className="text-sm text-gray-500 mt-2">or click to browse (max 20MB)</p>
      </div>
      {error && <p className="text-red-500 text-sm">{error}</p>}
    </div>
  );
}
