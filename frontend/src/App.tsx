import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import "./App.css";
import type { AvailableModels, Task } from "./types/type";
import { Navbar } from "./components/Navbar";
import { FileUploader } from "./components/FileUploader";
import { FileList } from "./components/FileList";
import { LLMSettings } from "./components/LLMSettings";

export const ADDRESS = import.meta.env.VITE_SERVER_ADDRESS;
const API_URL = `http://${ADDRESS}:8866`;

const providerNameMap: Record<string, string> = {
  ollama: "Ollama",
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Gemini",
  deepseek: "DeepSeek",
};

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [translationComplete, setTranslationComplete] = useState(false);
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
  const eventSourceRef = useRef<EventSource | null>(null);

  // Set up SSE connection
  useEffect(() => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Create a new EventSource connection
    const eventSource = new EventSource(`${API_URL}/tasks/updates`);
    eventSourceRef.current = eventSource;

    // Connection opened
    eventSource.addEventListener("connected", (event) => {
      console.log("SSE connection established", event);
    });

    // Handle task updates
    eventSource.addEventListener("update", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data?.task_id && data.status) {
          // Update the task in our local state
          setTranslationTasks((prevTasks) =>
            prevTasks.map((task) =>
              task.task_id === data.task_id
                ? { ...task, status: data.status }
                : task,
            ),
          );

          // If a task is completed or failed, refresh the task list to get the latest data
          if (data.status === "completed" || data.status === "failed") {
            handleGetTasks();
          }
        }
      } catch (error) {
        console.error("Error parsing SSE update:", error);
      }
    });

    // Error handling
    eventSource.addEventListener("error", (event) => {
      console.error("SSE connection error:", event);

      // Try to reconnect after a delay
      setTimeout(() => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = new EventSource(`${API_URL}/tasks/updates`);
        }
      }, 5000);
    });

    // Clean up on unmount
    return () => {
      eventSource.close();
    };
  }, []);

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

      // Check for error header
      const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
      if (errorMessage) {
        console.error("Failed to fetch models:", errorMessage);
        throw new Error(errorMessage);
      }

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

  const handleFileSelected = (selectedFile: File | null) => {
    setFile(selectedFile);
    setError(null);

    if (!selectedFile) {
      setError("PDFファイルのみ対応しています");
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

      // Check for error header
      const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
      if (errorMessage) {
        throw new Error(errorMessage);
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

      // Check for error header
      const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
      if (errorMessage) {
        console.error("Failed to fetch translation tasks:", errorMessage);
        return;
      }

      if (!response.ok) {
        throw new Error("Failed to fetch translation tasks");
      }
      const data = (await response.json()) as Task[];
      setTranslationTasks(data);
    } catch (err) {
      console.error("Failed to fetch translation tasks:", err);
    }
  };

  const handleDeleteTask = (taskId: string) => {
    fetch(`${API_URL}/task/${taskId}`, {
      method: "DELETE",
    })
      .then((response) => {
        // Check for error header
        const errorMessage = response.headers.get("X-LEADABLE-ERROR-MESSAGE");
        if (errorMessage) {
          console.error("Failed to delete translation task:", errorMessage);
          throw new Error(errorMessage);
        }

        if (!response.ok) {
          throw new Error("Failed to delete translation task");
        }
        setTranslationTasks((prev) =>
          prev.filter((task) => task.task_id !== taskId),
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
  };

  const handleProviderChange = (provider: string) => {
    setSelectedProvider(provider);

    // Save to localStorage
    localStorage.setItem("leadable-selected-provider", provider);

    // Set default model for the selected provider
    if (availableModels[provider] && availableModels[provider].length > 0) {
      const defaultModel = availableModels[provider][0];
      setSelectedModel(defaultModel);
      localStorage.setItem("leadable-selected-model", defaultModel);
    }
  };

  const handleModelChange = (model: string) => {
    setSelectedModel(model);
    localStorage.setItem("leadable-selected-model", model);
  };

  const handleApiKeyChange = (value: string) => {
    // Update state
    setApiKeys((prev) => ({
      ...prev,
      [selectedProvider]: value,
    }));

    // Save to localStorage
    debounceSaveApiKeys(selectedProvider, value);
  };

  return (
    <div className="min-h-screen bg-base-100">
      {/* Navbar */}
      <Navbar />

      <div className="container mx-auto px-4 py-8 max-w-3xl">
        {/* File Uploader */}
        <FileUploader
          onFileSelected={handleFileSelected}
          isTranslating={isTranslating}
          translationComplete={translationComplete}
          onTranslate={handleTranslate}
          error={error}
          file={file}
        />

        {/* File List */}
        <FileList
          tasks={translationTasks}
          onDeleteTask={handleDeleteTask}
        />

        {/* LLM Settings */}
        <LLMSettings
          selectedProvider={selectedProvider}
          selectedModel={selectedModel}
          availableModels={availableModels}
          isLoadingModels={isLoadingModels}
          onProviderChange={handleProviderChange}
          onModelChange={handleModelChange}
          apiKeys={apiKeys}
          onApiKeyChange={handleApiKeyChange}
          apiKeySaveStatus={apiKeySaveStatus}
          providerNameMap={providerNameMap}
        />
      </div>
    </div>
  );
}

export default App;
