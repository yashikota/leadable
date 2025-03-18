import {
  useState,
  useRef,
  type DragEvent,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import "./App.css";
import {
  CircleCheckBig,
  CircleX,
  FileDown,
  FileUp,
  Trash2,
} from "lucide-react";

const API_URL =
  import.meta.env.VITE_LEADABLE_API_URL || "http://localhost:8000";

interface TranslatedFile {
  id: string;
  name: string;
  originalName: string;
  timestamp: Date;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [translationComplete, setTranslationComplete] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [translatedFiles, setTranslatedFiles] = useState<TranslatedFile[]>([]);

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
    setError(null);

    if (file.type !== "application/pdf") {
      setError("PDFファイルのみ対応しています");
      setFile(null);
      return;
    }

    setFile(file);
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

  const handleTranslate = async () => {
    if (!file) return;

    setIsTranslating(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/translate/`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || "翻訳リクエストに失敗しました");
      }

      setTranslationComplete(true);

      // Add the translated file to the list
      if (file) {
        const newTranslatedFile = {
          id: crypto.randomUUID(),
          name: file.name,
          originalName: file.name,
          timestamp: new Date(),
        };
        setTranslatedFiles((prev) => [newTranslatedFile, ...prev]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "翻訳に失敗しました");
    } finally {
      setIsTranslating(false);
    }
  };

  const handleDownload = () => {
    if (file) {
      window.open(`${API_URL}/download/${file.name}`, "_blank");
    }
  };

  const handleDownloadFile = (fileName: string) => {
    window.open(`${API_URL}/download/${fileName}`, "_blank");
  };

  const handleDeleteFile = (id: string) => {
    setTranslatedFiles((prev) => prev.filter((file) => file.id !== id));
  };

  const formatTimestamp = (date: Date): string => {
    return new Intl.DateTimeFormat("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  const resetForm = () => {
    setFile(null);
    setError(null);
    setTranslationComplete(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="min-h-screen bg-base-100">
      {/* Navbar */}
      <div className="navbar bg-base-200 shadow-md">
        <div className="navbar-start flex items-center">
          <div className="flex items-center gap-2">
            <img src="/icon.png" alt="Leadable" className="h-8 w-auto" />
            <span className="text-2xl font-semibold">Leadable</span>
          </div>
        </div>
        <div className="navbar-end">
          <a href="/settings" className="btn btn-outline">
            設定
          </a>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <div className="card bg-base-100">
          <div className="card-body">
            <div
              className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all duration-200 ${
                isDragging
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
              <div className="alert alert-error mt-4">
                <CircleX size={24} />
                <span>{error}</span>
              </div>
            )}

            <div className="card-actions justify-center mt-6">
              {file && !translationComplete && (
                <button
                  type="button"
                  className={`btn btn-primary ${isTranslating ? "btn-disabled" : ""}`}
                  onClick={handleTranslate}
                  disabled={isTranslating}
                >
                  {isTranslating ? (
                    <>
                      <span className="loading loading-spinner" />
                      翻訳中...
                    </>
                  ) : (
                    "PDFを翻訳"
                  )}
                </button>
              )}

              {translationComplete && (
                <div className="flex flex-col sm:flex-row gap-2 w-full">
                  <button
                    type="button"
                    className="btn btn-success flex-1"
                    onClick={handleDownload}
                  >
                    <FileDown size={20} className="mr-2" />
                    ダウンロード
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline flex-1"
                    onClick={resetForm}
                  >
                    新しいPDFを翻訳
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {translatedFiles.length > 0 && (
          <div className="mt-4">
            <h2 className="text-xl font-bold mb-4">翻訳済みファイル一覧</h2>
            <div className="overflow-x-auto">
              <table className="table w-full">
                <thead>
                  <tr>
                    <th>ファイル名</th>
                    <th>日時</th>
                    <th className="text-right">アクション</th>
                  </tr>
                </thead>
                <tbody>
                  {translatedFiles.map((file) => (
                    <tr key={file.id} className="hover">
                      <td className="max-w-xs truncate">{file.name}</td>
                      <td>{formatTimestamp(file.timestamp)}</td>
                      <td className="text-right">
                        <div className="join">
                          <button
                            type="button"
                            className="btn btn-sm join-item"
                            onClick={() =>
                              handleDownloadFile(file.originalName)
                            }
                            aria-label="ダウンロード"
                          >
                            <FileDown size={18} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-error join-item ml-2"
                            onClick={() => handleDeleteFile(file.id)}
                            aria-label="削除"
                          >
                            <Trash2 size={18} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
