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
import type { AvailableModels, SelectOption, Task } from "./types/type";

const ADDRESS = import.meta.env.VITE_SERVER_ADDRESS;
const API_URL = `http://${ADDRESS}:8866`;

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [translationComplete, setTranslationComplete] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [translationTasks, setTranslationTasks] = useState<Task[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [availableModels, setAvailableModels] = useState<AvailableModels>({});
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    openai: "",
    anthropic: "",
    google: "",
    deepseek: "",
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
    Object.keys(availableModels)
      .filter((id) => id !== "ollama")
      .forEach(loadApiKey);
  }, [availableModels]);

  // Load saved provider and model on mount
  useEffect(() => {
    if (isLoadingModels || Object.keys(availableModels).length === 0) return;

    const savedProvider = localStorage.getItem("leadable-selected-provider");

    if (savedProvider && availableModels[savedProvider]) {
      setSelectedProvider(savedProvider);

      const savedModel = localStorage.getItem("leadable-selected-model");
      if (savedModel && availableModels[savedProvider].includes(savedModel)) {
        setSelectedModel(savedModel);
      } else if (availableModels[savedProvider].length > 0) {
        // Fallback to first model if saved model is not available
        setSelectedModel(availableModels[savedProvider][0]);
      }
    }
  }, [availableModels, isLoadingModels]);

  // Load models from API
  useEffect(() => {
    fetchAvailableModels();
    handleGetTasks();
  }, []);

  // Fetch available models from API
  const fetchAvailableModels = async () => {
    setIsLoadingModels(true);
    try {
      const response = await fetch(`${API_URL}/models`);
      if (!response.ok) {
        throw new Error("Failed to fetch models");
      }
      const data = await response.json();
      setAvailableModels(data);

      // Set default provider and model if available
      if (Object.keys(data).length > 0) {
        const firstProvider = Object.keys(data)[0];
        setSelectedProvider(firstProvider);

        if (data[firstProvider] && data[firstProvider].length > 0) {
          setSelectedModel(data[firstProvider][0]);
        }
      }
    } catch (err) {
      console.error("Failed to fetch models:", err);
    } finally {
      setIsLoadingModels(false);
    }
  };

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
      formData.append("source_lang", "en");
      formData.append("target_lang", "ja");
      formData.append("provider", selectedProvider);
      formData.append("model", selectedModel);
      formData.append("api_key", apiKeys[selectedProvider]);

      const response = await fetch(`${API_URL}/translate`, {
        method: "POST",
        body: formData,
      });

      if (response.status === 404) {
        throw new Error("プロバイダーまたはモデルが見つかりません");
      }
      if (response.status !== 200) {
        const errorData = await response
          .json()
          .catch(() => ({ message: "翻訳リクエストの受付に失敗しました" }));
        throw new Error(
          errorData.message || `HTTP error! status: ${response.status}`,
        );
      }
      resetForm();
      handleGetTasks();
    } catch (err) {
      console.error("Translation request failed:", err);
      const errorMessage =
        err instanceof Error
          ? (err as any).error || err.message
          : "翻訳に失敗しました";
      setError(errorMessage);
    } finally {
      setIsTranslating(false);
    }
  };

  const handleGetTasks = async () => {
    try {
      const response = await fetch(`${API_URL}/tasks`);
      if (!response.ok) {
        throw new Error("Failed to fetch translation tasks");
      }
      const data = (await response.json()) as Task[];
      setTranslationTasks(data);
    } catch (err) {
      console.error("Failed to fetch translation tasks:", err);
    }
  };

  // const handleGetTask = async (taskId: string) => {
  //   try {
  //     const response = await fetch(`${API_URL}/task/${taskId}`);
  //     if (!response.ok) {
  //       throw new Error("Failed to fetch translation task");
  //     }
  //     const data = (await response.json()) as Task;
  //     setTranslationTasks((prev) => [...prev, data]);
  //   } catch (err) {
  //     console.error("Failed to fetch translation task:", err);
  //   }
  // };

  const handleDeleteTask = (task_id: string) => {
    fetch(`${API_URL}/task/${task_id}`, {
      method: "DELETE",
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to delete translation task");
        }
        setTranslationTasks((prev) =>
          prev.filter((task) => task.task_id !== task_id),
        );
      })
      .catch((err) => {
        console.error("Failed to delete translation task:", err);
      });
  };

  const resetForm = () => {
    setFile(null);
    setError(null);
    setTranslationComplete(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Convert available providers to react-select options
  const getProviderOptions = (): SelectOption[] => {
    return Object.keys(availableModels).map((providerId) => ({
      value: providerId,
      label: providerNameMap[providerId] || providerId,
    }));
  };

  // Mapping of provider IDs to display names
  const providerNameMap: Record<string, string> = {
    ollama: "Ollama",
    openai: "OpenAI",
    anthropic: "Anthropic",
    google: "Gemini",
    deepseek: "DeepSeek",
  };

  // ステータスの日本語表示を取得
  const getStatusLabel = (status: string): string => {
    switch (status) {
      case "pending":
        return "待機中";
      case "in_progress":
        return "処理中";
      case "completed":
        return "完了";
      case "failed":
        return "失敗";
      default:
        return status;
    }
  };

  // ステータスに応じたバッジのスタイルを取得
  const getStatusBadgeClass = (status: string): string => {
    switch (status) {
      case "pending":
        return "badge-warning";
      case "in_progress":
        return "badge-info";
      case "completed":
        return "badge-success";
      case "failed":
        return "badge-error";
      default:
        return "badge-neutral";
    }
  };

  // Get all models for the selected provider as react-select options
  const getModelOptions = (): SelectOption[] => {
    if (!availableModels[selectedProvider]) return [];
    return availableModels[selectedProvider].map((modelId) => ({
      value: modelId,
      label: modelId,
    }));
  };

  const handleProviderChange = (option: SelectOption | null) => {
    if (!option) return;

    const newProvider = option.value;
    setSelectedProvider(newProvider);

    // Save to localStorage
    localStorage.setItem("leadable-selected-provider", newProvider);

    // Set default model for the selected provider
    if (
      availableModels[newProvider] &&
      availableModels[newProvider].length > 0
    ) {
      const defaultModel = availableModels[newProvider][0];
      setSelectedModel(defaultModel);
      localStorage.setItem("leadable-selected-model", defaultModel);
    }
  };

  const handleModelChange = (option: SelectOption | null) => {
    if (!option) return;
    const model = option.value;
    setSelectedModel(model);
    localStorage.setItem("leadable-selected-model", model);
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
            </div>
          </div>
        </div>

        {translationTasks.length > 0 && (
          <div className="mt-4">
            <h2 className="text-xl font-bold mb-4">ファイル一覧</h2>
            <div className="overflow-x-auto">
              <table className="table w-full">
                <thead>
                  <tr>
                    <th>ファイル名</th>
                    <th>ステータス</th>
                    <th>作成日時</th>
                    <th className="text-right">アクション</th>
                  </tr>
                </thead>
                <tbody>
                  {translationTasks
                    .slice()
                    .sort(
                      (a, b) =>
                        new Date(b.timestamp).getTime() -
                        new Date(a.timestamp).getTime(),
                    )
                    .map((task: Task) => (
                      <tr key={task.task_id} className="hover">
                        <td className="max-w-xs truncate">{task.filename}</td>
                        <td>
                          <span
                            className={`badge ${getStatusBadgeClass(task.status)}`}
                          >
                            {getStatusLabel(task.status)}
                          </span>
                        </td>
                        <td>{new Date(task.timestamp).toLocaleString()}</td>
                        <td className="text-right">
                          <div className="join">
                            {task.status === "completed" ? (
                              <a
                                href={task.translated_url}
                                className="btn btn-sm join-item hover:bg-blue-200 border-none"
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label="開く"
                              >
                                <SquareArrowOutUpRight size={18} />
                              </a>
                            ) : (
                              <button
                                className="btn btn-sm join-item hover:bg-blue-200 border-none opacity-50 cursor-not-allowed"
                                disabled
                                aria-label="準備中"
                              >
                                <SquareArrowOutUpRight size={18} />
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn btn-sm join-item hover:bg-red-200 border-none"
                              onClick={() =>
                                (
                                  document.getElementById(
                                    `delete-modal-${task.task_id}`,
                                  ) as HTMLDialogElement
                                )?.showModal()
                              }
                              aria-label="削除"
                            >
                              <Trash2 size={18} />
                            </button>

                            {/* Delete confirmation modal */}
                            <dialog
                              id={`delete-modal-${task.task_id}`}
                              className="modal modal-bottom sm:modal-middle"
                            >
                              <div className="modal-box">
                                <p className="py-4 text-xl">
                                  「{task.filename}
                                  」を削除してもよろしいですか？
                                </p>
                                <div className="modal-action">
                                  <form method="dialog">
                                    <button className="btn mr-2">
                                      キャンセル
                                    </button>
                                  </form>
                                  <button
                                    type="button"
                                    className="btn btn-error"
                                    onClick={() => {
                                      handleDeleteTask(task.task_id);
                                      document.getElementById(
                                        `delete-modal-${task.task_id}`,
                                      );
                                    }}
                                  >
                                    削除する
                                  </button>
                                </div>
                              </div>
                            </dialog>
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
        <div className="collapse collapse-arrow bg-slate-100 mt-8 rounded-box">
          <input type="checkbox" />
          <div className="collapse-title flex justify-between items-center">
            <div className="text-lg font-medium flex items-center gap-2">
              <Settings size={18} />
              LLM設定
            </div>
            {selectedProvider && selectedModel && (
              <div className="text-sm font-medium">
                <span className="badge badge-secondary">
                  {providerNameMap[selectedProvider] || selectedProvider}
                </span>{" "}
                / <span className="badge badge-secondary">{selectedModel}</span>
              </div>
            )}
          </div>
          <div className="collapse-content">
            {selectedProvider !== "ollama" && !apiKeys[selectedProvider] && (
              <div className="alert alert-warning py-2 mb-2 text-sm">
                <span>
                  APIキーが必要です。下部でAPIキーを設定してください。
                </span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
              <div className="form-control">
                <label htmlFor="provider-select" className="label">
                  <span className="label-text">プロバイダー</span>
                </label>
                <select
                  id="provider-select"
                  className="select select-bordered w-full bg-white"
                  value={selectedProvider}
                  onChange={(e) => {
                    const newProvider = e.target.value;
                    handleProviderChange({
                      value: newProvider,
                      label: providerNameMap[newProvider] || newProvider,
                    });
                  }}
                  disabled={isLoadingModels}
                >
                  <option disabled value="">
                    プロバイダーを選択
                  </option>
                  {getProviderOptions().map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {isLoadingModels && (
                  <div className="mt-2 text-center">
                    <span className="loading loading-spinner loading-sm" />
                  </div>
                )}
              </div>

              <div className="form-control">
                <label htmlFor="model-select" className="label">
                  <span className="label-text">モデル</span>
                </label>
                <select
                  id="model-select"
                  className="select select-bordered w-full bg-white"
                  value={selectedModel}
                  onChange={(e) => {
                    const newModel = e.target.value;
                    handleModelChange({
                      value: newModel,
                      label: newModel,
                    });
                  }}
                  disabled={isLoadingModels}
                >
                  <option disabled value="">
                    モデルを選択
                  </option>
                  {getModelOptions().map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {isLoadingModels && (
                  <div className="mt-2 text-center">
                    <span className="loading loading-spinner loading-sm" />
                  </div>
                )}
              </div>
            </div>

            {selectedProvider !== "ollama" && (
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
                      APIキーはローカルに保存され、共有されません。
                    </span>
                  </label>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
