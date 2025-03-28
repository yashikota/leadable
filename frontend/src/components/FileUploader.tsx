import {
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  useRef,
  useState,
} from "react";
import { CircleCheckBig, CircleX, FileUp } from "lucide-react";

type FileUploaderProps = {
  onFileSelected: (file: File | null) => void;
  isTranslating: boolean;
  translationComplete: boolean;
  onTranslate: () => void;
  error: string | null;
  file: File | null;
};

export function FileUploader({
  onFileSelected,
  isTranslating,
  translationComplete,
  onTranslate,
  error,
  file,
}: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      validateAndSetFile(files[0]);
    }
  };

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    if (file.type !== "application/pdf") {
      onFileSelected(null);
      return;
    }

    onFileSelected(file);
  };

  const handleClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      handleClick();
    }
  };

  return (
    <div className="card">
      <div className="card-body">
        <div
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all duration-200 ${isDragging
              ? "border-primary bg-base-200"
              : "border-base-300 hover:border-primary/50"
            }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
        >
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept="application/pdf"
            onChange={handleFileInputChange}
          />

          {!file ? (
            <div className="flex flex-col items-center justify-center">
              <FileUp size={48} className="text-base-content/70" />
              <p className="mt-4 text-lg font-medium">
                PDFファイルをドロップ
              </p>
              <p className="mt-2 text-sm text-base-content/70">
                または、クリックしてファイルを選択
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center">
              <CircleCheckBig size={48} className="text-success" />
              <p className="mt-4 text-lg font-medium">{file.name}</p>
              <p className="mt-2 text-sm text-base-content/70">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          )}
        </div>

        {error && (
          <div className="alert alert-error bg-red-200 mt-2">
            <CircleX size={24} />
            <span>{error}</span>
          </div>
        )}

        <div className="card-actions justify-center mt-2">
          {file && !translationComplete && (
            <button
              type="button"
              className={`btn btn-neutral ${isTranslating ? "btn-disabled" : ""}`}
              onClick={onTranslate}
              disabled={isTranslating}
            >
              {isTranslating ? (
                <>
                  <span className="loading loading-spinner" />
                  アップロード中
                </>
              ) : (
                "アップロード"
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
