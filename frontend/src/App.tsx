import {
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import "./App.css";
import {
  Check,
  CircleCheckBig,
  CircleX,
  FileUp,
  GithubIcon,
  Save,
  Settings,
  SquareArrowOutUpRight,
  Trash2,
} from "lucide-react";
import Select from "react-select";

const ADDRESS = import.meta.env.VITE_SERVER_ADDRESS;
const API_URL = `http://${ADDRESS}:8866`;

interface TranslatedFile {
  id: string;
  name: string;
  originalName: string;
  timestamp: Date;
  url: string;
}

// Define available LLM providers and models
interface LLMModel {
  id: string;
  name: string;
}

interface LLMProvider {
  id: string;
  name: string;
  models: LLMModel[];
}

const llmProviders: LLMProvider[] = [
  {
    id: "openai",
    name: "OpenAI",
    models: [
      { id: "gpt-4", name: "GPT-4" },
      { id: "gpt-4o", name: "GPT-4o" },
      { id: "o1", name: "o1" },
      { id: "o1-mini", name: "o1-mini" },
      { id: "o3-mini", name: "o3-mini" },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    models: [
      { id: "claude-2", name: "Claude 2" },
      { id: "claude-instant", name: "Claude Instant" },
    ],
  },
  {
    id: "google",
    name: "Google",
    models: [
      { id: "gemini-pro", name: "Gemini Pro" },
      { id: "gemini-ultra", name: "Gemini Ultra" },
    ],
  },
  {
    id: "ollama",
    name: "Ollama",
    models: [
      { id: "llama2", name: "Llama 2" },
      { id: "mistral", name: "Mistral" },
      { id: "codellama", name: "Code Llama" },
      { id: "phi", name: "Phi" },
      { id: "neural-chat", name: "Neural Chat" },
    ],
  },
];

// Define interface for react-select options
interface SelectOption {
  value: string;
  label: string;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [translationComplete, setTranslationComplete] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [translatedFiles, setTranslatedFiles] = useState<TranslatedFile[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("openai");
  const [selectedModel, setSelectedModel] = useState<string>("gpt-3.5-turbo");
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    openai: "",
    anthropic: "",
    google: "",
  });
  const [apiKeySaveStatus, setApiKeySaveStatus] = useState<
    "saved" | "unsaved" | "saving"
  >("saved");
  const [apiKeyTimer, setApiKeyTimer] = useState<NodeJS.Timeout | null>(null);

  // Load saved API keys on mount
  useEffect(() => {
    const loadApiKey = (provider: string) => {
      const savedKey = localStorage.getItem(`leadable-api-key-${provider}`);
      if (savedKey) {
        setApiKeys((prev) => ({
          ...prev,
          [provider]: savedKey,
        }));
      }
    };

    // Load keys for each provider
    llmProviders
      .map((p) => p.id)
      .filter((id) => id !== "ollama")
      .forEach(loadApiKey);
  }, []);

  // Debounce save to localStorage
  const debounceSaveApiKeys = useCallback(
    (provider: string, key: string) => {
      setApiKeySaveStatus("unsaved");

      // Clear any existing timer
      if (apiKeyTimer) {
        clearTimeout(apiKeyTimer);
      }

      // Set a new timer
      const timer = setTimeout(() => {
        setApiKeySaveStatus("saving");
        try {
          localStorage.setItem(`leadable-api-key-${provider}`, key);
          // Wait a short delay to show "saving" status before showing "saved"
          setTimeout(() => setApiKeySaveStatus("saved"), 300);
        } catch (error) {
          console.error(`Failed to save API key for ${provider}`, error);
        }
      }, 1000); // Save after 1 second of inactivity

      setApiKeyTimer(timer);
    },
    [apiKeyTimer],
  );

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

      const data = await response.json();
      const fileUrl = data.url;

      setTranslationComplete(true);
      // Add the translated file to the list
      if (file) {
        const newTranslatedFile = {
          id: "1",
          name: file.name,
          originalName: file.name,
          timestamp: new Date(),
          url: fileUrl,
        };
        setTranslatedFiles((prev) => [newTranslatedFile, ...prev]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "翻訳に失敗しました");
    } finally {
      setIsTranslating(false);
    }
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

  // Convert llmProviders models to react-select options
  const getProviderOptions = (): SelectOption[] => {
    return llmProviders.map((provider) => ({
      value: provider.id,
      label: provider.name,
    }));
  };

  // Get all models for the selected provider as react-select options
  const getModelOptions = (): SelectOption[] => {
    const provider = llmProviders.find((p) => p.id === selectedProvider);
    if (!provider) return [];

    const modelOptions = provider.models.map((model) => ({
      value: model.id,
      label: model.name,
    }));

    return modelOptions;
  };

  const handleProviderChange = (option: SelectOption | null) => {
    if (!option) return;

    const newProvider = option.value;
    setSelectedProvider(newProvider);

    // Set default model for the selected provider
    const provider = llmProviders.find((p) => p.id === newProvider);
    if (provider && provider.models.length > 0) {
      setSelectedModel(provider.models[0].id);
    }
  };

  const handleModelChange = (option: SelectOption | null) => {
    if (!option) return;
    setSelectedModel(option.value);
  };

  // Find the current selected option
  const getCurrentModelOption = (): SelectOption | undefined => {
    return getModelOptions().find((option) => option.value === selectedModel);
  };

  const getCurrentProviderOption = (): SelectOption | undefined => {
    return getProviderOptions().find(
      (option) => option.value === selectedProvider,
    );
  };

  const handleApiKeyChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { value } = e.target;

    // Update state
    setApiKeys((prev) => ({
      ...prev,
      [selectedProvider]: value,
    }));

    // Save to localStorage
    debounceSaveApiKeys(selectedProvider, value);
  };

  // Render save status icon
  const renderSaveStatus = () => {
    switch (apiKeySaveStatus) {
      case "saved":
        return <Check size={16} className="text-success" />;
      case "saving":
        return <div className="loading loading-spinner loading-xs" />;
      case "unsaved":
        return <Save size={16} className="text-warning" />;
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
          <a
            href="https://github.com/yashikota/leadable"
            target="_blank"
            className="btn btn-outline border-none"
            rel="noreferrer"
          >
            <GithubIcon />
          </a>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 max-w-3xl">
        {/* Dropzone */}
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
                  <a
                    href={translatedFiles.length > 0 ? translatedFiles[0].url : '#'}
                    className="btn btn-success flex-1"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <SquareArrowOutUpRight size={20} className="mr-2" />
                    開く
                  </a>
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
                <tbody>
                  {translatedFiles.map((file) => (
                    <tr key={file.id} className="hover">
                      <td className="max-w-xs truncate">{file.name}</td>
                      <td>{formatTimestamp(file.timestamp)}</td>
                      <td className="text-right">
                        <div className="join">
                          <a
                            href={file.url}
                            className="btn btn-sm border-none bg-none join-item hover:bg-gray-200"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <SquareArrowOutUpRight size={18} />
                          </a>
                          <button
                            type="button"
                            className="btn btn-sm btn-error border-none bg-none join-item ml-2 hover:bg-red-200"
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

        {/* Settings */}
        <div className="card bg-slate-100 mt-8 rounded-box">
          <div className="card-body">
            <h3 className="card-title text-lg flex items-center gap-2">
              <Settings size={18} />
              LLM設定
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
              <div className="form-control">
                <label htmlFor="provider-select" className="label">
                  <span className="label-text">プロバイダー</span>
                </label>
                <Select
                  inputId="provider-select"
                  className="basic-single"
                  classNamePrefix="select"
                  value={getCurrentProviderOption()}
                  onChange={handleProviderChange}
                  options={getProviderOptions()}
                  isSearchable={false}
                  placeholder="プロバイダーを選択"
                />
              </div>

              <div className="form-control">
                <label htmlFor="model-select" className="label">
                  <span className="label-text">モデル</span>
                </label>
                <Select
                  inputId="model-select"
                  className="basic-single"
                  classNamePrefix="select"
                  value={getCurrentModelOption()}
                  onChange={handleModelChange}
                  options={getModelOptions()}
                  isSearchable={true}
                  placeholder="モデルを選択"
                />
              </div>
            </div>

            <div className="mt-4">
              <div className="form-control w-full">
                <label htmlFor="api-key-input" className="label">
                  <span className="label-text">API キー</span>
                  <span className="label-text-alt flex items-center gap-1">
                    {apiKeySaveStatus === "saved"
                      ? "保存済み"
                      : apiKeySaveStatus === "saving"
                        ? "保存中..."
                        : "未保存"}
                    {renderSaveStatus()}
                  </span>
                </label>
                <div className="join w-full">
                  <input
                    id="api-key-input"
                    type="password"
                    placeholder="sk-*************************************"
                    className="input input-bordered input-primary w-full bg-white"
                    value={apiKeys[selectedProvider] || ""}
                    onChange={handleApiKeyChange}
                  />
                </div>
                <label htmlFor="api-key-input" className="label">
                  <span className="label-text-alt text-base-content/70 mt-2">
                    APIキーを入力してください。これはローカルに保存され、他のユーザーとは共有されません。
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
